import os
import xml.etree.cElementTree as ET
import datetime
import math
import numpy as np
import pandas as pd
import time
import argparse
import urllib.request
from xbbg import blp
from sklearn import linear_model

import urllib.request
url = 'http://repo.mfl-info.bmogc.net/files/bmoca.crt'
if not os.path.exists("C:\\Temp\\bmoca.crt"):
    os.makedirs("C:\\Temp", exist_ok=True)
    urllib.request.urlretrieve(url, "C:\\Temp\\bmoca.crt")

import pymfl_setup
pymfl_setup.start_mfl(pymfl_setup.registered_mfl(), True)
import pymfl
from pymfl.translator import translate
from Mfl.Service import Factory
from Mfl.DbTools.Cmdb import InstrumentLookup

from wex_export import generate_wex_spreadsheet


CMDB_OPTIONS = {'Matching': 'blank_when_unmatched'}


def define_support(directory: str) -> int:
    file_name = os.path.join(directory, '..', 'Configs', 'MflConfig.xml')
    if not os.path.exists(file_name):
        return 8
    root = ET.parse(file_name).getroot()
    support_num = root.find('.//SupportNum')
    if support_num is None:
        return 8
    return int(support_num.text)


def init_mfl(directory: str) -> None:
    import pymfl_setup
    pymfl_setup.start_mfl(directory, False)
    support_num = define_support(directory)
    local_app_data = os.environ['LOCALAPPDATA']
    pkgs = os.path.join(local_app_data, 'MFL', 'pkgs', f'support{support_num}', 'x64')
    os.environ['PATH'] = pkgs + os.pathsep + os.environ['PATH']


def load_price_from_cmdb(date: datetime.date, tickers: list, symbology: str, label: str, is_index: bool = False) -> list:
    quotes_load = translate(
        pymfl.Quotes().Load(
            CMDB_OPTIONS,
            date,
            label,
            None,
            None,
            None,
            None,
            None,
            'MID' if is_index else 'BID/OFFER/LAST/VOLUME/OPEN INTEREST',
            None,
            pymfl.Securities().ByDatedTicker(date, symbology, tickers)
        )
    )
    return list(quotes_load['VALUE1' if is_index else 'VALUE3'])


def convert_one_instrument_risks(risks: list) -> dict:
    return {risk.Instrument: risk.Value for risk in risks}


def convert_two_instrument_risks(risks: list) -> dict:
    return {(risk.Instrument1, risk.Instrument2): risk.Value for risk in risks}


