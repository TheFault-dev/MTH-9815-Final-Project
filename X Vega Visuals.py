from my_utilities import DataBase
import numpy as np

ivy = DataBase()

def fetch_hvol_ivy(tickstr, days1, sdate, edate):
    sqlStr = f"""
        SELECT s.ticker, v1.date, v1.volatility
        FROM security s
        JOIN historical_volatility v1 ON s.securityid = v1.securityid
        WHERE s.ticker IN ({tickstr})
          AND v1.date >= ? AND v1.date <= ?
          AND v1.days = ?
        ORDER BY s.ticker, v1.date
    """
    df = ivy.run("Ivy", sqlStr, params=(sdate, edate, days1))
    if df.empty:
        return pd.DataFrame()
    df['ticker'] = df['ticker'].str.strip()
    df.set_index('date', inplace=True)
    df = df.pivot_table(index=df.index, columns='ticker', values='volatility')
    df = df.ffill(limit=50).bfill(limit=250)
    return df

def fetch_atmf_implied_volatility_ivy(tickstr, days1, sdate, edate):
    sqlStr = f"""
        SELECT s.ticker, v1.date, v1.impliedvolatility, v1.callput
        FROM security s
        JOIN std_option_price v1 ON s.securityid = v1.securityid
        WHERE s.ticker IN ({tickstr})
          AND v1.date >= ? AND v1.date <= ?
          AND v1.days = ?
        ORDER BY s.ticker, v1.date, v1.callput
    """
    df = ivy.run("Ivy", sqlStr, params=(sdate, edate, days1))
    if df.empty:
        return pd.DataFrame()
    df['ticker'] = df['ticker'].str.strip()
    df.set_index('date', inplace=True)
    df = df.pivot_table(index=df.index, columns=['ticker', 'callput'], values='impliedvolatility')
    df = df.mask(df.round() == -100, np.nan)
    df = df.T.groupby(level=0).mean().T
    df = df.ffill(limit=50).bfill(limit=250)
    return df

portfolio_df = pd.read_csv("portfolio.csv")
total_vega = portfolio_df["vega"].sum()
vega_delta = (portfolio_df["delta"] * portfolio_df["vega"]).sum() / total_vega
print(f"Portfolio Vega Delta: {vega_delta:.4f}")

portfolio_df["weight"] = portfolio_df["vega"] / total_vega
new_w_star = portfolio_df.set_index("ticker")["weight"]
new_list = list(new_w_star.index)

cap_param = None
df_reco_sectors = pd.DataFrame(columns=["Sector", "SPX", "Basket", "Spread"])

df_notional = pd.DataFrame({"Ticker": ["SPX"] + list(new_w_star.sort_values(ascending=False).index)})
df_notional = df_notional.set_index("Ticker")
df_notional["Weight"] = df_notional.index.map(new_w_star).fillna("")
df_notional.loc["SPX", "Weight"] = -1
df_notional["Sector"] = ""
df_notional["Name"] = ""
df_notional["Skew Delta"] = ""
df_notional["Ticker"] = df_notional.index
df_notional = df_notional[["Ticker", "Weight", "Sector", "Name", "Skew Delta"]]

print("Chart ...")

df_metrics_final1 = pd.DataFrame()
new_basket_str = ', '.join(f"'{ticker}'" for ticker in new_list)

window_perc_RV_date1 = (ref_date - relativedelta(years=window_perc_RV)).strftime("%Y-%m-%d")
window_perc_IV_date1 = (ref_date - relativedelta(years=window_perc_IV)).strftime("%Y-%m-%d")
start_date_str = (ref_date - relativedelta(years=total_hist_window_chart)).strftime("%Y-%m-%d")
end_date_str = ref_date.strftime("%Y-%m-%d")

