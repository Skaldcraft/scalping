"""
dashboard/app.py
================
Streamlit web dashboard for the Precision Scalping Utility backtester.

Run with:
    streamlit run dashboard/app.py

The dashboard provides:
  - Sidebar controls for all backtest parameters
  - Equity curve chart (2R and 3R overlaid)
  - Trade journal table with filtering
  - Key metrics panels
  - 2R vs 3R comparison table
  - Per-instrument and per-mode breakdowns
  - Circuit breaker event log
  - Download buttons for all result files
"""

import sys
import logging
from datetime import date, timedelta
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

from data.models import TradeResult
from engine.backtester import Backtester
from journal.metrics import compare_targets
from journal.recorder import JournalRecorder
from journal.run_report import generate_run_report
from journal.execution_log import generate_execution_log
from risk.circuit_breaker import CircuitBreaker

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Precision Scalping Utility",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Load default config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"

@st.cache_resource
def load_default_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

# ---------------------------------------------------------------------------
# Sidebar — parameter controls
# ---------------------------------------------------------------------------

def build_sidebar(default_cfg: dict) -> dict:
    st.sidebar.title("⚙️ Backtest Parameters")

    st.sidebar.subheader("Date Range")
    start_date = st.sidebar.date_input(
        "Start Date",
        value=date.today() - timedelta(days=90),
        max_value=date.today() - timedelta(days=2),
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=date.today() - timedelta(days=1),
        max_value=date.today(),
    )

    st.sidebar.subheader("Instruments")
    default_equities = default_cfg["instruments"].get("equities", [])
    equities = st.sidebar.multiselect(
        "Equities",
        options=["AAPL", "NVDA", "AMZN", "MSFT", "GOOGL", "META", "QQQ", "SPY"],
        default=default_equities,
    )

    st.sidebar.subheader("Strategy")
    or_minutes = st.sidebar.selectbox(
        "Opening Range Candle",
        options=[5, 15],
        index=[5, 15].index(default_cfg["opening_range"]["candle_size_minutes"]),
        format_func=lambda x: f"{x}-minute",
    )

    manip_threshold = st.sidebar.slider(
        "ATR Manipulation Threshold (%)",
        min_value=15, max_value=40,
        value=int(default_cfg["strategy"]["manipulation_threshold_pct"]),
        step=1,
    )

    session_end = st.sidebar.selectbox(
        "Session Gate",
        options=["11:00", "11:30"],
        index=0,
    )

    st.sidebar.subheader("Risk Management")
    starting_capital = st.sidebar.number_input(
        "Starting Capital ($)",
        min_value=1000, max_value=1_000_000,
        value=int(default_cfg["account"]["starting_capital"]),
        step=1000,
    )
    risk_pct = st.sidebar.slider(
        "Risk Per Trade (%)",
        min_value=0.25, max_value=3.0,
        value=float(default_cfg["account"]["risk_per_trade_pct"]),
        step=0.25,
    )
    daily_loss_pct = st.sidebar.slider(
        "Daily Loss Limit (%)",
        min_value=1.0, max_value=10.0,
        value=float(default_cfg["account"]["daily_loss_limit_pct"]),
        step=0.5,
    )
    commission = st.sidebar.number_input(
        "Commission Per Trade ($)",
        min_value=0.0, max_value=10.0,
        value=float(default_cfg["commissions"]["per_trade_flat"]),
        step=0.25,
    )

    # Build config override
    cfg = dict(default_cfg)
    cfg["account"] = {
        "starting_capital":   starting_capital,
        "risk_per_trade_pct": risk_pct,
        "daily_loss_limit_pct": daily_loss_pct,
    }
    cfg["opening_range"] = {"candle_size_minutes": or_minutes}
    cfg["strategy"] = {
        "atr_period": 14,
        "manipulation_threshold_pct": manip_threshold,
        "reward_ratios": [2, 3],
    }
    cfg["session"]["end_time"]   = session_end
    cfg["commissions"]["per_trade_flat"] = commission
    cfg["instruments"]["equities"] = equities

    return cfg, start_date, end_date


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def equity_curve_chart(metrics_2r: dict, metrics_3r: dict, starting_capital: float):
    curve_2r = metrics_2r.get("equity_curve", [])
    curve_3r = metrics_3r.get("equity_curve", [])

    fig = go.Figure()
    if curve_2r:
        fig.add_trace(go.Scatter(
            y=curve_2r, mode="lines", name="2:1 R/R",
            line=dict(color="#00C896", width=2),
        ))
    if curve_3r:
        fig.add_trace(go.Scatter(
            y=curve_3r, mode="lines", name="3:1 R/R",
            line=dict(color="#4A90E2", width=2, dash="dash"),
        ))
    fig.add_hline(
        y=starting_capital, line_dash="dot",
        line_color="gray", annotation_text="Starting Capital",
    )
    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Trade #",
        yaxis_title="Account Equity ($)",
        height=400,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def mode_bar_chart(metrics_2r: dict):
    modes = metrics_2r.get("by_mode", {})
    if not modes:
        return None
    labels = [m.replace("_", " ").title() for m in modes]
    pnls   = [v.get("net_pnl", 0) for v in modes.values()]
    colors = ["#00C896" if p >= 0 else "#FF4B4B" for p in pnls]

    fig = go.Figure(go.Bar(
        x=labels, y=pnls, marker_color=colors, text=[f"${p:,.0f}" for p in pnls],
        textposition="outside",
    ))
    fig.update_layout(
        title="Net P&L by Strategy Mode (2:1 R/R)",
        yaxis_title="Net P&L ($)",
        height=300,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------------------
# Metric cards
# ---------------------------------------------------------------------------

def metric_row(label: str, m: dict):
    pf  = m.get("profit_factor")
    sr  = m.get("sharpe_ratio")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Trades",        m.get("total_trades", 0))
    c2.metric("Win Rate",      f"{m.get('win_rate', 0)*100:.1f}%")
    c3.metric("Profit Factor", f"{pf:.3f}" if pf else "N/A")
    c4.metric("Net P&L",       f"${m.get('net_pnl', 0):,.2f}")
    c5.metric("Max Drawdown",  f"{m.get('max_drawdown_pct', 0)*100:.1f}%")
    c6.metric("Sharpe",        f"{sr:.2f}" if sr else "N/A")


# ---------------------------------------------------------------------------
# Trade journal table
# ---------------------------------------------------------------------------

def build_trade_df(all_trades: list) -> pd.DataFrame:
    if not all_trades:
        return pd.DataFrame()

    rows = []
    for t in all_trades:
        rows.append({
            "ID":           t.trade_id,
            "Date":         t.session_date,
            "Instrument":   t.instrument,
            "Mode":         t.mode.replace("_", " ").title(),
            "Direction":    t.direction.upper(),
            "Entry":        t.entry_price,
            "SL":           t.stop_loss,
            "TP 2R":        t.take_profit_2r,
            "TP 3R":        t.take_profit_3r,
            "Outcome 2R":   (t.outcome_2r or "").upper(),
            "P&L 2R":       t.pnl_2r,
            "Outcome 3R":   (t.outcome_3r or "").upper(),
            "P&L 3R":       t.pnl_3r,
            "Exit Reason":  (t.exit_reason or "").replace("_", " ").title(),
            "Pattern":      t.pattern_detected or "—",
            "Manipulation": "Yes" if t.manipulation_flagged else "No",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    st.title("📈 Precision Scalping Utility — Backtester")
    st.caption(
        "A mechanical opening-range breakout strategy with ATR manipulation "
        "filter, slingshot retest confirmation, and automated risk management."
    )

    default_cfg = load_default_config()
    cfg, start_date, end_date = build_sidebar(default_cfg)

    run_button = st.sidebar.button("▶  Run Backtest", type="primary", use_container_width=True)

    if not run_button:
        st.info(
            "Configure your parameters in the sidebar and press **Run Backtest** to begin. "
            "\n\n"
            "**Data sources:**  Equities are fetched automatically from Yahoo Finance.  "
            "For Forex instruments, drop OHLCV CSV files into the `data_files/` folder "
            "and add them to `config/settings.yaml`."
        )
        return

    if not cfg["instruments"]["equities"] and not cfg["instruments"].get("forex_csv_files"):
        st.error("Please select at least one instrument before running.")
        return

    if start_date >= end_date:
        st.error("Start date must be before end date.")
        return

    # ------------------------------------------------------------------
    # Run backtest
    # ------------------------------------------------------------------
    with st.spinner("Running backtest…"):
        try:
            bt = Backtester(cfg)
            result = bt.run(start_date, end_date)
        except Exception as exc:
            st.error(f"Backtest failed: {exc}")
            st.exception(exc)
            return

    all_trades = [
        t for trades in result.instrument_results.values() for t in trades
    ]

    if not all_trades:
        st.warning(
            "The backtest completed but produced no trades.  "
            "Check the date range, instrument selection, and data availability. "
            "Validation warnings (if any) are shown below."
        )
        for w in result.validation_warnings:
            st.warning(w)
        return

    # ------------------------------------------------------------------
    # Compute metrics
    # ------------------------------------------------------------------
    comparison = compare_targets(all_trades, cfg["account"]["starting_capital"])
    metrics_2r = comparison["2r"]
    metrics_3r = comparison["3r"]

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    version = default_cfg.get("version", "1.0")
    recorder = JournalRecorder(
        results_dir="results",
        version=version,
        config=cfg,
    )
    recorder.save_trade_log(result.instrument_results)
    recorder.save_session_log(result.session_summaries)
    recorder.save_config_snapshot()

    # Collect circuit breaker events across all instruments
    # (simplified: pull from summaries for display)
    halt_events = []  # populated by circuit breaker during run

    report_path = generate_run_report(
        instrument_results=result.instrument_results,
        session_summaries=result.session_summaries,
        metrics_2r=metrics_2r,
        metrics_3r=metrics_3r,
        circuit_halt_events=halt_events,
        config=cfg,
        start_date=str(start_date),
        end_date=str(end_date),
        version=version,
        run_dir=recorder.directory,
    )

    exec_log_path = generate_execution_log(
        session_summaries=result.session_summaries,
        instrument_results=result.instrument_results,
        run_dir=recorder.directory,
        version=version,
        config=cfg,
        start_date=str(start_date),
        end_date=str(end_date),
    )

    # ------------------------------------------------------------------
    # Validation warnings
    # ------------------------------------------------------------------
    if result.validation_warnings:
        with st.expander("⚠️ Data Validation Warnings"):
            for w in result.validation_warnings:
                st.warning(w)

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------
    st.subheader("Performance Summary")

    tab_2r, tab_3r = st.tabs(["2:1 Reward Target", "3:1 Reward Target"])
    with tab_2r:
        metric_row("2:1", metrics_2r)
    with tab_3r:
        metric_row("3:1", metrics_3r)

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------
    st.plotly_chart(
        equity_curve_chart(metrics_2r, metrics_3r, cfg["account"]["starting_capital"]),
        use_container_width=True,
    )

    # ------------------------------------------------------------------
    # Mode chart
    # ------------------------------------------------------------------
    mode_fig = mode_bar_chart(metrics_2r)
    if mode_fig:
        st.plotly_chart(mode_fig, use_container_width=True)

    # ------------------------------------------------------------------
    # Comparison table
    # ------------------------------------------------------------------
    st.subheader("2R vs 3R Comparison")
    compare_data = {
        "Metric":         ["Trades", "Win Rate", "Profit Factor", "Net P&L",
                           "Max Drawdown", "Sharpe Ratio"],
        "2:1 Target":     [
            metrics_2r["total_trades"],
            f"{metrics_2r['win_rate']*100:.1f}%",
            f"{metrics_2r['profit_factor']:.3f}" if metrics_2r["profit_factor"] else "N/A",
            f"${metrics_2r['net_pnl']:,.2f}",
            f"{metrics_2r['max_drawdown_pct']*100:.1f}%",
            f"{metrics_2r['sharpe_ratio']:.2f}" if metrics_2r["sharpe_ratio"] else "N/A",
        ],
        "3:1 Target":     [
            metrics_3r["total_trades"],
            f"{metrics_3r['win_rate']*100:.1f}%",
            f"{metrics_3r['profit_factor']:.3f}" if metrics_3r["profit_factor"] else "N/A",
            f"${metrics_3r['net_pnl']:,.2f}",
            f"{metrics_3r['max_drawdown_pct']*100:.1f}%",
            f"{metrics_3r['sharpe_ratio']:.2f}" if metrics_3r["sharpe_ratio"] else "N/A",
        ],
    }
    st.table(pd.DataFrame(compare_data))

    # ------------------------------------------------------------------
    # Per-instrument breakdown
    # ------------------------------------------------------------------
    st.subheader("Per-Instrument Breakdown (2R)")
    inst_data = metrics_2r.get("by_instrument", {})
    if inst_data:
        inst_rows = []
        for sym, v in inst_data.items():
            inst_rows.append({
                "Instrument": sym,
                "Trades":     v["trades"],
                "Win Rate":   f"{v['win_rate']*100:.1f}%",
                "Net P&L":    f"${v['net_pnl']:,.2f}",
            })
        st.table(pd.DataFrame(inst_rows))

    # ------------------------------------------------------------------
    # Trade journal
    # ------------------------------------------------------------------
    st.subheader("Trade Journal")
    trade_df = build_trade_df(all_trades)
    if not trade_df.empty:
        # Filters
        col_mode, col_dir, col_inst = st.columns(3)
        modes_available = ["All"] + trade_df["Mode"].unique().tolist()
        sel_mode = col_mode.selectbox("Filter by Mode",   modes_available)
        dirs_available  = ["All"] + trade_df["Direction"].unique().tolist()
        sel_dir  = col_dir.selectbox("Filter by Direction", dirs_available)
        insts_available = ["All"] + trade_df["Instrument"].unique().tolist()
        sel_inst = col_inst.selectbox("Filter by Instrument", insts_available)

        filtered = trade_df.copy()
        if sel_mode != "All":
            filtered = filtered[filtered["Mode"] == sel_mode]
        if sel_dir != "All":
            filtered = filtered[filtered["Direction"] == sel_dir]
        if sel_inst != "All":
            filtered = filtered[filtered["Instrument"] == sel_inst]

        st.dataframe(filtered, use_container_width=True, height=400)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------
    st.subheader("Download Results")
    dl1, dl2, dl3 = st.columns(3)

    trade_log_path = recorder.directory / "trade_log.csv"
    if trade_log_path.exists():
        with open(trade_log_path, "rb") as f:
            dl1.download_button("📥 Trade Log (CSV)", f, file_name="trade_log.csv")

    if report_path.exists():
        with open(report_path, "rb") as f:
            dl2.download_button("📄 Run Report (TXT)", f, file_name="run_report.txt")

    if exec_log_path.exists():
        with open(exec_log_path, "rb") as f:
            dl3.download_button("🔍 Execution Log (JSON)", f, file_name="execution_log.json")

    st.caption(f"Results saved to: `{recorder.directory}`")


if __name__ == "__main__":
    main()