def generate_contexts(ticker, valuation_date, expiry_date, vega_notional, swap_type):
    calendar = pymfl.Dates().calendar("NYSE")
    paylag = 2
    maturity_date = pymfl.Calendar.addBusDays(calendar, expiry_date, paylag, True)
    option_type = 'Call'
    currency = 'USD'
    ir_curve_name = 'USD_SOFR'
    is_live_curve = valuation_date == datetime.date.today()
    ir_curve = pymfl.Equities().LoadIrCurve(valuation_date, ir_curve_name, is_live_curve, None)

    symbology = 'BLOOMBERG'
    quote_label = 'SETTLE'
    dividend_label = 'NA CLOSE'
    is_index = ticker == "SPX"
    spot_ticker = ticker.replace('-', ' ')

    # Bypass CMDB for spot if valuing today to prevent null/stale data
    if valuation_date == datetime.date.today():
        bbg_ticker = f"{ticker} Index" if is_index else f"{ticker} US Equity"
        spot_price = blp.bdp(bbg_ticker, 'PX_LAST').iloc[0, 0]
    else:
        spot_price = load_price_from_cmdb(valuation_date, [spot_ticker], symbology, quote_label, is_index)[0]

    strike = spot_price

    div_cmdb = pymfl.CMDB().LoadDividends(dividend_label, ticker, valuation_date, {'map': symbology, 'useDates': True, 'pivotColumn': 'div_type'})
    dividend_schedule = pymfl.EquityUtilities().DvdArrayFromDBQuery(div_cmdb)
    forward = pymfl.Dividend().ForwardPrice(dividend_schedule, ir_curve, expiry_date, valuation_date, spot_price, None, None, None, None, None, None, None)

    vol_label = 'NA CLOSE'
    vol_load_options = {'map': symbology, 'useDates': True, 'Mid': True}
    vol_cmdb = pymfl.CMDB().LoadVolatilities(vol_label, ticker, valuation_date, vol_load_options)
    vol_surface = pymfl.EquityUtilities().VolArrayFromDBQuery(vol_cmdb)

    pf = pymfl.Securities().ByTicker("Bloomberg Equity", None, [ticker])
    inputOpt = {"p_date": valuation_date, "p_label": "NA CLOSE", "p_instance": "latest", "p_filter": pf}
    vcb_rn = pymfl.Request(None).Create("eq.query", "vcb")
    vcb = pymfl.Request(vcb_rn).ByName(inputOpt)
    vcb_ticker = translate(pymfl.Dict(vcb).Item(ticker))
    vcb_dict = {
        'VolDate': vcb_ticker["VOL_DATE"],
        'VolSpot': 100.0,
        'TenorParameters': sorted(vcb_ticker["TENOR_PARAMETERS"], key=lambda x: x['Term'])
    }

    input_svi = {"p_date": valuation_date, "p_label": "NA CLOSE", "p_instance": "latest", "query": "svi", "p_filter": pf}
    svi_rn = pymfl.Request(None).Create("eq.query", "svi")
    svi_obj = pymfl.Request(svi_rn).ByName(input_svi)
    svi_ticker = pymfl.Dict(svi_obj).Item(ticker)
    svi_params = pymfl.EquityUtilities().SVIParametersFromDBQuery(svi_ticker)

    product = {
        'PercentStrike': 1.0, 'CurrencySymbol': 'USD', 'InceptionDate': valuation_date,
        'ExpiryDate': expiry_date, 'MaturityDate': maturity_date, 'Payoff': option_type,
        'FaceValue': strike, 'ExerciseType': 'European', 'InitialFixing': strike,
    }
    asset_data = {
        "Volatility": vol_surface, 'CurrencySymbol': currency, 'Dividend': dividend_schedule,
        'Price': spot_price, 'ForecastCurveSymbol': 'Discount', 'Symbol': ticker, 'SVIParameters': svi_params
    }
    currency_data = [{'Name': currency, 'CurveData': [{'Name': 'Discount'}]}]

    model_parameters = {
        'VERSION': '20160613', 'PricingMethod': 'Binomial', 'PricingBinomialSteps': -500,
        'SeparateThetaAndCarry': True, 'IsForwardGreeks': False, 'ThetaSpotType': 'ConstantDiv',
        'ThetaCurveType': 'ConstantRate', 'CalibrationMethod': 'SVI',
        'SVIParameters': pymfl.SVIUtilities().GetSVIParams("ReFitExtreme"),
        'DeltaTweak': [0.001, 0.001], 'AbsoluteVegaTweak': 0.01, 'PhiTweak': 0.01, 'ThetaTweak': 1.0, 'VegaType': 'Single'
    }

    context_dict = {
        'Product': product,
        'AssetData': asset_data,
        'CurrencyData': currency_data,
        'ValueDate': valuation_date,
        'ModelParameters': model_parameters
    }
    context = pymfl.Equities().ApplyRecommendedModelParameters(
        pymfl.Equities().European_Contextualize_Temp(context_dict, [[ir_curve]], ir_curve)
    )

    vs_asset_data = {
        "Volatility": vol_surface, 'CurrencySymbol': currency, 'Dividend': dividend_schedule,
        'Price': spot_price, 'ForecastCurveSymbol': 'Discount', 'Symbol': ticker,
        "VolConvexityBasis": vcb_dict, 'SVIParameters': svi_params
    }

    schedule_dates = pymfl.Dates().businessDates(valuation_date, expiry_date, calendar)
    schedule = [{"Date": x, "Fixing": None} for x in schedule_dates]
    schedule[0]["Fixing"] = spot_price

    # NOTE: 21.0 is a placeholder used only to instantiate the variance/vol swap product.
    # The fair strike is set a few lines later after repricing no-strike / no-discount contexts.
    vs_product = {
        'CurrencySymbol': 'USD', 'InceptionDate': valuation_date, 'MaturityDate': maturity_date,
        'PayoffType': swap_type, 'TriggerType': 'Corridor', 'TriggerStyle': 'KnockOut',
        'VolatilityStrike': 21.0, 'VarianceUnits': vega_notional, 'UseDiscrete': False,
        'AnnualizationFactor': 252.0, 'Schedule': schedule, 'TriggerDay': 'Both', 'VERSION': '20141022'
    }

    vs_context_dict = {
        'Product': vs_product,
        'AssetData': vs_asset_data,
        'CurrencyData': currency_data,
        'ValueDate': valuation_date,
        'ModelParameters': model_parameters
    }
    vs_context = pymfl.Equities().ApplyRecommendedModelParameters(
        pymfl.Equities().VarianceSwap_Contextualize_Temp(vs_context_dict, [[ir_curve]], ir_curve)
    )

    discount_rule = "{ModelParameters.{Discount=x}}"
    volstrike_rule = "{Product.{VolatilityStrike=x}}"
    unit_rule = "{Product.{VarianceUnits=x}}"
    no_discount_ctxt = pymfl.MflData().SetProperty(vs_context, discount_rule, False)
    no_strike_ctxt = pymfl.MflData().SetProperty(
        pymfl.MflData().SetProperty(vs_context, discount_rule, False),
        volstrike_rule,
        0.0
    )

    v0 = pymfl.Equities().PV(no_discount_ctxt)
    v1 = pymfl.Equities().PV(no_strike_ctxt)
    fair_strike = v1 / vega_notional if swap_type == "Volatility" else np.sqrt(v1 / vega_notional)
    fair_units = vega_notional if swap_type == "Volatility" else vega_notional / (2.0 * fair_strike)
    vs_context = pymfl.MflData().SetProperty(
        pymfl.MflData().SetProperty(vs_context, volstrike_rule, fair_strike),
        unit_rule,
        fair_units
    )

    return context, vs_context


