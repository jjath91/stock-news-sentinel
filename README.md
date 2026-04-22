# Stock News Sentinel: Get Ahead of the Market

A Streamlit dashboard that combines **real-time news monitoring**, **sentiment analysis**, **Google Trends (alternative data)**, and **stock price signals** to help you detect potential big moves *before* they fully hit the mainstream market.

## Why This Helps You Get Ahead

Traditional investors react to news. This tool lets you:
- **Monitor news sentiment in real-time** (using Finnhub/Alpha Vantage APIs with built-in or local NLP sentiment).
- **Track leading indicators** like search volume spikes via Google Trends (often leads earnings/sales by 1-4 weeks per research).
- **Detect anomalies**: Sudden sentiment shifts, viral search trends, or unusual price/volume action.
- **Combine signals**: Multiple confirming signals (e.g. positive news sentiment + rising search volume) are strong alpha indicators (as per hedge fund practices).
- **Set up alerts** for your watchlist of tickers.

Based on 2026 best practices from alternative data research: behavioral signals (search, sentiment, social) provide leading edges over traditional filings and earnings.

## Features

- **Live News Feed**: Filtered by tickers, with AI-driven sentiment scores, relevance, and full context.
- **Alternative Data Dashboard**: Google Trends heatmaps and spike detection.
- **Potential Movers**: Ranked list based on composite scores (sentiment velocity + trend momentum + price action).
- **Watchlist Management**: Add/remove tickers (e.g. NVDA, TSLA, AAPL).
- **Visualizations**: Sentiment over time, search volume charts, price correlation.
- **Alert System**: Configurable thresholds for "high conviction" signals.

## Quick Start

1. Get free API keys:
   - [Finnhub](https://finnhub.io/register) (recommended for news + sentiment, generous free tier)
   - Optional: Alpha Vantage

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add your keys:
   ```
   FINNHUB_API_KEY=your_key_here
   ```

4. Run the app:
   ```bash
   streamlit run app.py
   ```

5. Add your watchlist tickers and monitor the "Potential Big Movers" section.

## Tech Stack

- **Streamlit**: Modern, interactive UI
- **Finnhub**: Real-time news, company news, sentiment
- **pytrends**: Google Trends for search volume (leading indicator)
- **yfinance**: Stock prices, volume for confirmation
- **VADER Sentiment**: Fast, finance-tuned NLP (or upgrade to transformers)
- **Pandas/Plotly**: Analysis and beautiful charts

## How to Use for Alpha

1. **Setup Watchlist**: Focus on sectors prone to big news moves (tech, biotech, consumer).
2. **Scan for Spikes**: Look for news sentiment >0.7 or <-0.7 with high volume, combined with search trend acceleration.
3. **Cross-validate**: Use satellite/social ideas manually or extend the tool (e.g. add Twitter/X monitoring via API).
4. **Backtest**: The tool includes notes on combining signals; test historically before trading.
5. **Risk Management**: This is for informational/educational use. Alternative data has decay; always combine with fundamentals. No financial advice.

## Extending It

- Add WebSocket for true real-time (finlight.me or Finnhub WS).
- Integrate more alt data (credit card via vendors, satellite via paid APIs).
- Add ML model for composite scoring/prediction.
- Deploy to cloud with scheduled alerts (email/Slack via Streamlit sharing or separate script).
- MCP integration for advanced agents.

## Research References
- Alternative Data for Hedge Funds (Paradox Intelligence, 2026)
- Sentiment + Search as leading indicators (1-4 week horizon)
- News sentiment combined with behavioral data outperforms single signals

**Disclaimer**: Trading involves risk. Past performance (including backtested signals) is not indicative of future results. Use at your own risk. This tool is for research and education.

---

Built with Cursor AI to help retail investors level the playing field against institutions using alternative data.