index_rvol_new = fetch_hvol_ivy(index_str, tenor_curr_RV, start_date_str, end_date_str).squeeze()
basket_rvol_new = fetch_hvol_ivy(new_basket_str, tenor_curr_RV, start_date_str, end_date_str)
weighted_basket_rvol_new = rebase_vol(basket_rvol_new, new_w_star)

percentile_index_rvol_new = fetch_hvol_ivy(index_str, tenor_curr_RV, window_perc_RV_date1, end_date_str).squeeze()
percentile_basket_rvol_new = fetch_hvol_ivy(new_basket_str, tenor_curr_RV, window_perc_RV_date1, end_date_str)
weighted_percentile_basket_rvol_new = rebase_vol(percentile_basket_rvol_new, new_w_star)

df_metrics_final1[f"{tenor_curr_RV_str} RV Spread"] = weighted_basket_rvol_new - index_rvol_new
df_metrics_final1[f"{tenor_curr_RV_str} RV Spread ({int(percentile*100)}th percentile, {window_perc_RV_str}Y window)"] = (weighted_percentile_basket_rvol_new - percentile_index_rvol_new).quantile(percentile)

index_rvol_new_iv_bench = fetch_hvol_ivy(index_str, IV_maturity, start_date_str, end_date_str).squeeze()
basket_rvol_new_iv_bench = fetch_hvol_ivy(new_basket_str, IV_maturity, start_date_str, end_date_str)
weighted_basket_rvol_new_iv_bench = rebase_vol(basket_rvol_new_iv_bench, new_w_star, cap_param)

percentile_index_rvol_new_iv_bench = fetch_hvol_ivy(index_str, IV_maturity, window_perc_RV_date1, end_date_str).squeeze()
percentile_basket_rvol_new_iv_bench = fetch_hvol_ivy(new_basket_str, IV_maturity, window_perc_RV_date1, end_date_str)
weighted_percentile_basket_rvol_new_iv_bench = rebase_vol(percentile_basket_rvol_new_iv_bench, new_w_star, cap_param)

df_metrics_final1[f"{IV_maturity_str} RV Spread"] = weighted_basket_rvol_new_iv_bench - index_rvol_new_iv_bench
df_metrics_final1[f"{IV_maturity_str} RV Spread ({int(percentile*100)}th percentile, {window_perc_RV_str}Y window)"] = (weighted_percentile_basket_rvol_new_iv_bench - percentile_index_rvol_new_iv_bench).quantile(percentile)

current_index_ivol_new = fetch_atmf_implied_volatility_ivy(index_str, IV_maturity, start_date_str, end_date_str).squeeze()
current_basket_ivol_new = fetch_atmf_implied_volatility_ivy(new_basket_str, IV_maturity, start_date_str, end_date_str)
weighted_current_basket_ivol_new = rebase_vol(current_basket_ivol_new, new_w_star)

percentile_index_ivol_new = fetch_atmf_implied_volatility_ivy(index_str, IV_maturity, window_perc_IV_date1, end_date_str).squeeze()
percentile_basket_ivol_new = fetch_atmf_implied_volatility_ivy(new_basket_str, IV_maturity, window_perc_IV_date1, end_date_str)
weighted_percentile_basket_ivol_new = rebase_vol(percentile_basket_ivol_new, new_w_star)

df_metrics_final1[f"{IV_maturity_str} IV Spread"] = weighted_current_basket_ivol_new - current_index_ivol_new
df_metrics_final1[f"Current {IV_maturity_str} IV Spread"] = df_metrics_final1[f"{IV_maturity_str} IV Spread"].iloc[-1]
df_metrics_final1[f"{IV_maturity_str} IV Spread ({int(percentile*100)}th percentile, {window_perc_IV_str}Y window)"] = (weighted_percentile_basket_ivol_new - percentile_index_ivol_new).quantile(percentile)