############################################################
# BEGIN CHANGED BLOCK: strike-universe helpers
############################################################

def _get_reference_spot_for_strike_filter(
    ticker: str,
    valuation_date: datetime.date
) -> float:
    is_index = ticker == "SPX"
    if valuation_date == datetime.date.today():
        bbg_ticker = f"{ticker} Index" if is_index else f"{ticker} US Equity"
        return blp.bdp(bbg_ticker, 'PX_LAST').iloc[0, 0]
    return load_price_from_cmdb(
        valuation_date,
        [ticker.replace('-', ' ')],
        'BLOOMBERG',
        'SETTLE',
        is_index
    )[0]


def _parse_strikes_from_chain_strings(chain_values: pd.Series, expiry_date: datetime.date) -> np.ndarray:
    exp_str = expiry_date.strftime("%m/%d/%y")
    filtered = chain_values[chain_values.astype(str).str.contains(exp_str, na=False)]
    strikes = filtered.astype(str).str.extract(r'[CP](\d+(?:\.\d+)?)').astype(float)[0].dropna().unique()
    strikes = np.sort(strikes.astype(float))
    return strikes


def get_bbg_strikes(
    ticker: str,
    expiry_date: datetime.date,
    valuation_date: datetime.date,
    moneyness: tuple = (0.1, 2.0)
) -> np.ndarray:
    if valuation_date is None:
        valuation_date = datetime.date.today()

    bbg_ticker = f"{ticker} Index" if ticker == "SPX" else f"{ticker} US Equity"

    bbg_exp = expiry_date.strftime("%Y%m%d")

    if valuation_date == datetime.date.today():
        spot = blp.bdp(bbg_ticker, 'PX_LAST').iloc[0, 0]
        chain = blp.bds(bbg_ticker, 'OPT_CHAIN', CHAIN_EXP_DT_OVRD=bbg_exp)
    else:
        is_index = (ticker == "SPX")
        spot_ticker = ticker.replace('-', ' ')
        spot = load_price_from_cmdb(valuation_date, [spot_ticker], 'BLOOMBERG', 'SETTLE', is_index)[0]
        val_date_str = valuation_date.strftime("%Y%m%d")
        chain = blp.bds(
            bbg_ticker,
            'OPT_CHAIN',
            SINGLE_DATE_OVERRIDE=val_date_str,
            CHAIN_EXP_DT_OVRD=bbg_exp
        )

    col_name = chain.columns[0]
    strikes = _parse_strikes_from_chain_strings(chain[col_name], expiry_date)
    strikes = strikes[(strikes >= spot * moneyness[0]) & (strikes <= spot * moneyness[1])]

    if len(strikes) < 2:
        raise ValueError(f"Bloomberg returned too few strikes for {ticker} {expiry_date} on {valuation_date}.")

    return strikes


