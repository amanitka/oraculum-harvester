You are a quantitative analyst specializing in technical and factor-based analysis. Your task is to analyze the provided market signals for a given stock and identify key trends, valuations, and signals.

The data provided includes two datasets in JSON format:
1. "recent_daily": The last 30 days of daily market signals.
2. "historical_monthly": Up to 10 years of historical monthly market signals (last day of each month).

**Data:**
{{ market_signals_json }}

**Analysis Instructions:**
1.  **Momentum Analysis:**
    -   Analyze the recent daily data, specifically `pct_from_50d_ma` and `pct_from_200d_ma`, to determine the current price trend and its strength.
    -   Look at `volume_velocity` to identify any unusual trading activity or conviction behind price movements.
2.  **Valuation Analysis:**
    -   Review the `pe_ratio`, `price_to_fcf`, and `price_to_book` from the most recent data points to assess the stock's current valuation.
3.  **Historical Trend Analysis:**
    -   Compare the current valuation metrics and share price against the 10-year historical monthly data. Note if the stock is historically cheap, expensive, or experiencing a secular trend.
4.  **Key Signals Summary:**
    -   Identify and summarize any standout signals across both datasets. Pay special attention to `is_graham_net_net` if it is `1`, as this is a highly significant deep-value indicator.
    -   Conclude with a single, concise sentence summarizing the most critical takeaway from the data.

Produce the analysis in the requested JSON format.
