import numpy as np
from datetime import date

def year_fraction(start, end):
    return (end - start).days / 365.0

def zero_rate(T, curve):
    times, rates = zip(*curve)
    return np.interp(T, times, rates)

def discount_factor(T, curve):
    return np.exp(-zero_rate(T, curve) * T)

def simulate_terminal(spots, vols, corr, T, r, n_paths, seed=None):
    """
    corr : either a scalar 'rho' (equal-corr model)   or
           a full NxN positive-definite correlation matrix.
    """
    spots   = np.asarray(spots, dtype=float)
    vols    = np.asarray(vols,  dtype=float)
    N       = spots.size

    if np.isscalar(corr):                         # single-rho ⇒ homogeneous matrix
        rho       = float(corr)
        corr_mat  = np.full((N, N), rho)
        np.fill_diagonal(corr_mat, 1.0)
    else:
        corr_mat  = np.asarray(corr, dtype=float)
        assert corr_mat.shape == (N, N), "corr matrix dimension mismatch"

    L  = np.linalg.cholesky(corr_mat)             # Cholesky for N-variate normals
    rng = np.random.default_rng(seed)
    z   = rng.standard_normal((n_paths, N)) @ L.T

    drift     = (r - 0.5 * vols**2) * T
    diffusion = vols * np.sqrt(T) * z
    return spots * np.exp(drift + diffusion)      # shape (n_paths, N)


def cvc_payoff(paths, strike, weights):
    """
    weights : array of length N that sums to 1 (usual CvC convention)
    """
    weights = np.asarray(weights, dtype=float)
    basket  = paths @ weights
    indiv   = np.maximum(paths - strike, 0) @ weights
    return np.maximum(basket - strike, 0) - indiv
    
def price_cvc(spots, vols, rho, strike, weights, T, curve, n_paths=100_000, seed=None):
    r = zero_rate(T, curve)
    paths = simulate_terminal(np.array(spots), np.array(vols), rho, T, r, n_paths, seed)
    payoff = cvc_payoff(paths, strike, weights)
    return discount_factor(T, curve) * payoff.mean()

def implied_corr(market_price, spots, vols, strike, weights, T, curve, n_paths=100_000, tol=1e-4, max_iter=60):
    lo, hi = -0.999, 0.999
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        mid_price = price_cvc(spots, vols, mid, strike, weights, T, curve, n_paths)
        if abs(mid_price - market_price) < tol:
            return mid
        if mid_price > market_price:
            hi = mid
        else:
            lo = mid
    return mid

def bump(val, pct):
    return val * (1 + pct)

def bump_curve(curve, pct):
    return [(t, r * (1 + pct)) for t, r in curve]

# Greeks via central finite‑difference bump‑and‑revalue (important design choice)
def greeks_cvc(spots, vols, rho, strike, weights, T, curve, n_paths=100_000, bump_pct=1e-4):
    base = price_cvc(spots, vols, rho, strike, weights, T, curve, n_paths)
    # delta
    deltas = []
    for i in range(2):
        up_spots = spots.copy(); up_spots[i] = bump(up_spots[i], bump_pct)
        down_spots = spots.copy(); down_spots[i] = bump(down_spots[i], -bump_pct)
        price_up = price_cvc(up_spots, vols, rho, strike, weights, T, curve, n_paths)
        price_down = price_cvc(down_spots, vols, rho, strike, weights, T, curve, n_paths)
        deltas.append((price_up - price_down) / (2 * spots[i] * bump_pct))
    # vega and volga
    vegas, volga = [], []
    for i in range(2):
        up_vols = vols.copy(); up_vols[i] = bump(up_vols[i], bump_pct)
        down_vols = vols.copy(); down_vols[i] = bump(down_vols[i], -bump_pct)
        price_up = price_cvc(spots, up_vols, rho, strike, weights, T, curve, n_paths)
        price_down = price_cvc(spots, down_vols, rho, strike, weights, T, curve, n_paths)
        vegas.append((price_up - price_down) / (2 * vols[i] * bump_pct))
        volga.append((price_up - 2 * base + price_down) / ((vols[i] * bump_pct) ** 2))
    # vanna
    vanna = []
    for i in range(2):
        up_spot = spots.copy(); up_spot[i] = bump(up_spot[i], bump_pct)
        down_spot = spots.copy(); down_spot[i] = bump(down_spot[i], -bump_pct)
        up_vol = vols.copy(); up_vol[i] = bump(up_vol[i], bump_pct)
        down_vol = vols.copy(); down_vol[i] = bump(down_vol[i], -bump_pct)
        pp = price_cvc(up_spot, up_vol, rho, strike, weights, T, curve, n_paths)
        mm = price_cvc(down_spot, down_vol, rho, strike, weights, T, curve, n_paths)
        pm = price_cvc(up_spot, down_vol, rho, strike, weights, T, curve, n_paths)
        mp = price_cvc(down_spot, up_vol, rho, strike, weights, T, curve, n_paths)
        vanna.append((pp - pm - mp + mm) / (4 * spots[i] * vols[i] * bump_pct ** 2))
    # rho sensitivity
    rho_up = bump(rho, bump_pct); rho_down = bump(rho, -bump_pct)
    price_up = price_cvc(spots, vols, rho_up, strike, weights, T, curve, n_paths)
    price_down = price_cvc(spots, vols, rho_down, strike, weights, T, curve, n_paths)
    rho_sensitivity = (price_up - price_down) / (2 * rho * bump_pct) if rho != 0 else np.nan
    # rate sensitivity
    curve_up = bump_curve(curve, bump_pct)
    curve_down = bump_curve(curve, -bump_pct)
    price_up = price_cvc(spots, vols, rho, strike, weights, T, curve_up, n_paths)
    price_down = price_cvc(spots, vols, rho, strike, weights, T, curve_down, n_paths)
    rho_r = (price_up - price_down) / (2 * bump_pct * zero_rate(T, curve))
    # maturity sensitivity
    T_up = T * (1 + bump_pct); T_down = T * (1 - bump_pct)
    price_up = price_cvc(spots, vols, rho, strike, weights, T_up, curve, n_paths)
    price_down = price_cvc(spots, vols, rho, strike, weights, T_down, curve, n_paths)
    theta = (price_up - price_down) / (2 * T * bump_pct)
    return {
        "price": base,
        "delta": deltas,
        "vega": vegas,
        "volga": volga,
        "vanna": vanna,
        "rho": rho_sensitivity,
        "rho_r": rho_r,
        "theta": theta,
    }