def get_cmdb_strikes(
    ticker: str,
    expiry_date: datetime.date,
    valuation_date: datetime.date,
    moneyness: tuple = (0.1, 2.0)
) -> np.ndarray:
    """
    Historical listed strike retrieval.

    IMPORTANT:
    - The exact CMDB option-chain lookup API is desk-specific and was not present in the code snippet.
    - This function first attempts a CMDB/InstrumentLookup-based historical lookup if available.
    - If the local runtime does not expose a compatible lookup path, it falls back to Bloomberg's
      historical chain for continuity and raises only if neither path works.

    Replace the InstrumentLookup block below with the desk's canonical CMDB option-universe query
    once you confirm the exact method signature.
    """
    spot = _get_reference_spot_for_strike_filter(ticker, valuation_date)

    # Attempt a CMDB lookup first.
    try:
        lookup = InstrumentLookup()

        ############################################################
        # BEGIN CHANGED BLOCK: defensive CMDB lookup for historical strikes
        ############################################################
        #
        # The exact InstrumentLookup API is not inferable from the pasted file alone.
        # We try a few plausible access paths without hard-failing the whole script.
        # Once you know the exact CMDB method your desk uses, replace this section
        # with that explicit call and keep the downstream parsing/filtering.
        #
        ############################################################
        candidate_objects = []

        for attr_name in ["ByDateAndUnderlying", "ByUnderlyingAndDate", "LookupOptions", "Lookup"]:
            if hasattr(lookup, attr_name):
                method = getattr(lookup, attr_name)
                try:
                    result = method(ticker, valuation_date, expiry_date)
                    candidate_objects.append(result)
                except TypeError:
                    try:
                        result = method(valuation_date, ticker, expiry_date)
                        candidate_objects.append(result)
                    except Exception:
                        pass
                except Exception:
                    pass

        for obj in candidate_objects:
            if obj is None:
                continue

            if isinstance(obj, pd.DataFrame):
                cols_upper = {c.upper(): c for c in obj.columns}
                strike_col = None
                for key in ["STRIKE", "STRIKE_PRICE", "PERCENT_STRIKE", "K"]:
                    if key in cols_upper:
                        strike_col = cols_upper[key]
                        break
                if strike_col is not None:
                    strikes = np.sort(pd.to_numeric(obj[strike_col], errors="coerce").dropna().unique())
                    strikes = strikes[(strikes >= spot * moneyness[0]) & (strikes <= spot * moneyness[1])]
                    if len(strikes) >= 2:
                        return strikes

            if isinstance(obj, (list, tuple, np.ndarray)):
                numeric_values = []
                for x in obj:
                    if isinstance(x, (int, float, np.integer, np.floating)):
                        numeric_values.append(float(x))
                    elif isinstance(x, dict):
                        for key in ["Strike", "STRIKE", "strike"]:
                            if key in x:
                                try:
                                    numeric_values.append(float(x[key]))
                                except Exception:
                                    pass
                if numeric_values:
                    strikes = np.sort(np.unique(np.array(numeric_values, dtype=float)))
                    strikes = strikes[(strikes >= spot * moneyness[0]) & (strikes <= spot * moneyness[1])]
                    if len(strikes) >= 2:
                        return strikes
        ############################################################
        # END CHANGED BLOCK: defensive CMDB lookup for historical strikes
        ############################################################

    except Exception as exc:
        print(f"Warning: CMDB strike lookup attempt failed for {ticker} on {valuation_date}: {exc}")

    # Fallback for continuity until the exact CMDB historical option-chain query is wired in.
    print(
        f"Warning: falling back to Bloomberg historical chain for {ticker} on {valuation_date}. "
        f"Replace get_cmdb_strikes() with the desk's canonical CMDB option-chain lookup."
    )
    return get_bbg_strikes(ticker, expiry_date, valuation_date, moneyness)


def get_market_strikes(
    ticker: str,
    expiry_date: datetime.date,
    valuation_date: datetime.date,
    moneyness: tuple = (0.1, 2.0)
) -> np.ndarray:
    if valuation_date == datetime.date.today():
        return get_bbg_strikes(ticker, expiry_date, valuation_date, moneyness)
    return get_cmdb_strikes(ticker, expiry_date, valuation_date, moneyness)


def calculate_strip_weights(strikes: np.ndarray, k_power: float = 0.0) -> np.ndarray:
    strikes = np.asarray(sorted(np.unique(strikes)), dtype=float)
    if len(strikes) < 2:
        raise ValueError("Need at least two strikes to build a strip.")

    dK = np.zeros_like(strikes)
    dK[0] = strikes[1] - strikes[0]
    dK[-1] = strikes[-1] - strikes[-2]
    dK[1:-1] = 0.5 * (strikes[2:] - strikes[:-2])

    # Base strip is 1 / K^2, and k_power tilts the discrete strip to K^(k_power - 2).
    return dK * np.power(strikes, k_power - 2.0)