plot_columns = [
    f"{tenor_curr_RV_str} RV Spread",
    f"{tenor_curr_RV_str} RV Spread ({int(percentile*100)}th percentile, {window_perc_RV_str}Y window)",
    f"{IV_maturity_str} RV Spread",
    f"{IV_maturity_str} RV Spread ({int(percentile*100)}th percentile, {window_perc_RV_str}Y window)",
    f"{IV_maturity_str} IV Spread",
    f"Current {IV_maturity_str} IV Spread",
    f"{IV_maturity_str} IV Spread ({int(percentile*100)}th percentile, {window_perc_IV_str}Y window)"
]

colors = ['#1f77b4', '#aec7e8',  "#45963c",  "#779C73", '#ff7f0e', 'black', '#ffbb78']

if "3M" not in [tenor_curr_RV_str, IV_maturity_str]:
    index_rvol_new3m = fetch_hvol_ivy(index_str, 91, start_date_str, end_date_str).squeeze()
    basket_rvol_new3m = fetch_hvol_ivy(new_basket_str, 91, start_date_str, end_date_str)
    weighted_basket_rvol_new3m = rebase_vol(basket_rvol_new3m, new_w_star)
    df_metrics_final1["3M RV Spread"] = weighted_basket_rvol_new3m - index_rvol_new3m
    plot_columns += ["3M RV Spread"]
    colors += ["#777D80"]

df_metrics_final1 = df_metrics_final1.ffill(limit=3)

