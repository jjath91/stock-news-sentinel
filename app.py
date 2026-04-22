import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pytrends.request import TrendReq
import os
from dotenv import load_dotenv
import json
from typing import List, Dict, Any
import time

# Load environment variables
load_dotenv()

# Initialize VADER sentiment analyzer (finance-tuned)
analyzer = SentimentIntensityAnalyzer()

# Finnhub API setup
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "demo")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")

# API Status helper
def get_api_status():
    if FINNHUB_API_KEY and FINNHUB_API_KEY != "demo":
        return "✅ Finnhub Connected", True
    elif ALPHA_VANTAGE_API_KEY and ALPHA_VANTAGE_API_KEY != "demo":
        return "⚠️ Using Alpha Vantage fallback (limited)", True
    else:
        return "❌ No valid API key - using demo mode (very limited data)", False

# Default watchlist
DEFAULT_WATCHLIST = ["NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "META"]

def load_watchlist() -> List[str]:
    """Load watchlist from env or session state."""
    if "watchlist" not in st.session_state:
        watchlist_str = os.getenv("WATCHLIST", ",".join(DEFAULT_WATCHLIST))
        st.session_state.watchlist = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    return st.session_state.watchlist

def save_watchlist(watchlist: List[str]):
    """Save watchlist to session state."""
    st.session_state.watchlist = [t.upper() for t in watchlist]
    # Note: In production, persist to file or DB

def get_finnhub_news(tickers: List[str], days_back: int = 7, limit: int = 20) -> pd.DataFrame:
    """Fetch recent company news from Finnhub with fallback to Alpha Vantage."""
    all_news = []
    errors = []

    # Try Finnhub first (preferred - more complete articles)
    if FINNHUB_API_KEY and FINNHUB_API_KEY != "demo":
        for ticker in tickers[:5]:  # Limit concurrent calls
            try:
                from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={datetime.now().strftime('%Y-%m-%d')}&token={FINNHUB_API_KEY}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    news = response.json()
                    for item in news[:limit//len(tickers) + 2]:
                        if isinstance(item, dict) and item.get("headline"):
                            item["ticker"] = ticker
                            item["source_api"] = "finnhub"
                            # Compute sentiment
                            text = item.get("headline", "") + " " + item.get("summary", "")
                            scores = analyzer.polarity_scores(text)
                            item["compound"] = scores["compound"]
                            item["sentiment_label"] = ("positive" if scores["compound"] > 0.05 
                                                    else "negative" if scores["compound"] < -0.05 
                                                    else "neutral")
                            all_news.append(item)
                elif response.status_code == 403:
                    errors.append(f"Finnhub API key invalid (403)")
                else:
                    errors.append(f"Finnhub returned {response.status_code} for {ticker}")
            except Exception as e:
                errors.append(f"Finnhub error for {ticker}: {str(e)}")
                continue

    # Fallback to Alpha Vantage if no/limited Finnhub results
    if len(all_news) < 5 and ALPHA_VANTAGE_API_KEY and ALPHA_VANTAGE_API_KEY != "demo":
        try:
            tickers_str = ",".join(tickers[:5])
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={tickers_str}&apikey={ALPHA_VANTAGE_API_KEY}&limit=20"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                feed = data.get("feed", [])
                for item in feed:
                    if isinstance(item, dict):
                        # Alpha Vantage format is slightly different
                        news_item = {
                            "headline": item.get("title", ""),
                            "summary": item.get("summary", ""),
                            "url": item.get("url", ""),
                            "datetime": item.get("time_published", ""),
                            "ticker": item.get("ticker", tickers[0] if tickers else "UNKNOWN"),
                            "source_api": "alphavantage",
                            "compound": float(item.get("overall_sentiment_score", 0.5)),
                            "sentiment_label": item.get("overall_sentiment_label", "neutral").lower()
                        }
                        all_news.append(news_item)
        except Exception as e:
            errors.append(f"Alpha Vantage fallback failed: {str(e)}")

    df = pd.DataFrame(all_news)
    if not df.empty:
        # Normalize datetime column
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors='coerce')
            df = df.sort_values("datetime", ascending=False)
    
    # Store errors for display (using session state since this is cached)
    if errors and "news_errors" not in st.session_state:
        st.session_state.news_errors = errors[:3]  # limit noise
    
    return df

def get_google_trends(tickers: List[str], timeframe: str = "today 3-m") -> Dict:
    """Get Google Trends data for tickers/company names."""
    pytrends = TrendReq(hl='en-US', tz=360)
    trends_data = {}
    for ticker in tickers:
        try:
            # Use ticker + company name for better results
            keywords = [ticker, f"{ticker} stock", f"{ticker} news"]
            pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo='', gprop='')
            df = pytrends.interest_over_time()
            if not df.empty:
                trends_data[ticker] = {
                    "trend_df": df,
                    "avg_interest": int(df.mean().mean()),
                    "peak": int(df.max().max()),
                    "recent_change": float((df.iloc[-1].mean() - df.iloc[-5].mean()) / df.iloc[-5].mean() * 100) if len(df) > 5 else 0
                }
        except Exception as e:
            trends_data[ticker] = {"error": str(e)}
            continue
    return trends_data