# --- Test cases ---
cases = [
    {
        "pricing_date": date(2025, 7, 7),
        "s1": 100.0,
        "s2": 120.0,
        "maturity_date": date(2026, 7, 7),
        "option_type": "call",
        "strike_pct": 1.0,
        "rho": 0.30,
    },
    {
        "pricing_date": date(2025, 7, 7),
        "s1": 95.0,
        "s2": 105.0,
        "maturity_date": date(2026, 1, 7),
        "option_type": "call",
        "strike_pct": 1.0,
        "rho": -0.25,
    },
]

curve = [(0.0, 0.03), (5.0, 0.03)]
weights = np.array([0.5, 0.5])
vols = [0.20, 0.25]

for i, c in enumerate(cases, 1):
    T = year_fraction(c["pricing_date"], c["maturity_date"])
    spots = [c["s1"], c["s2"]]
    strike = np.mean(spots) * c["strike_pct"]
    price = price_cvc(spots, vols, c["rho"], strike, weights, T, curve, n_paths=50_000, seed=42)
    implied_rho = implied_corr(price, spots, vols, strike, weights, T, curve, n_paths=50_000)
    greeks = greeks_cvc(spots, vols, c["rho"], strike, weights, T, curve, n_paths=50_000)
    print(f"\n--- Case {i} ---")
    print(f"Market ρ input: {c['rho']:.4f}")
    print(f"Price          : {price:.6f}")
    print(f"Implied ρ      : {implied_rho:.4f}")
    for g, v in greeks.items():
        print(g, v)
        
# market price observed on the tape
p_mkt = 1.27        # dollars

# inputs (4-name equally-weighted basket)
spots   = [ 95, 103, 88, 110 ]
vols    = [ .21, .25, .19, .23 ]
weights = np.full(4, 0.25)
strike  = 100
T       = 0.75                      # 9-month maturity
curve   = [(0.0, 0.031), (1.0, 0.030)]

rho_star = implied_corr(
    market_price = p_mkt,
    spots   = spots,
    vols    = vols,
    strike  = strike,
    weights = weights,
    T       = T,
    curve   = curve,
    n_paths = 150_000                # raise for production
)

print(f"Implied average pairwise correlation = {rho_star:.4f}")

def greeks_cvc(
        spots, vols, rho, strike, weights, T, curve,
        n_paths=100_000, bump_pct=1e-4):

    base = price_cvc(spots, vols, rho, strike, weights, T, curve, n_paths)
    N    = len(spots)

    deltas, gammas = [], []
    for i in range(N):
        up   = spots.copy();  up[i]   *= 1 + bump_pct
        down = spots.copy();  down[i] *= 1 - bump_pct

        p_up   = price_cvc(up,   vols, rho, strike, weights, T, curve, n_paths)
        p_down = price_cvc(down, vols, rho, strike, weights, T, curve, n_paths)

        delta  = (p_up - p_down) / (2 * spots[i] * bump_pct)
        gamma  = (p_up - 2*base + p_down) / ((spots[i]*bump_pct)**2)

        deltas.append(delta)
        gammas.append(gamma)

    # --- existing vega / volga / vanna / rho / rho_r / theta code here ---
    …
    return {
        "price": base,
        "delta": deltas,
        "gamma": gammas,          # NEW
        "vega": vegas,
        "volga": volga,
        "vanna": vanna,
        "rho": rho_sensitivity,
        "rho_r": rho_r,
        "theta": theta,
    }
    
def cross_gamma(spots, i, j, bump_pct=1e-4):
    up_i  = spots.copy(); up_i[i] *= 1 + bump_pct
    up_j  = spots.copy(); up_j[j] *= 1 + bump_pct
    up_ij = up_i.copy();  up_ij[j] *= 1 + bump_pct

    p_ij  = price_cvc(up_ij, vols, rho, strike, weights, T, curve, n_paths)
    p_i   = price_cvc(up_i,  vols, rho, strike, weights, T, curve, n_paths)
    p_j   = price_cvc(up_j,  vols, rho, strike, weights, T, curve, n_paths)
    return (p_ij - p_i - p_j + base) / ((spots[i]*spots[j])*bump_pct**2)
    