df_metrics_final2 = pd.DataFrame()
df_metrics_final2[f"{IV_maturity_str} RV Spread"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"]
df_metrics_final2[f"{IV_maturity_str} IV Spread"] = df_metrics_final1[f"{IV_maturity_str} IV Spread"]
df_metrics_final2[f"Current {IV_maturity_str} IV Spread"] = df_metrics_final1[f"Current {IV_maturity_str} IV Spread"]

plot_columns2 = [
    f"{IV_maturity_str} RV Spread",
    f"{IV_maturity_str} IV Spread",
    f"Current {IV_maturity_str} IV Spread"
]

colors2 = ["#45963c", "#ff7f0e", "black"]

# Adding single name contribution calculations
df_contrib_iv = current_basket_ivol_new.mul(new_w_star, axis=1)
df_contrib_rv = basket_rvol_new_iv_bench.mul(new_w_star, axis=1)

contrib_plot_columns_iv = list(df_contrib_iv.columns)
contrib_plot_columns_rv = list(df_contrib_rv.columns)
contrib_colors = ['#%06X' % np.random.randint(0, 0xFFFFFF) for _ in range(len(new_list))]

current_IV_spread = df_metrics_final2[f"Current {IV_maturity_str} IV Spread"].iloc[0].item()
rows = ['Last 6M', 'Last 1Y', 'Last 3Y', 'Last 5Y']
cols = [f'25th Perc. {tenor_curr_RV_str}', f'50th Perc. {tenor_curr_RV_str}', f'75th Perc. {tenor_curr_RV_str}', f"25th Perc. {IV_maturity_str}", f"50th Perc. {IV_maturity_str}", f"75th Perc. {IV_maturity_str}"]
summary_df = pd.DataFrame(index=rows, columns=cols)
summary_df.loc['Last 6M', f'25th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-int(252*0.5):].quantile(0.25) - current_IV_spread
summary_df.loc['Last 6M', f'50th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-int(252*0.5):].quantile(0.50) - current_IV_spread
summary_df.loc['Last 6M', f'75th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-int(252*0.5):].quantile(0.75) - current_IV_spread
summary_df.loc['Last 6M', f"25th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-int(252*0.5):].quantile(0.25) - current_IV_spread
summary_df.loc['Last 6M', f"50th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-int(252*0.5):].quantile(0.5) - current_IV_spread
summary_df.loc['Last 6M', f"75th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-int(252*0.5):].quantile(0.75) - current_IV_spread
summary_df.loc['Last 1Y', f'25th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252:].quantile(0.25) - current_IV_spread
summary_df.loc['Last 1Y', f'50th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252:].quantile(0.50) - current_IV_spread
summary_df.loc['Last 1Y', f'75th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252:].quantile(0.75) - current_IV_spread
summary_df.loc['Last 1Y', f"25th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252:].quantile(0.25) - current_IV_spread
summary_df.loc['Last 1Y', f"50th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252:].quantile(0.5) - current_IV_spread
summary_df.loc['Last 1Y', f"75th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252:].quantile(0.75) - current_IV_spread
summary_df.loc['Last 3Y', f'25th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252*3:].quantile(0.25) - current_IV_spread
summary_df.loc['Last 3Y', f'50th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252*3:].quantile(0.50) - current_IV_spread
summary_df.loc['Last 3Y', f'75th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252*3:].quantile(0.75) - current_IV_spread
summary_df.loc['Last 3Y', f"25th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252*3:].quantile(0.25) - current_IV_spread
summary_df.loc['Last 3Y', f"50th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252*3:].quantile(0.5) - current_IV_spread
summary_df.loc['Last 3Y', f"75th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252*3:].quantile(0.75) - current_IV_spread
summary_df.loc['Last 5Y', f'25th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252*5:].quantile(0.25) - current_IV_spread
summary_df.loc['Last 5Y', f'50th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252*5:].quantile(0.50) - current_IV_spread
summary_df.loc['Last 5Y', f'75th Perc. {tenor_curr_RV_str}'] = df_metrics_final1[f'{tenor_curr_RV_str} RV Spread'].iloc[-252*5:].quantile(0.75) - current_IV_spread
summary_df.loc['Last 5Y', f"25th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252*5:].quantile(0.25) - current_IV_spread
summary_df.loc['Last 5Y', f"50th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252*5:].quantile(0.5) - current_IV_spread
summary_df.loc['Last 5Y', f"75th Perc. {IV_maturity_str}"] = df_metrics_final1[f"{IV_maturity_str} RV Spread"].iloc[-252*5:].quantile(0.75) - current_IV_spread
summary_df = summary_df.loc[:,~summary_df.columns.duplicated()]

print("Email ...")

path_plot = create_matplotlib_plot(df_metrics_final1, EXPORT_PATH, ref_date_str, plot_columns, colors, "Global Vol spreads")
path_plot2 = create_matplotlib_plot(df_metrics_final2, EXPORT_PATH, ref_date_str, plot_columns2, colors2, f"{IV_maturity_str} Vol spreads")

# Utilizing your proprietary function for single name component charts
path_plot_contrib_iv = create_matplotlib_plot(df_contrib_iv, EXPORT_PATH, ref_date_str, contrib_plot_columns_iv, contrib_colors, f"{IV_maturity_str} IV Contributions")
path_plot_contrib_rv = create_matplotlib_plot(df_contrib_rv, EXPORT_PATH, ref_date_str, contrib_plot_columns_rv, contrib_colors, f"{IV_maturity_str} RV Contributions")

path_excel = create_excel_with_multiple_tables(df_notional, df_reco_sectors, summary_df, df_metrics_final1, EXPORT_PATH, ref_date_str)

checks = {}
checks.update(params) 
path_checks = write_checks_to_txt(checks, EXPORT_PATH, ref_date_str)

# The new single name plot paths have been added below. You may need to augment your proprietary `send_report_via_outlook` function to accommodate these.
send_report_via_outlook(
    current_IV_spread=current_IV_spread,
    current_IV_spread_mat=IV_maturity_str,
    df1=df_notional,
    df2=df_reco_sectors,
    df3=summary_df,
    plot_path=path_plot,
    plot_path2=path_plot2,
    plot_path_contrib_iv=path_plot_contrib_iv,
    plot_path_contrib_rv=path_plot_contrib_rv,
    excel_path=path_excel,
    checks_txt_path=path_checks,
    to_recipients=recipients,
    subject=f"Dispersion Analytics automated email - {ref_datemmyy}",
)