def get_stock_data(tickers: List[str]) -> pd.DataFrame:
    """Fetch recent price and volume data."""
    data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            if not hist.empty:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest
                data.append({
                    "ticker": ticker,
                    "price": round(latest["Close"], 2),
                    "change_pct": round((latest["Close"] - prev["Close"]) / prev["Close"] * 100, 2),
                    "volume": int(latest["Volume"]),
                    "avg_volume_5d": int(hist["Volume"].mean()),
                    "volume_surge": round(latest["Volume"] / hist["Volume"].mean(), 2)
                })
        except:
            continue
    return pd.DataFrame(data)

def calculate_composite_score(news_df: pd.DataFrame, trends: Dict, stock_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate a composite 'mover potential' score from multiple signals."""
    scores = []
    watchlist = load_watchlist()
    
    for ticker in watchlist:
        score_components = {"sentiment": 0.0, "trend": 0.0, "volume": 0.0, "price_momentum": 0.0}
        
        # Sentiment from news
        ticker_news = news_df[news_df.get("ticker", "") == ticker] if not news_df.empty and "ticker" in news_df.columns else pd.DataFrame()
        if not ticker_news.empty and "compound" in ticker_news.columns:
            avg_sent = ticker_news["compound"].mean()
            score_components["sentiment"] = avg_sent * 50  # Scale -50 to 50
        
        # Google Trends momentum
        if ticker in trends and "recent_change" in trends[ticker]:
            trend_change = trends[ticker].get("recent_change", 0)
            score_components["trend"] = min(max(trend_change, -50), 50)  # Cap
        
        # Stock volume and price
        ticker_stock = stock_df[stock_df["ticker"] == ticker]
        if not ticker_stock.empty:
            vol_surge = ticker_stock.iloc[0].get("volume_surge", 1.0)
            score_components["volume"] = (vol_surge - 1) * 30
            price_chg = ticker_stock.iloc[0].get("change_pct", 0)
            score_components["price_momentum"] = price_chg * 2
        
        # Composite (weighted: sentiment 40%, trend 30%, volume 20%, momentum 10%)
        composite = (
            score_components["sentiment"] * 0.4 +
            score_components["trend"] * 0.3 +
            score_components["volume"] * 0.2 +
            score_components["price_momentum"] * 0.1
        )
        total_score = max(min(composite, 100), -100)  # Bound score
        
        scores.append({
            "ticker": ticker,
            "composite_score": round(total_score, 1),
            "sentiment": round(score_components["sentiment"], 1),
            "trend_momentum": round(score_components["trend"], 1),
            "volume_surge": round(ticker_stock.iloc[0]["volume_surge"], 2) if not ticker_stock.empty else 1.0,
            "price_change": round(ticker_stock.iloc[0]["change_pct"], 2) if not ticker_stock.empty else 0.0,
            "signal_strength": "HIGH" if total_score > 35 else "MEDIUM" if total_score > 10 else "LOW"
        })
    
    score_df = pd.DataFrame(scores)
    if not score_df.empty:
        score_df = score_df.sort_values("composite_score", ascending=False)
    return score_df

# ----------------------- STREAMLIT UI -----------------------
st.set_page_config(page_title="Stock News Sentinel", layout="wide", page_icon="📈")
st.title("📈 Stock News Sentinel")
st.markdown("**Get ahead of the market** with real-time news sentiment, Google Trends, and anomaly detection. Built to surface *leading signals* before the crowd reacts.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    status_text, has_key = get_api_status()
    st.info(status_text)
    
    if not has_key:
        st.warning("⚠️ Get a free Finnhub API key at https://finnhub.io/register and add it to your `.env` file as `FINNHUB_API_KEY=your_key`")
        st.caption("Without a real key, news data will be very limited.")
    
    st.subheader("Watchlist")
    current_watchlist = load_watchlist()
    new_tickers = st.text_input("Add tickers (comma separated)", value=",".join(current_watchlist))
    if st.button("Update Watchlist"):
        updated = [t.strip().upper() for t in new_tickers.split(",") if t.strip()]
        save_watchlist(updated)
        st.success("Watchlist updated!")
        st.rerun()
    
    st.subheader("Timeframes")
    news_days = st.slider("News lookback (days)", 1, 30, 7)
    trends_period = st.selectbox("Trends period", ["today 3-m", "today 1-y", "2024-01-01 2026-04-21"])
    
    if st.button("🔄 Refresh All Data", type="primary"):
        if "news_errors" in st.session_state:
            del st.session_state.news_errors  # Clear previous errors
        st.session_state.refresh = True
        st.rerun()

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["📰 Live News Feed", "📊 Google Trends & Alt Data", "🚀 Potential Big Movers", "🛎️ Alerts & Insights"])

watchlist = load_watchlist()

# Cache data where possible
@st.cache_data(ttl=180)  # Reduced TTL so changes to API key are picked up faster
def fetch_all_data(watchlist_tuple, news_days):
    news_df = get_finnhub_news(list(watchlist_tuple), days_back=news_days)
    trends = get_google_trends(list(watchlist_tuple))
    stock_df = get_stock_data(list(watchlist_tuple))
    movers = calculate_composite_score(news_df, trends, stock_df)
    return news_df, trends, stock_df, movers

news_df, trends_data, stock_df, movers_df = fetch_all_data(tuple(watchlist), news_days)

with tab1:
    st.header("Live News Feed with Sentiment")
    
    if news_df.empty:
        st.error("**No news found**")
        st.info("This usually means you are using the demo API key. Please get a free Finnhub key:")
        st.code("FINNHUB_API_KEY=your_key_here", language="bash")
        st.markdown("[Get Free Key →](https://finnhub.io/register)")
        
        if "news_errors" in st.session_state and st.session_state.news_errors:
            with st.expander("Debug Info"):
                for err in st.session_state.news_errors:
                    st.warning(err)
    else:
        st.success(f"Found **{len(news_df)}** recent articles")
        # Filter and display
        for _, row in news_df.head(15).iterrows():
            sentiment_color = "🟢" if row.get("compound", 0) > 0.1 else "🔴" if row.get("compound", 0) < -0.1 else "⚪"
            source = row.get("source_api", "news").upper()
            with st.expander(f"{sentiment_color} {row.get('headline', 'No headline')} ({row.get('ticker', '')}) [{source}]"):
                dt = row.get('datetime')
                st.caption(f"{dt.strftime('%Y-%m-%d %H:%M') if hasattr(dt, 'strftime') else str(dt)} | "
                          f"Sentiment: **{row.get('compound', 0):.2f}**")
                st.write(row.get("summary", "No summary available"))
                if "url" in row and row["url"]:
                    st.markdown(f"[Read full article]({row['url']})")
    
    st.subheader("News Sentiment Distribution")
    if not news_df.empty and "compound" in news_df.columns:
        fig = px.histogram(news_df, x="compound", nbins=20, title="Sentiment Score Distribution")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Sentiment chart will appear once news data is available.")

with tab2:
    st.header("Google Trends - Leading Alternative Data")
    st.markdown("Search volume spikes often **lead** earnings and price moves by weeks (per hedge fund research).")
    
    col1, col2 = st.columns(2)
    with col1:
        for ticker, data in list(trends_data.items())[:4]:
            if isinstance(data, dict) and "avg_interest" in data:
                delta = data.get("recent_change", 0)
                st.metric(
                    f"{ticker} Search Interest", 
                    f"{data.get('avg_interest', 0)}/100",
                    f"{delta:+.1f}% (recent)"
                )
    
    with col2:
        st.info("**Pro Tip**: Rising search volume for a ticker + positive news sentiment = strong early signal for potential upside move.")
    
    # Plot trends for selected
    selected_ticker = st.selectbox("Select ticker for detailed trend", watchlist)
    if (selected_ticker in trends_data and 
        isinstance(trends_data[selected_ticker], dict) and 
        "trend_df" in trends_data[selected_ticker]):
        
        trend_df = trends_data[selected_ticker]["trend_df"].copy()
        if not trend_df.empty:
            # pytrends returns wide-format data with an 'isPartial' boolean column.
            # This causes Plotly Express "different type" error. Drop non-numeric columns.
            if "isPartial" in trend_df.columns:
                trend_df = trend_df.drop(columns=["isPartial"])
            
            # Plot all keyword trends (multi-line) - cleaner than wide-form defaults
            fig = px.line(
                trend_df, 
                title=f"Google Search Trends for {selected_ticker} (last {len(trend_df)} periods)",
                labels={"value": "Search Interest (0-100)", "index": "Date"},
                markers=True
            )
            fig.update_layout(hovermode="x unified", legend_title="Keyword")
            st.plotly_chart(fig, width="stretch")
            
            # Show summary stats
            st.caption(f"Average interest: {trends_data[selected_ticker].get('avg_interest', 0)} | "
                      f"Peak: {trends_data[selected_ticker].get('peak', 0)} | "
                      f"Recent momentum: {trends_data[selected_ticker].get('recent_change', 0):+.1f}%")
    else:
        st.warning("No trend data available for this ticker. pytrends may have rate limits or Google is throttling requests.")

with tab3:
    st.header("🚀 Potential Big Movers")
    st.markdown("**Composite Score** combines news sentiment velocity, search trend momentum, volume surges, and price action. Higher scores indicate higher likelihood of significant moves.")
    
    if not movers_df.empty:
        # Highlight high conviction
        high_conviction = movers_df[movers_df["composite_score"] > 20]
        if not high_conviction.empty:
            st.success(f"**HIGH CONVICTION MOVERS DETECTED**: {len(high_conviction)} tickers")
            st.dataframe(
                high_conviction.style.background_gradient(subset=["composite_score"], cmap="RdYlGn"),
                width="stretch",
                hide_index=True
            )
        
        st.subheader("Full Ranking")
        st.dataframe(
            movers_df.style.background_gradient(subset=["composite_score"], cmap="RdYlGn")
            .format({"composite_score": "{:.1f}", "sentiment": "{:.1f}"}),
            width="stretch",
            hide_index=True
        )
        
        # Visualization
        fig = px.bar(movers_df, x="ticker", y="composite_score", color="signal_strength",
                    title="Composite Mover Scores", color_discrete_map={"HIGH": "green", "MEDIUM": "orange", "LOW": "gray"})
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Add more data or refresh to see mover rankings.")

with tab4:
    st.header("🛎️ Alerts & Market Insights")
    st.markdown("### Key Takeaways for Getting Ahead")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Leading Signals to Watch")
        st.markdown("""
        - **Search Volume Spikes**: Google Trends often precede sales/earnings by 2-6 weeks
        - **News Sentiment Velocity**: Sudden shifts in tone across multiple articles
        - **Volume + Sentiment Combo**: Confirmation from price action
        - **Multi-Signal Convergence**: 2+ indicators aligning = highest probability
        """)
    
    with col_b:
        st.subheader("Current High-Conviction Alerts")
        if not movers_df.empty:
            alerts = movers_df[movers_df["composite_score"] > 25]
            for _, alert in alerts.iterrows():
                st.error(f"**{alert['ticker']}**: Score **{alert['composite_score']}** - {alert['signal_strength']} conviction. Check news & trends immediately!")
        else:
            st.info("No high-conviction alerts at this time. Refresh data regularly.")
    
    st.divider()
    st.markdown("""
    ### How Institutions Get Ahead (and How You Can Too)
    1. **Alternative Data**: Use search, satellite, credit cards (this tool focuses on accessible ones).
    2. **Continuous Monitoring**: Run this dashboard multiple times per day.
    3. **Combine Signals**: Never trade on one data point.
    4. **Backtest**: Test these signals historically before using real capital.
    5. **Extend This Tool**: Add X/Twitter monitoring, SEC filing scraper, earnings transcript sentiment.
    
    **Remember**: Alternative data has *signal decay*. What works today may be arbitraged tomorrow. Always pair with fundamental analysis.
    """)
    
    st.caption("Data refreshed at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Footer
st.divider()
st.markdown("**Disclaimer**: This is an educational/research tool. Not financial advice. Trading involves substantial risk of loss. API usage subject to rate limits and terms of service. pytrends and Finnhub free tiers have limitations.")