def validate_delta_band(delta_band, name: str):
    if delta_band is None:
        return None
    lo, hi = float(delta_band[0]), float(delta_band[1])
    if not (0.0 < lo <= hi < 1.0):
        raise ValueError(f"{name} must satisfy 0 < low <= high < 1.")
    return (lo, hi)


def get_option_delta(vanilla_context, strike: float, spot: float, payoff: str) -> float:
    payoffRule = "{Product.{Payoff=x}}"
    percentStrikeRule = "{Product.{PercentStrike=x}}"
    spotRule = "{AssetData.{Price=x}}"

    ctx = pymfl.MflData().SetProperty(
        pymfl.MflData().SetProperty(
            pymfl.MflData().SetProperty(vanilla_context, payoffRule, payoff),
            percentStrikeRule,
            strike / spot
        ),
        spotRule,
        spot
    )
    val = pymfl.Equities().Valuation(ctx)
    return val.Delta[0].Item2


def filter_strikes_by_delta(
    strikes: np.ndarray,
    vanilla_context,
    spot: float,
    fwd: float,
    put_delta=None,
    call_delta=None
) -> np.ndarray:
    if put_delta is None and call_delta is None:
        return strikes

    selected = []
    for k in strikes:
        if k < fwd:
            # Interpret put deltas in absolute-value convention:
            # e.g. --put_delta 0.10 0.50 means raw model delta in [-0.50, -0.10].
            if put_delta is None:
                selected.append(k)
            else:
                d = get_option_delta(vanilla_context, k, spot, "Put")
                if put_delta[0] <= abs(d) <= put_delta[1]:
                    selected.append(k)
        else:
            if call_delta is None:
                selected.append(k)
            else:
                d = get_option_delta(vanilla_context, k, spot, "Call")
                if call_delta[0] <= d <= call_delta[1]:
                    selected.append(k)

    selected = np.asarray(sorted(np.unique(selected)), dtype=float)
    if len(selected) < 2:
        raise ValueError("Not enough strikes remain after delta filtering.")
    return selected

############################################################
# END CHANGED BLOCK: strike-universe helpers
############################################################


