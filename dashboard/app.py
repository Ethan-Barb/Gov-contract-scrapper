"""Streamlit dashboard for the investing intel bot.

Run locally: streamlit run dashboard/app.py
Deploy: push to GitHub, connect to Streamlit Cloud, set DASHBOARD_PASSWORD secret.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf

# ------------------------ Page config + theming ------------------------
st.set_page_config(
    page_title="Investing Intel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for dark polish
st.markdown("""
<style>
    .main { padding-top: 1rem; }
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #262730;
        border-radius: 8px 8px 0 0;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] { background-color: #FF4B4B; }
</style>
""", unsafe_allow_html=True)


# ------------------------ Password gate ------------------------
def check_password() -> bool:
    """Returns True if user has entered correct password."""
    correct_pw = st.secrets.get("DASHBOARD_PASSWORD", None)

    # If no password configured (e.g. local dev), skip gate
    if not correct_pw:
        return True

    if "auth" not in st.session_state:
        st.session_state.auth = False

    if st.session_state.auth:
        return True

    st.markdown("# 🔒 Investing Intel")
    pw = st.text_input("Password", type="password")
    if st.button("Enter") or pw:
        if pw == correct_pw:
            st.session_state.auth = True
            st.rerun()
        elif pw:
            st.error("Incorrect password")
    return False


# ------------------------ Data loading ------------------------
DB_PATH = Path(__file__).parent.parent / "data" / "intel.db"
PORTFOLIO_PATH = Path(__file__).parent.parent / "data" / "portfolio.csv"


@st.cache_data(ttl=900)  # 15 min cache
def load_table(name: str) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        try:
            return pd.read_sql_query(f"SELECT * FROM {name}", conn)
        except Exception:
            return pd.DataFrame()


@st.cache_data(ttl=900)
def load_portfolio() -> pd.DataFrame:
    if not PORTFOLIO_PATH.exists():
        return pd.DataFrame(columns=["ticker", "shares", "cost_basis", "purchase_date", "notes", "target_price"])
    return pd.read_csv(PORTFOLIO_PATH)


@st.cache_data(ttl=900)
def fetch_current_prices(tickers: list[str]) -> dict:
    """Fetch latest closes via yfinance for portfolio P&L."""
    if not tickers:
        return {}
    prices = {}
    try:
        data = yf.download(tickers, period="2d", progress=False, auto_adjust=False)
        if "Close" in data:
            close = data["Close"]
            if isinstance(close, pd.Series):
                # single ticker case
                prices[tickers[0]] = float(close.iloc[-1])
            else:
                for t in tickers:
                    if t in close.columns:
                        prices[t] = float(close[t].iloc[-1])
    except Exception:
        pass
    return prices


def refresh_button():
    if st.button("🔄 Refresh data", help="Clear cache and reload"):
        st.cache_data.clear()
        st.rerun()


# ============================================================
# Main app
# ============================================================
if not check_password():
    st.stop()

st.title("📊 Investing Intel")

with st.sidebar:
    st.markdown("### Controls")
    refresh_button()
    st.markdown("---")
    st.markdown("**Data sources**")
    st.caption("Bot writes to SQLite, dashboard reads. Refreshes every 15 min.")

# Load all data once
alerts_df = load_table("alerts")
contracts_df = load_table("contracts")
insiders_df = load_table("insider_transactions")
filings_8k_df = load_table("form_8k_filings")
earnings_df = load_table("earnings_history")
portfolio_df = load_portfolio()

# Tabs
tab_overview, tab_alerts, tab_insiders, tab_earnings, tab_contracts, tab_portfolio = st.tabs([
    "📊 Overview",
    "📋 Alerts",
    "🟢 Insiders",
    "📅 Earnings",
    "🏛️ Contracts",
    "💼 Portfolio",
])

# ============================================================
# OVERVIEW TAB
# ============================================================
with tab_overview:
    st.subheader("At a glance")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total alerts", len(alerts_df) if not alerts_df.empty else 0)
    col2.metric("Contracts tracked", len(contracts_df) if not contracts_df.empty else 0)
    col3.metric("Insider events", len(insiders_df) if not insiders_df.empty else 0)
    col4.metric("8-Ks summarized", len(filings_8k_df) if not filings_8k_df.empty else 0)

    st.markdown("---")
    st.subheader("Recent alerts")

    if alerts_df.empty:
        st.info("No alerts yet. The bots will populate this as they run.")
    else:
        recent = alerts_df.sort_values("sent_at", ascending=False).head(10)
        for _, row in recent.iterrows():
            icon = {
                "contract": "🏛️",
                "form4": "🟢" if "BUY" in str(row.get("title", "")) else "🔴",
                "8k": "📋",
                "earnings": "📅",
            }.get(row["source"], "📌")

            with st.container():
                cols = st.columns([1, 4, 2])
                cols[0].markdown(f"### {icon}")
                cols[1].markdown(
                    f"**{row.get('ticker', '?')}** — {row.get('title', '')}\n\n"
                    f"_{row.get('body', '')[:120]}_"
                )
                cols[2].caption(row["sent_at"][:16] if row.get("sent_at") else "")
                if row.get("link"):
                    cols[2].markdown(f"[View →]({row['link']})")

# ============================================================
# ALERTS TAB
# ============================================================
with tab_alerts:
    st.subheader("All alerts")

    if alerts_df.empty:
        st.info("No alerts logged yet.")
    else:
        # Filters
        c1, c2, c3 = st.columns(3)
        sources = ["All"] + sorted(alerts_df["source"].dropna().unique().tolist())
        source_filter = c1.selectbox("Source", sources)

        tickers = ["All"] + sorted(alerts_df["ticker"].dropna().unique().tolist())
        ticker_filter = c2.selectbox("Ticker", tickers)

        days = c3.selectbox("Time range", [7, 14, 30, 90, 365], index=2)

        # Apply filters
        df = alerts_df.copy()
        df["sent_at"] = pd.to_datetime(df["sent_at"], errors="coerce")
        cutoff = datetime.utcnow() - timedelta(days=days)
        df = df[df["sent_at"] >= cutoff]

        if source_filter != "All":
            df = df[df["source"] == source_filter]
        if ticker_filter != "All":
            df = df[df["ticker"] == ticker_filter]

        st.caption(f"{len(df)} alerts in last {days} days")

        df_display = df.sort_values("sent_at", ascending=False)[
            ["sent_at", "source", "ticker", "title", "body", "link"]
        ]
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "sent_at": st.column_config.DatetimeColumn("Time", format="MMM DD, HH:mm"),
                "link": st.column_config.LinkColumn("Link"),
            },
        )

# ============================================================
# INSIDERS TAB
# ============================================================
with tab_insiders:
    st.subheader("Insider transactions")

    if insiders_df.empty:
        st.info("No insider transactions logged yet. The Form 4 module needs to run first.")
    else:
        # Buy vs sell volume by ticker
        df = insiders_df.copy()
        df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
        df["is_buy"] = df["transaction_code"] == "P"

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Buy/sell volume by ticker (USD)**")
            agg = df.groupby(["ticker", "is_buy"])["total_value"].sum().reset_index()
            pivot = agg.pivot(index="ticker", columns="is_buy", values="total_value").fillna(0)
            pivot.columns = ["Sales", "Buys"]
            pivot["Net"] = pivot["Buys"] - pivot["Sales"]
            pivot = pivot.sort_values("Net", ascending=False)
            st.bar_chart(pivot[["Buys", "Sales"]])

        with c2:
            st.markdown("**Top buys (last 90 days)**")
            recent = df[df["filing_date"] >= datetime.utcnow() - timedelta(days=90)]
            top_buys = recent[recent["is_buy"]].nlargest(10, "total_value")[
                ["ticker", "insider_name", "total_value", "filing_date"]
            ]
            st.dataframe(top_buys, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("**All transactions**")
        st.dataframe(
            df.sort_values("filing_date", ascending=False)[
                ["filing_date", "ticker", "insider_name", "insider_role",
                 "transaction_code", "shares", "price", "total_value", "filing_url"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "filing_url": st.column_config.LinkColumn("Filing"),
                "total_value": st.column_config.NumberColumn("USD", format="$%.0f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            },
        )

# ============================================================
# EARNINGS TAB
# ============================================================
with tab_earnings:
    st.subheader("Earnings tracker")

    if earnings_df.empty:
        st.info("No earnings history yet. The Earnings module needs to run after companies report.")
    else:
        df = earnings_df.copy()
        df["earnings_date"] = pd.to_datetime(df["earnings_date"], errors="coerce")
        df["beat"] = (df["eps_actual"] >= df["eps_estimate"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Total reports tracked", len(df))
        beats = df["beat"].sum()
        c2.metric("Beats", f"{beats} ({beats/len(df)*100:.0f}%)" if len(df) else "0")
        avg_reaction = df["pct_change"].mean()
        c3.metric("Avg price reaction", f"{avg_reaction:+.2f}%" if not pd.isna(avg_reaction) else "n/a")

        st.markdown("---")
        st.markdown("**Beat vs miss by ticker**")
        by_ticker = df.groupby("ticker").agg(
            total=("ticker", "count"),
            beats=("beat", "sum"),
            avg_reaction=("pct_change", "mean"),
        ).reset_index()
        by_ticker["beat_rate"] = (by_ticker["beats"] / by_ticker["total"] * 100).round(0)
        st.dataframe(
            by_ticker.sort_values("total", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "beat_rate": st.column_config.ProgressColumn(
                    "Beat rate", format="%.0f%%", min_value=0, max_value=100,
                ),
                "avg_reaction": st.column_config.NumberColumn("Avg %", format="%+.2f%%"),
            },
        )

        st.markdown("---")
        st.markdown("**Full history**")
        st.dataframe(
            df.sort_values("earnings_date", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

# ============================================================
# CONTRACTS TAB
# ============================================================
with tab_contracts:
    st.subheader("Government contracts")

    if contracts_df.empty:
        st.info("No contracts tracked yet. The Contracts module needs to find awards.")
    else:
        df = contracts_df.copy()
        df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce")

        c1, c2 = st.columns(2)
        c1.metric("Awards tracked", len(df))
        total = df["amount"].sum()
        c2.metric("Total value", f"${total/1_000_000_000:.2f}B" if total >= 1e9 else f"${total/1_000_000:.0f}M")

        st.markdown("---")
        st.markdown("**Total $ won by recipient (top 15)**")
        by_recipient = df.groupby("recipient")["amount"].sum().nlargest(15)
        st.bar_chart(by_recipient)

        st.markdown("---")
        st.markdown("**Public-company awards (have ticker)**")
        public = df[df["ticker"].notna() & (df["ticker"] != "")]
        if not public.empty:
            by_ticker = public.groupby("ticker")["amount"].sum().sort_values(ascending=False)
            st.bar_chart(by_ticker)

        st.markdown("---")
        st.markdown("**All contracts**")
        st.dataframe(
            df.sort_values("posted_date", ascending=False)[
                ["posted_date", "recipient", "ticker", "amount", "naics", "title", "summary", "ui_link"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("Amount", format="$%.0f"),
                "ui_link": st.column_config.LinkColumn("SAM.gov"),
            },
        )

# ============================================================
# PORTFOLIO TAB
# ============================================================
with tab_portfolio:
    st.subheader("My portfolio")

    if portfolio_df.empty:
        st.info(
            "No portfolio data yet. Edit `data/portfolio.csv` in your repo:\n\n"
            "```\nticker,shares,cost_basis,purchase_date,notes,target_price\n"
            "NVDA,5,890.00,2024-12-15,AI conviction,1500\n```"
        )
    else:
        portfolio_df["ticker"] = portfolio_df["ticker"].str.upper()
        tickers = portfolio_df["ticker"].unique().tolist()

        with st.spinner("Fetching current prices..."):
            current_prices = fetch_current_prices(tickers)

        portfolio_df["current_price"] = portfolio_df["ticker"].map(current_prices)
        portfolio_df["market_value"] = portfolio_df["current_price"] * portfolio_df["shares"]
        portfolio_df["cost_total"] = portfolio_df["cost_basis"] * portfolio_df["shares"]
        portfolio_df["pnl_dollar"] = portfolio_df["market_value"] - portfolio_df["cost_total"]
        portfolio_df["pnl_pct"] = (portfolio_df["pnl_dollar"] / portfolio_df["cost_total"]) * 100

        total_value = portfolio_df["market_value"].sum()
        total_cost = portfolio_df["cost_total"].sum()
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Market value", f"${total_value:,.0f}")
        c2.metric("Cost basis", f"${total_cost:,.0f}")
        c3.metric("Total P&L", f"${total_pnl:,.0f}", f"{total_pnl_pct:+.2f}%")
        c4.metric("Positions", len(portfolio_df))

        st.markdown("---")

        # Allocation pie chart
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("**Allocation by position**")
            allocation = portfolio_df.set_index("ticker")["market_value"]
            st.bar_chart(allocation)

        with c2:
            st.markdown("**P&L by position**")
            pnl = portfolio_df.set_index("ticker")["pnl_dollar"]
            st.bar_chart(pnl)

        st.markdown("---")
        st.markdown("**Holdings**")
        display_cols = ["ticker", "shares", "cost_basis", "current_price",
                        "market_value", "pnl_dollar", "pnl_pct", "purchase_date", "target_price", "notes"]
        display_df = portfolio_df[[c for c in display_cols if c in portfolio_df.columns]]
        st.dataframe(
            display_df.sort_values("market_value", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "cost_basis": st.column_config.NumberColumn("Cost", format="$%.2f"),
                "current_price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "market_value": st.column_config.NumberColumn("Value", format="$%.0f"),
                "pnl_dollar": st.column_config.NumberColumn("P&L $", format="$%.0f"),
                "pnl_pct": st.column_config.NumberColumn("P&L %", format="%+.2f%%"),
                "target_price": st.column_config.NumberColumn("Target", format="$%.2f"),
            },
        )

        st.caption("Edit `data/portfolio.csv` in your repo and push to update.")