def run_variance_swap_hedge(
    underlyings,
    valuation_date=None,
    expiry_date=None,
    vega_notional=100000.0,
    swap_type="Volatility",
    outputfolder=".",
    generate_wex=False,
    risks=None,
    k_power=0.0,
    alpha=0.00001,
    moneyness=(0.1, 2.0),
    plot=False,
    put_delta=None,
    call_delta=None
):
    '''
    Evaluates a variance or volatility swap and computes a linearly regularized vanilla strip hedge.
    Supports flexible constraints over option strip power, chosen regression risks, and strike moneyness limits.
    Optionally outputs matplotlib visualizations via the `plot` parameter.
    '''
    if valuation_date is None:
        valuation_date = datetime.date.today()
    if risks is None:
        risks = ['theta', 'gamma']

    put_delta = validate_delta_band(put_delta, "put_delta")
    call_delta = validate_delta_band(call_delta, "call_delta")

    os.makedirs(outputfolder, exist_ok=True)

    for thisu in underlyings:
        print(f"\n" + "=" * 50)
        print(f"Processing Underlying: {thisu}")
        print(f"Swap Type: {swap_type} | Vega Notional: {vega_notional}")
        print(f"Risks used: {risks} | Strip Power (k_power): {k_power}")
        print(f"Lasso Alpha: {alpha} | Moneyness Range: {moneyness}")
        print(f"Put Delta Filter: {put_delta} | Call Delta Filter: {call_delta}")
        print("=" * 50)

        vanilla, volswap = generate_contexts(
            ticker=thisu,
            valuation_date=valuation_date,
            expiry_date=expiry_date,
            vega_notional=vega_notional,
            swap_type=swap_type
        )

        payoffRule = "{Product.{Payoff=x}}"
        percentStrikeRule = "{Product.{PercentStrike=x}}"
        spotRule = "{AssetData.{Price=x}}"
        fixingRule = "{Product.{Schedule[0].{Fixing=x}}}"

        spot = volswap.AssetData.Price
        vanilla = pymfl.MflData().SetProperty(
            pymfl.MflData().SetProperty(
                pymfl.MflData().SetProperty(vanilla, "{ModelParameters.{PricingMethod=x}}", "Analytic"),
                "{Product.{ExerciseType=x}}",
                "European"
            ),
            "{ModelParameters.{SkewStickinessRatio=x}}",
            1
        )
        volswap = pymfl.MflData().SetProperty(
            pymfl.MflData().SetProperty(volswap, "{ModelParameters.{SkewStickinessRatio=x}}", 1),
            "{ModelParameters.{ConvexityStickinessRatio=x}}",
            1
        )

        div = volswap.AssetData.Dividend
        vd = volswap.ValueDate
        forecast = pymfl.Equities().ContextGetCcyForecastsBase(volswap)[0][0]
        expiry = list(volswap.Product.Schedule)[-1].Date
        fwd = pymfl.Dividend().ForwardPrice(div, forecast, expiry, vd, spot)

        # NOTE: slide grid remains a modeling choice for hedge fitting, not strike sourcing.
        # This was preserved intentionally.
        slides = [spot * (1.0 + 0.01 * x) for x in range(-20, 21)]

        ############################################################
        # BEGIN CHANGED BLOCK: use actual listed strikes instead of synthetic quadrature strikes
        ############################################################
        fullStrikes = get_market_strikes(
            ticker=thisu,
            expiry_date=expiry_date,
            valuation_date=valuation_date,
            moneyness=moneyness
        )

        fullStrikes = filter_strikes_by_delta(
            strikes=fullStrikes,
            vanilla_context=vanilla,
            spot=spot,
            fwd=fwd,
            put_delta=put_delta,
            call_delta=call_delta
        )

        strip_weights = calculate_strip_weights(fullStrikes, k_power=k_power)
        ############################################################
        # END CHANGED BLOCK: use actual listed strikes instead of synthetic quadrature strikes
        ############################################################

        t = (len(volswap.Product.Schedule) - 1) / 252.0
        v = volswap.Product.VarianceUnits

        nslides = len(slides)
        nstrikes = len(fullStrikes)

        deltaX = np.zeros((nslides, nstrikes))
        deltaY = np.zeros(nslides)
        gammaX = np.zeros((nslides, nstrikes))
        gammaY = np.zeros(nslides)
        vegaX = np.zeros((nslides, nstrikes))
        vegaY = np.zeros(nslides)
        thetaX = np.zeros((nslides, nstrikes))
        thetaY = np.zeros(nslides)
        pvX = np.zeros((nslides, nstrikes))
        pvY = np.zeros(nslides)

        print("Start clustering...")
        st = time.time()
        outputs = pymfl.MflArray.Map(
            pymfl.MflArray([
                pymfl.MflData().SetProperty(
                    pymfl.MflData().SetProperty(volswap, spotRule, x),
                    fixingRule,
                    x
                ) for x in slides
            ]),
            "=Equities.Valuation(,x)",
            pymfl.BasicTools().RunCluster("MDN")
        )

        vanillaoutputs = pymfl.MflArray.Map(
            pymfl.MflArray([
                pymfl.MflData().SetProperty(
                    pymfl.MflData().SetProperty(
                        pymfl.MflData().SetProperty(vanilla, payoffRule, "Put" if k < fwd else "Call"),
                        percentStrikeRule,
                        k / spot
                    ),
                    spotRule,
                    sd
                )
                for sd in slides
                for k in fullStrikes
            ]),
            "=Equities.Valuation(,x)",
            pymfl.BasicTools().RunCluster("MDN")
        )
        print('Execution time:', time.time() - st, 'seconds')

        ############################################################
        # BEGIN CHANGED BLOCK: discrete market-strip sizing
        ############################################################
        volScalar = 10000.0 if translate(volswap.Product.PayoffType) == 0 else 100.0
        positions = (volScalar * v / t) * strip_weights
        ############################################################
        # END CHANGED BLOCK: discrete market-strip sizing
        ############################################################

        for i in range(nslides):
            swapVal = outputs[i]
            gammaY[i] = swapVal.Gamma[0].Value(0, 0) * slides[i] * slides[i] / 100.0
            thetaY[i] = swapVal.Theta
            vegaY[i] = swapVal.Vega[0][0].Item2
            deltaY[i] = swapVal.Delta[0].Item2 * slides[i]
            pvY[i] = swapVal.Pv

            for j in range(nstrikes):
                vanillaVal = vanillaoutputs[i * nstrikes + j]

                gammaX[i, j] = positions[j] * vanillaVal.Gamma[0].Value(0, 0) * slides[i] * slides[i] / 100.0
                thetaX[i, j] = positions[j] * vanillaVal.Theta
                vegaX[i, j] = positions[j] * vanillaVal.Vega[0][0].Item2
                deltaX[i, j] = positions[j] * vanillaVal.Delta[0].Item2 * slides[i]
                pvX[i, j] = positions[j] * vanillaVal.Pv

        risk_Y_dict = {'delta': deltaY, 'gamma': gammaY, 'vega': vegaY, 'theta': thetaY, 'pv': pvY}
        risk_X_dict = {'delta': deltaX, 'gamma': gammaX, 'vega': vegaX, 'theta': thetaX, 'pv': pvX}

        y_components = []
        x_components = []

        for risk in risks:
            r = risk.lower().strip()
            if r in risk_Y_dict:
                norm = np.mean(np.abs(risk_Y_dict[r]))
                if norm == 0:
                    norm = 1.0
                y_components.append(risk_Y_dict[r] / norm)
                x_components.append(risk_X_dict[r] / norm)
            else:
                print(f"Warning: Risk '{risk}' is not valid and will be skipped.")

        if not y_components:
            raise ValueError("No valid risks provided for linear regression.")

        yvalue = np.concatenate(y_components)
        xvalue = np.concatenate(x_components, axis=0)

        clf = linear_model.Lasso(alpha=alpha, positive=True, fit_intercept=False)
        clf.fit(xvalue, yvalue)
        extraw = clf.coef_

        option_types = ["Put" if k < fwd else "Call" for k in fullStrikes]
        final_hedge_quantity = positions * extraw

        df_hedge = pd.DataFrame({
            "Underlying": thisu,
            "Strike": fullStrikes,
            "Option_Type": option_types,
            "Theoretical_Weight": positions,
            "Lasso_Multiplier": extraw,
            "Final_Trade_Quantity": final_hedge_quantity
        })

        csv_path = os.path.join(outputfolder, f"{thisu}_hedge.csv")
        df_hedge.to_csv(csv_path, index=False)
        print(f"\n--> Regression Completed! Lasso selected {sum(extraw > 1e-6)} active quantities.")
        print(f"Saved hedge blotter to: {csv_path}")
        print(df_hedge[df_hedge['Final_Trade_Quantity'] > 0].to_string(index=False))

        if generate_wex:
            wex_path = os.path.join(outputfolder, f"{thisu}_wex.csv")
            generate_wex_spreadsheet(df_hedge, expiry_date, wex_path)
            print(f"Saved WeX spreadsheet to: {wex_path}")

        if plot:
            try:
                import matplotlib.pyplot as plt
                fig = plt.figure(figsize=(12, 10))

                plt.subplot(3, 2, 1)
                plt.plot(slides, deltaY, label="volswap")
                plt.plot(slides, np.matmul(deltaX, extraw), label="vanilla")
                plt.legend(loc="lower right", fontsize=8)
                plt.title("Delta", fontsize=10)

                plt.subplot(3, 2, 2)
                plt.plot(slides, gammaY, label="volswap")
                plt.plot(slides, np.matmul(gammaX, extraw), label="vanilla")
                plt.title("Gamma", fontsize=10)

                plt.subplot(3, 2, 3)
                plt.plot(slides, vegaY, label="volswap")
                plt.plot(slides, np.matmul(vegaX, extraw), label="vanilla")
                plt.title("Vega", fontsize=10)

                plt.subplot(3, 2, 4)
                plt.plot(slides, thetaY, label="volswap")
                plt.plot(slides, np.matmul(thetaX, extraw), label="vanilla")
                plt.title("Theta", fontsize=10)

                plt.subplot(3, 2, 5)
                try:
                    vstrike = volswap.Product.VolatilityStrike
                except Exception:
                    vstrike = 0.0
                plt.plot(slides, pvY + v * vstrike, label="volswap")
                plt.plot(slides, np.matmul(pvX, extraw), label="vanilla")
                plt.title("Pv", fontsize=10)

                plt.subplot(3, 2, 6)
                plt.plot(fullStrikes, final_hedge_quantity, ".")
                plt.title("Positions", fontsize=10)

                plt.tight_layout()
                plot_path = os.path.join(outputfolder, f"{thisu}_risk_profile.png")
                plt.savefig(plot_path, bbox_inches='tight')
                print(f"Saved risk profile plots to: {plot_path}")
                plt.show()
                plt.close(fig)
            except ImportError:
                print("matplotlib not found, skipping plot generation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Variance Swap Hedge & WeX Trade Generator")
    parser.add_argument("--ticker", nargs="+", help="Underlying tickers (e.g. AAPL-UQ SPX)")
    parser.add_argument("--valuation_date", type=str, help="Valuation date in YYYY-MM-DD")
    parser.add_argument("--expiry_date", type=str, help="Expiry date in YYYY-MM-DD")
    parser.add_argument("--vega", type=float, default=100000.0, help="Vega Notional")
    parser.add_argument("--swap_type", type=str, default="Volatility", help="Payoff Type")
    parser.add_argument("--out_folder", type=str, default=".", help="Output directory")
    parser.add_argument("--csv", type=str, help="Path to a CSV file for batch processing. Columns required: ticker, valuation_date, expiry_date, vega_notional, swap_type")
    parser.add_argument("-s", action="store_true", help="Generate downstream WeX spreadsheet automatically")
    parser.add_argument("--risks", nargs="+", default=["theta", "gamma"], help="Risks for regression (e.g., theta gamma vega delta pv)")
    parser.add_argument("--k_power", type=float, default=0.0, help="Strip K power multiplier ('0' for 1/K^2 base, '1' for 1/K base, etc.)")
    parser.add_argument("--alpha", type=float, default=0.00001, help="Regularization factor alpha for Lasso regression")
    parser.add_argument("--moneyness", nargs=2, type=float, default=[0.1, 2.0], help="Moneyness range for strikes (e.g. 0.1 2.0)")
    parser.add_argument("--plot", action="store_true", help="Generate and save risk profile plots")

    ############################################################
    # BEGIN CHANGED BLOCK: delta-band strike filters
    ############################################################
    parser.add_argument(
        "--put_delta",
        nargs=2,
        type=float,
        metavar=("LOW", "HIGH"),
        help="Absolute put delta band. Example: --put_delta 0.10 0.50 keeps puts with |delta| in [0.10, 0.50]."
    )
    parser.add_argument(
        "--call_delta",
        nargs=2,
        type=float,
        metavar=("LOW", "HIGH"),
        help="Call delta band. Example: --call_delta 0.10 0.50 keeps calls with delta in [0.10, 0.50]."
    )
    ############################################################
    # END CHANGED BLOCK: delta-band strike filters
    ############################################################

    args = parser.parse_args()

    put_delta = validate_delta_band(args.put_delta, "--put_delta")
    call_delta = validate_delta_band(args.call_delta, "--call_delta")

    if args.csv:
        df_batch = pd.read_csv(args.csv)
        for _, row in df_batch.iterrows():
            v_date_raw = row.get('valuation_date')
            v_date = datetime.datetime.strptime(v_date_raw, "%Y-%m-%d").date() if pd.notna(v_date_raw) else datetime.date.today()
            e_date = datetime.datetime.strptime(row['expiry_date'], "%Y-%m-%d").date()
            run_variance_swap_hedge(
                underlyings=[row['ticker']],
                valuation_date=v_date,
                expiry_date=e_date,
                vega_notional=float(row['vega_notional']),
                swap_type=row['swap_type'],
                outputfolder=args.out_folder,
                generate_wex=args.s,
                risks=args.risks,
                k_power=args.k_power,
                alpha=args.alpha,
                moneyness=tuple(args.moneyness),
                plot=args.plot,
                put_delta=put_delta,
                call_delta=call_delta
            )
    elif args.ticker and args.expiry_date:
        v_date = datetime.datetime.strptime(args.valuation_date, "%Y-%m-%d").date() if args.valuation_date else datetime.date.today()
        e_date = datetime.datetime.strptime(args.expiry_date, "%Y-%m-%d").date()
        run_variance_swap_hedge(
            underlyings=args.ticker,
            valuation_date=v_date,
            expiry_date=e_date,
            vega_notional=args.vega,
            swap_type=args.swap_type,
            outputfolder=args.out_folder,
            generate_wex=args.s,
            risks=args.risks,
            k_power=args.k_power,
            alpha=args.alpha,
            moneyness=tuple(args.moneyness),
            plot=args.plot,
            put_delta=put_delta,
            call_delta=call_delta
        )
    else:
        print("Provide either --csv or --ticker and --expiry_date flags")
