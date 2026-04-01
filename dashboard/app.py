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
import json
from datetime import date, timedelta, datetime
from pathlib import Path
from statistics import mean

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

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results"
WEEKLY_HISTORY_START = date(2026, 3, 9)

st.markdown(
    """
    <style>
      .pulse-brand {
        padding: 0.25rem 0 0.75rem 0;
      }
      .pulse-brand h1 {
        margin: 0;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.05;
      }
      .pulse-brand p {
        margin: 0.25rem 0 0 0;
        color: rgba(49, 51, 63, 0.72);
        font-size: 0.92rem;
      }
      a, a:visited {
        color: #f1e0b7 !important;
        text-decoration: none !important;
      }
      a:hover {
        color: #fbf0d9 !important;
        text-decoration: underline !important;
      }
      a[target="_blank"]::after,
      a[rel*="noopener"]::after {
        content: none !important;
      }
      div[data-testid="stButton"] > button[kind="secondary"] {
        border-radius: 999px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PulseTrader",
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

def build_sidebar(default_cfg: dict) -> tuple[dict, date, date]:
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
    st.session_state.setdefault("custom_symbols_raw", "")
    st.session_state.setdefault("selected_equities", list(default_equities))
    custom_symbols_raw = st.sidebar.text_input(
        "Custom Symbols",
        value=st.session_state["custom_symbols_raw"],
        placeholder="TSLA, AMD, INTC",
        help="Comma-separated symbols added to the default list.",
    )
    custom_symbols = parse_custom_symbols(custom_symbols_raw)
    equity_options = list(dict.fromkeys([
        "AAPL", "NVDA", "AMZN", "MSFT", "GOOGL", "META", "QQQ", "SPY",
        *default_equities,
        *custom_symbols,
    ]))
    equities = st.sidebar.multiselect(
        "Equities",
        options=equity_options,
        default=st.session_state["selected_equities"],
    )
    st.session_state["selected_equities"] = equities
    st.session_state["custom_symbols_raw"] = custom_symbols_raw

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
    cfg["instruments"]["custom_symbols"] = custom_symbols

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


def parse_custom_symbols(raw: str) -> list[str]:
    return [sym.strip().upper() for sym in raw.split(",") if sym.strip()]


def preview_equities(default_cfg: dict) -> list[str]:
    base = list(default_cfg["instruments"].get("equities", []))
    custom = parse_custom_symbols(st.session_state.get("custom_symbols_raw", ""))
    return list(dict.fromkeys(base + custom))


def _trade_result_from_row(row: pd.Series) -> TradeResult:
    def parse_dt(value):
        if pd.notna(value) and value != "":
            return pd.to_datetime(value).to_pydatetime()
        return datetime.fromisoformat("1970-01-01T00:00:00")

    return TradeResult(
        trade_id=str(row.get("trade_id", "")),
        session_date=str(row.get("session_date", "")),
        instrument=str(row.get("instrument", "")),
        mode=str(row.get("mode", "")),
        direction=str(row.get("direction", "")),
        or_high=float(row.get("or_high", 0) or 0),
        or_low=float(row.get("or_low", 0) or 0),
        or_midpoint=float(row.get("or_midpoint", 0) or 0),
        atr_14=float(row.get("atr_14", 0) or 0),
        manipulation_flagged=bool(row.get("manipulation_flagged", False)),
        pattern_detected=str(row.get("pattern_detected", "") or ""),
        entry_time=parse_dt(row.get("entry_time")),
        entry_price=float(row.get("entry_price", 0) or 0),
        stop_loss=float(row.get("stop_loss", 0) or 0),
        take_profit_2r=float(row.get("take_profit_2r", 0) or 0),
        take_profit_3r=float(row.get("take_profit_3r", 0) or 0),
        position_size=float(row.get("position_size", 0) or 0),
        risk_amount=float(row.get("risk_amount", 0) or 0),
        exit_time_2r=parse_dt(row.get("exit_time_2r")),
        exit_price_2r=float(row.get("exit_price_2r", 0) or 0),
        outcome_2r=str(row.get("outcome_2r", "") or "") or None,
        pnl_2r=float(row.get("pnl_2r", 0) or 0),
        exit_time_3r=parse_dt(row.get("exit_time_3r")),
        exit_price_3r=float(row.get("exit_price_3r", 0) or 0),
        outcome_3r=str(row.get("outcome_3r", "") or "") or None,
        pnl_3r=float(row.get("pnl_3r", 0) or 0),
        exit_reason=str(row.get("exit_reason", "") or "") or None,
    )


def load_run_history(results_dir: Path, limit: int = 10) -> list[dict]:
    if not results_dir.exists():
        return []

    run_dirs = sorted(
        [p for p in results_dir.iterdir() if p.is_dir() and (p / "trade_log.csv").exists()],
        reverse=True,
    )

    history = []
    for run_dir in run_dirs[:limit]:
        try:
            trade_df = pd.read_csv(run_dir / "trade_log.csv")
            if trade_df.empty:
                continue
            cfg = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text()) if (run_dir / "config_snapshot.yaml").exists() else load_default_config()
            trades = [_trade_result_from_row(row) for _, row in trade_df.iterrows()]
            metrics = compare_targets(trades, cfg["account"]["starting_capital"])["2r"]
            history.append({
                "run": run_dir.name,
                "version": cfg.get("version", "?"),
                "trades": metrics["total_trades"],
                "win_rate": metrics["win_rate"] * 100,
                "profit_factor": metrics["profit_factor"],
                "net_pnl": metrics["net_pnl"],
                "max_drawdown_pct": metrics["max_drawdown_pct"] * 100,
            })
        except Exception:
            continue

    return history


def load_latest_run_summary(results_dir: Path) -> dict | None:
    if not results_dir.exists():
        return None

    run_dirs = sorted(
        [p for p in results_dir.iterdir() if p.is_dir() and not p.name.startswith("batch_") and (p / "trade_log.csv").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not run_dirs:
        return None

    run_dir = run_dirs[0]
    trade_df = pd.read_csv(run_dir / "trade_log.csv")
    if trade_df.empty:
        return None

    cfg = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text()) if (run_dir / "config_snapshot.yaml").exists() else load_default_config()
    trades = [_trade_result_from_row(row) for _, row in trade_df.iterrows()]
    metrics = compare_targets(trades, cfg["account"]["starting_capital"])
    metrics_2r = metrics["2r"]
    metrics_3r = metrics["3r"]

    return {
        "run_dir": run_dir,
        "version": cfg.get("version", "?"),
        "trades": metrics_2r.get("total_trades", 0),
        "sessions": len(pd.read_csv(run_dir / "session_log.csv")) if (run_dir / "session_log.csv").exists() else 0,
        "win_rate_2r": metrics_2r.get("win_rate", 0) * 100,
        "profit_factor_2r": metrics_2r.get("profit_factor"),
        "net_pnl_2r": metrics_2r.get("net_pnl", 0),
        "win_rate_3r": metrics_3r.get("win_rate", 0) * 100,
        "profit_factor_3r": metrics_3r.get("profit_factor"),
        "net_pnl_3r": metrics_3r.get("net_pnl", 0),
        "drawdown_pct": metrics_2r.get("max_drawdown_pct", 0) * 100,
    }


def load_latest_batch_summary(results_dir: Path) -> dict | None:
    if not results_dir.exists():
        return None

    batch_dirs = sorted(
        [p for p in results_dir.iterdir() if p.is_dir() and p.name.startswith("batch_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not batch_dirs:
        return None

    batch_dir = batch_dirs[0]
    weekly_json = batch_dir / "weekly_report.json"
    weekly_csv = batch_dir / "weekly_summary.csv"
    if not weekly_json.exists() and not weekly_csv.exists():
        return None

    summary = json.loads(weekly_json.read_text()) if weekly_json.exists() else {}
    weeks = summary.get("weeks", []) if isinstance(summary, dict) else []
    if not weeks and weekly_csv.exists():
        df = pd.read_csv(weekly_csv)
        weeks = df.to_dict(orient="records")

    filtered_weeks = []
    for row in weeks:
        parsed = pd.to_datetime(row.get("week_start", row.get("week", "")), errors="coerce")
        if pd.isna(parsed):
            continue
        if parsed.date() < WEEKLY_HISTORY_START:
            continue
        filtered_weeks.append(row)

    weeks = filtered_weeks

    if weeks:
        summary["summary"] = {
            "weeks_processed": len(weeks),
            "avg_win_rate_2r": round(mean(row.get("win_rate_2r", 0) for row in weeks), 2),
            "avg_profit_factor_2r": round(mean((row.get("profit_factor_2r") or 0) for row in weeks), 2),
            "total_net_pnl_2r": round(sum(row.get("net_pnl_2r", 0) for row in weeks), 2),
        }
        summary["best_week"] = max(weeks, key=lambda row: row.get("net_pnl_2r", 0))
        summary["weakest_week"] = min(weeks, key=lambda row: row.get("net_pnl_2r", 0))

    return {
        "batch_dir": batch_dir,
        "weeks": weeks,
        "summary": summary.get("summary", {}) if isinstance(summary, dict) else {},
        "report_path": batch_dir / "weekly_report.txt",
    }


def _run_week_key(run_name: str) -> str:
    stamp = run_name.split("_v", 1)[0]
    run_date = pd.to_datetime(stamp, format="%Y%m%d_%H%M%S", errors="coerce")
    if pd.isna(run_date):
        return "unknown"
    iso = run_date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _run_week_start(run_name: str):
    stamp = run_name.split("_v", 1)[0]
    run_date = pd.to_datetime(stamp, format="%Y%m%d_%H%M%S", errors="coerce")
    if pd.isna(run_date):
        return None
    return run_date.date() - timedelta(days=run_date.date().weekday())


def build_weekly_long_view(results_dir: Path, weeks: int = 8) -> dict:
    history = load_run_history(results_dir, limit=weeks * 8)
    if not history:
        return {"weeks": [], "trend": {}}

    grouped: dict[str, list[dict]] = {}
    for item in history:
        week_start = _run_week_start(item["run"])
        if week_start is None or week_start < WEEKLY_HISTORY_START:
            continue
        key = _run_week_key(item["run"])
        grouped.setdefault(key, []).append(item)

    week_rows = []
    for week_key in sorted(grouped.keys(), reverse=True)[:weeks]:
        items = grouped[week_key]
        week_rows.append({
            "week": week_key,
            "runs": len(items),
            "trades": int(sum(x.get("trades", 0) for x in items)),
            "avg_win_rate": round(mean(x.get("win_rate", 0) for x in items), 2),
            "avg_profit_factor": round(mean((x.get("profit_factor") or 0) for x in items), 2),
            "net_pnl": round(sum(x.get("net_pnl", 0) for x in items), 2),
            "avg_drawdown_pct": round(mean(x.get("max_drawdown_pct", 0) for x in items), 2),
        })

    trend = {}
    if len(week_rows) >= 1:
        current = week_rows[0]
        trend = {
            "current_week": current["week"],
            "current_win_rate": current["avg_win_rate"],
            "current_profit_factor": current["avg_profit_factor"],
            "current_net_pnl": current["net_pnl"],
            "best_week": max(week_rows, key=lambda row: row.get("net_pnl", 0))["week"],
            "weakest_week": min(week_rows, key=lambda row: row.get("net_pnl", 0))["week"],
        }
        if len(week_rows) >= 2:
            prior = week_rows[1]
            trend["vs_previous_week"] = {
                "win_rate_change": round(current["avg_win_rate"] - prior["avg_win_rate"], 2),
                "profit_factor_change": round(current["avg_profit_factor"] - prior["avg_profit_factor"], 2),
                "net_pnl_change": round(current["net_pnl"] - prior["net_pnl"], 2),
            }

    return {"weeks": week_rows, "trend": trend}


def build_weekly_equity_overview(results_dir: Path, symbols: list[str]) -> dict:
    tracked = [sym.upper() for sym in symbols if sym]
    symbol_series: dict[str, dict[str, dict]] = {sym: {} for sym in tracked}
    overall_series: dict[str, dict] = {}

    trade_logs = sorted(results_dir.rglob("trade_log.csv")) if results_dir.exists() else []
    for trade_log in trade_logs:
        try:
            trade_df = pd.read_csv(trade_log)
        except Exception:
            continue
        if trade_df.empty or "session_date" not in trade_df.columns:
            continue

        for _, row in trade_df.iterrows():
            symbol = str(row.get("instrument", "")).upper()
            if symbol not in symbol_series:
                continue

            session_dt = pd.to_datetime(row.get("session_date"), errors="coerce")
            if pd.isna(session_dt):
                continue

            if session_dt.date() < WEEKLY_HISTORY_START:
                continue

            week_start = session_dt.date() - timedelta(days=session_dt.date().weekday())
            week_key = week_start.isoformat()
            pnl = float(row.get("pnl_2r", 0) or 0)
            outcome = str(row.get("outcome_2r", "") or "").lower()

            sym_bucket = symbol_series[symbol].setdefault(
                week_key,
                {
                    "week": week_key,
                    "week_start": week_start,
                    "week_end": (week_start + timedelta(days=6)).isoformat(),
                    "trades": 0,
                    "wins": 0,
                    "net_pnl": 0.0,
                },
            )
            sym_bucket["trades"] += 1
            sym_bucket["net_pnl"] += pnl
            if outcome == "win":
                sym_bucket["wins"] += 1

            overall_bucket = overall_series.setdefault(
                week_key,
                {
                    "week": week_key,
                    "week_start": week_start,
                    "week_end": (week_start + timedelta(days=6)).isoformat(),
                    "trades": 0,
                    "wins": 0,
                    "net_pnl": 0.0,
                },
            )
            overall_bucket["trades"] += 1
            overall_bucket["net_pnl"] += pnl
            if outcome == "win":
                overall_bucket["wins"] += 1

    overall = [overall_series[k] for k in sorted(overall_series.keys())]
    by_symbol = {}
    for symbol, weeks in symbol_series.items():
        ordered = [weeks[k] for k in sorted(weeks.keys())]
        for item in ordered:
            item["win_rate"] = round((item["wins"] / item["trades"] * 100), 2) if item["trades"] else 0.0
        by_symbol[symbol] = ordered

    for item in overall:
        item["win_rate"] = round((item["wins"] / item["trades"] * 100), 2) if item["trades"] else 0.0

    return {"overall": overall, "by_symbol": by_symbol}


def _sparkline_figure(points: list[dict], title: str):
    fig = go.Figure()
    if points:
        fig.add_trace(
            go.Scatter(
                x=[p["week"] for p in points],
                y=[p["net_pnl"] for p in points],
                mode="lines+markers",
                line=dict(color="#00C896", width=2),
                marker=dict(size=6),
                hovertemplate="Week %{x}<br>Net P&L $%{y:,.2f}<extra></extra>",
                showlegend=False,
            )
        )
    fig.update_layout(
        title=title,
        height=180,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis_title=None,
        yaxis_title=None,
        xaxis=dict(tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10)),
    )
    return fig


def render_weekly_equity_overview(symbols: list[str], results_dir: Path):
    overview = build_weekly_equity_overview(results_dir, symbols)
    overall = overview["overall"]
    by_symbol = overview["by_symbol"]

    st.subheader("Weekly Equity Overview")
    if overall:
        st.plotly_chart(_sparkline_figure(overall, "Portfolio Weekly Net P&L"), use_container_width=True)
    else:
        st.info("No weekly data yet for the portfolio overview.")

    if not symbols:
        st.info("No equities selected yet.")
        return

    st.write("Per-symbol weekly performance")
    cols = st.columns(2)
    for idx, symbol in enumerate(symbols):
        with cols[idx % 2]:
            points = by_symbol.get(symbol, [])
            st.markdown(f"**{symbol}**")
            if points:
                st.plotly_chart(_sparkline_figure(points, f"{symbol} Weekly Net P&L"), use_container_width=True)
                latest = points[-1]
                st.caption(
                    f"Latest week {latest['week']}: ${latest['net_pnl']:,.2f} | "
                    f"Trades: {latest['trades']} | Win Rate: {latest['win_rate']:.1f}%"
                )
            else:
                st.info("No data yet")


def render_top_nav(active_view: str):
    left, right = st.columns([1.5, 2])
    with left:
        if st.button("PulseTrader", key="nav_home", use_container_width=True):
            st.session_state["view"] = "home"
            st.rerun()
    with right:
        if st.button("Backtest", key="nav_backtest", use_container_width=True):
            st.session_state["view"] = "backtest"
            st.rerun()


def render_home():
    st.write("")

    st.subheader("Quick Symbol Editor")
    st.session_state.setdefault("custom_symbols_raw", "")
    custom_symbols_raw = st.text_input(
        "Custom Symbols",
        value=st.session_state["custom_symbols_raw"],
        placeholder="TSLA, AMD, INTC",
        help="Comma-separated symbols added to the default list for the next backtest.",
        key="home_custom_symbols",
    )
    st.session_state["custom_symbols_raw"] = custom_symbols_raw
    st.caption("Changes here will appear in the sidebar the next time you open Backtest.")
    live_symbols = preview_equities(load_default_config())
    st.markdown(
        f"<div style='color: rgba(241,224,183,0.95); font-size: 0.95rem;'>"
        f"Live symbol preview: {', '.join(live_symbols) if live_symbols else 'No symbols selected yet.'}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color: rgba(241,224,183,0.85); font-size: 0.9rem;'>"
        "Weekly results are directional and informational. They are not final conclusions, but a way to monitor how the strategy is behaving over time."
        "</div>",
        unsafe_allow_html=True,
    )

    latest_run = load_latest_run_summary(RESULTS_PATH)
    latest_batch = load_latest_batch_summary(RESULTS_PATH)
    long_view = build_long_view(RESULTS_PATH, limit=8)

    c1, c2 = st.columns(2)
    c1.metric("Saved Weeks", len(long_view.get("recent", [])))
    c2.metric("Batch Report", "Available" if latest_batch else "None")

    if latest_run:
        st.subheader("Latest Run")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Trades", latest_run["trades"])
        r2.metric("Win Rate", f"{latest_run['win_rate_2r']:.1f}%")
        r3.metric("Profit Factor", f"{latest_run['profit_factor_2r']:.2f}" if latest_run["profit_factor_2r"] else "N/A")
        r4.metric("Net P&L", f"${latest_run['net_pnl_2r']:,.2f}")
        latest_cfg_path = latest_run["run_dir"] / "config_snapshot.yaml"
        if latest_cfg_path.exists():
            latest_cfg = yaml.safe_load(latest_cfg_path.read_text())
            custom_symbols = latest_cfg.get("instruments", {}).get("custom_symbols", [])
            if custom_symbols:
                st.caption(f"Custom symbols used: {', '.join(custom_symbols)}")

    weekly_rows = long_view.get("recent", [])
    charts_tab, history_tab, summary_tab = st.tabs(["Weekly Charts", "Weekly History", "Weekly Summary"])

    with charts_tab:
        render_weekly_equity_overview(live_symbols, RESULTS_PATH)

    with history_tab:
        if weekly_rows:
            st.dataframe(pd.DataFrame(weekly_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No weekly history found yet.")

    with summary_tab:
        if latest_batch:
            review_cfg = load_default_config().get("weekly_review", {}) or {}
            batch_summary = latest_batch.get("summary", {})
            weeks = latest_batch.get("weeks", [])
            recent_weeks = weeks[-3:] if len(weeks) > 3 else weeks
            summary_df = pd.DataFrame(recent_weeks)[["week_start", "week_end", "status", "trades", "win_rate_2r", "net_pnl_2r"]] if recent_weeks else pd.DataFrame()
            b1, b2, b3 = st.columns(3)
            b1.metric("Weeks", len(recent_weeks))
            b2.metric("Avg Win Rate", f"{batch_summary.get('avg_win_rate_2r', 'N/A')}%" if batch_summary.get("avg_win_rate_2r") is not None else "N/A")
            b3.metric("Total P&L", f"${batch_summary.get('total_net_pnl_2r', 0):,.2f}" if batch_summary else "N/A")
            if not summary_df.empty:
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

            best_week = latest_batch.get("best_week")
            weakest_week = latest_batch.get("weakest_week")
            if best_week and weakest_week:
                st.write(
                    f"Best week: {best_week['week_start']} to {best_week['week_end']} (${best_week['net_pnl_2r']:,.2f})"
                )
                st.write(
                    f"Weakest week: {weakest_week['week_start']} to {weakest_week['week_end']} (${weakest_week['net_pnl_2r']:,.2f})"
                )
            st.caption(f"Recent view status: {classify_long_view_status(recent_weeks, review_cfg)}")
        else:
            st.info("No weekly batch report found yet.")

    st.divider()
    st.write("Use the PulseTrader button above to return to home and the Backtest button to run a new test.")


def build_long_view(results_dir: Path, limit: int = 5) -> dict:
    weekly = build_weekly_long_view(results_dir, weeks=limit)
    return {"recent": weekly["weeks"], "trend": weekly["trend"]}


def classify_review_status(metrics: dict, review_cfg: dict) -> str:
    trade_count = metrics.get("total_trades", 0)
    if trade_count < int(review_cfg.get("min_trades_for_setup_review", 10)):
        return f"Too few trades ({trade_count})"

    win_rate_pct = metrics.get("win_rate", 0) * 100
    profit_factor = metrics.get("profit_factor") or 0.0
    drawdown_pct = metrics.get("max_drawdown_pct", 0) * 100

    if (
        win_rate_pct >= float(review_cfg.get("good_win_rate_pct", 60.0))
        and profit_factor >= float(review_cfg.get("good_profit_factor", 1.5))
        and drawdown_pct <= float(review_cfg.get("good_drawdown_pct", 3.0))
    ):
        return "Good"

    if (
        win_rate_pct >= float(review_cfg.get("mixed_win_rate_pct", 45.0))
        and profit_factor >= float(review_cfg.get("mixed_profit_factor", 1.0))
        and drawdown_pct <= float(review_cfg.get("mixed_drawdown_pct", 5.0))
    ):
        return "Mixed"

    return "Weak"


def classify_long_view_status(weeks: list[dict], review_cfg: dict) -> str:
    if not weeks:
        return "No data"

    total_trades = sum(int(week.get("trades", 0)) for week in weeks)
    min_trades = int(review_cfg.get("min_trades_for_setup_review", 10))
    if total_trades < min_trades * 2:
        return f"Too few trades across recent weeks ({total_trades})"

    avg_win_rate = mean(float(week.get("win_rate_2r", 0)) for week in weeks)
    avg_pf = mean(float(week.get("profit_factor_2r") or 0) for week in weeks)
    if avg_win_rate >= float(review_cfg.get("good_win_rate_pct", 60.0)) and avg_pf >= float(review_cfg.get("good_profit_factor", 1.5)):
        return "Strong recent trend"
    if avg_win_rate >= float(review_cfg.get("mixed_win_rate_pct", 45.0)) and avg_pf >= float(review_cfg.get("mixed_profit_factor", 1.0)):
        return "Mixed recent trend"
    return "Weak recent trend"


def build_weekly_review(metrics: dict, cfg: dict) -> tuple[str, list[str], list[str]]:
    review_cfg = cfg.get("weekly_review", {}) or {}
    if not review_cfg.get("enabled", True):
        return "Off", [], []

    status = classify_review_status(metrics, review_cfg)
    by_mode = metrics.get("by_mode", {}) or {}
    by_instrument = metrics.get("by_instrument", {}) or {}

    best_setup = None
    weakest_setup = None
    if by_mode:
        ranked = sorted(by_mode.items(), key=lambda item: item[1].get("net_pnl", 0), reverse=True)
        best_setup = ranked[0][0]
        weakest_setup = ranked[-1][0]

    best_symbol = None
    weakest_symbol = None
    if by_instrument:
        ranked_symbols = sorted(by_instrument.items(), key=lambda item: item[1].get("net_pnl", 0), reverse=True)
        best_symbol = ranked_symbols[0][0]
        weakest_symbol = ranked_symbols[-1][0]

    takeaway = []
    if status.startswith("Too few trades"):
        takeaway.append("The sample is still small, so this is only a first read.")
    else:
        takeaway.append("The current sample is workable, but performance is uneven.")

    if best_setup:
        takeaway.append(f"Best setup this period: {best_setup.replace('_', ' ').title()}.")
    if weakest_setup:
        takeaway.append(f"Weakest setup this period: {weakest_setup.replace('_', ' ').title()}.")

    next_watch = []
    if best_symbol:
        next_watch.append(f"Watch whether {best_symbol} stays the strongest symbol.")
    if weakest_symbol:
        next_watch.append(f"Watch whether {weakest_symbol} improves or stays weak.")
    next_watch.append("Watch whether the win rate and profit factor stay above the mixed threshold.")

    return status, takeaway, next_watch


def build_shared_review_language(
    title: str,
    status: str,
    highlight: str | None,
    comparison_text: str | None,
    watch_items: list[str],
) -> list[str]:
    lines = [f"{title} status: {status}."]
    if highlight:
        lines.append(highlight)
    if comparison_text:
        lines.append(comparison_text)
    if watch_items:
        lines.append("Next watch:")
        lines.extend(watch_items)
    return lines


def render_results(cfg: dict, result, recorder: JournalRecorder, report_path, exec_log_path):
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

    comparison = compare_targets(all_trades, cfg["account"]["starting_capital"])
    metrics_2r = comparison["2r"]
    metrics_3r = comparison["3r"]

    if result.validation_warnings:
        with st.expander("⚠️ Data Validation Warnings"):
            for w in result.validation_warnings:
                st.warning(w)

    st.subheader("Performance Summary")

    tab_2r, tab_3r = st.tabs(["2:1 Reward Target", "3:1 Reward Target"])
    with tab_2r:
        metric_row("2:1", metrics_2r)
    with tab_3r:
        metric_row("3:1", metrics_3r)

    st.plotly_chart(
        equity_curve_chart(metrics_2r, metrics_3r, cfg["account"]["starting_capital"]),
        use_container_width=True,
    )

    mode_fig = mode_bar_chart(metrics_2r)
    if mode_fig:
        st.plotly_chart(mode_fig, use_container_width=True)

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

    st.subheader("Weekly Review")
    weekly_status, weekly_takeaway, weekly_watch = build_weekly_review(metrics_2r, cfg)
    weekly_sessions = sum(len(v) for v in result.session_summaries.values())
    weekly_trades = metrics_2r.get("total_trades", 0)
    weekly_win_rate = metrics_2r.get("win_rate", 0) * 100
    weekly_pf = metrics_2r.get("profit_factor")

    w1, w2, w3, w4 = st.columns(4)
    w1.metric("Sessions", weekly_sessions)
    w2.metric("Trades", weekly_trades)
    w3.metric("Win Rate", f"{weekly_win_rate:.1f}%")
    w4.metric("Profit Factor", f"{weekly_pf:.3f}" if weekly_pf else "N/A")

    status_color = {
        "Good": "success",
        "Mixed": "warning",
        "Weak": "error",
        "Too little data": "info",
    }.get(weekly_status, "info")
    if status_color == "success":
        st.success(f"Status: {weekly_status}")
    elif status_color == "warning":
        st.warning(f"Status: {weekly_status}")
    elif status_color == "error":
        st.error(f"Status: {weekly_status}")
    else:
        st.warning(f"Status: {weekly_status}")

    pf_text = f"{metrics_2r['profit_factor']:.3f}" if metrics_2r.get("profit_factor") else "N/A"
    weekly_lines = build_shared_review_language(
        title="This week",
        status=weekly_status,
        highlight=(
            f"The utility reviewed {metrics_2r.get('total_trades', 0)} trades. "
            f"Win rate was {metrics_2r.get('win_rate', 0)*100:.1f}%, profit factor was {pf_text}."
        ),
        comparison_text=weekly_takeaway[0] if weekly_takeaway else None,
        watch_items=weekly_watch,
    )
    for line in weekly_lines:
        st.write(line)

    st.subheader("Recent Runs")
    long_view_cfg = cfg.get("long_view", {}) or {}
    if long_view_cfg.get("enabled", True):
        long_view = build_long_view(
            RESULTS_PATH,
            limit=int(long_view_cfg.get("recent_weeks_to_show", 8)),
        )
        recent_weeks = long_view.get("recent", [])
        trend = long_view.get("trend", {})

        if recent_weeks:
            lr1, lr2, lr3, lr4 = st.columns(4)
            lr1.metric("Current Week Win Rate", f"{trend.get('current_win_rate', 0):.1f}%" if trend else "N/A")
            lr2.metric("Current Week PF", f"{trend.get('current_profit_factor', 0):.2f}" if trend else "N/A")
            lr3.metric("Current Week P&L", f"${trend.get('current_net_pnl', 0):,.2f}" if trend else "N/A")
            lr4.metric("Best Week", trend.get("best_week", "N/A"))

            if trend.get("vs_previous_week"):
                delta = trend["vs_previous_week"]
                st.caption(
                    f"Compared with the previous week: win rate {delta['win_rate_change']:+.2f} points, "
                    f"profit factor {delta['profit_factor_change']:+.2f}, net P&L {delta['net_pnl_change']:+.2f}."
                )

            long_lines = build_shared_review_language(
                title="Across recent weeks",
                status=weekly_status,
                highlight=(
                    f"The latest weekly window shows {trend.get('current_win_rate', 0):.1f}% win rate, "
                    f"profit factor {trend.get('current_profit_factor', 0):.2f}, and P&L ${trend.get('current_net_pnl', 0):,.2f}."
                ),
                comparison_text=(
                    f"The strongest week in this sample is {trend.get('best_week', 'N/A')}; "
                    f"the weakest is {trend.get('weakest_week', 'N/A')}."
                ),
                watch_items=[
                    "Watch whether the latest week stays above the mixed threshold.",
                    "Watch whether the week-over-week trend remains stable.",
                ],
            )
            for line in long_lines:
                st.write(line)

            st.dataframe(pd.DataFrame(recent_weeks), use_container_width=True, hide_index=True)
        else:
            st.info("No saved weekly history found yet for the long-view summary.")
    else:
        st.caption("Long-view review is disabled in config.")

    st.subheader("Trade Journal")
    trade_df = build_trade_df(all_trades)
    if not trade_df.empty:
        col_mode, col_dir, col_inst = st.columns(3)
        modes_available = ["All"] + trade_df["Mode"].unique().tolist()
        sel_mode = col_mode.selectbox("Filter by Mode", modes_available)
        dirs_available = ["All"] + trade_df["Direction"].unique().tolist()
        sel_dir = col_dir.selectbox("Filter by Direction", dirs_available)
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

    st.subheader("Download Results")
    dl1, dl2, dl3 = st.columns(3)
    trade_log_path = recorder.directory / "trade_log.csv"
    if trade_log_path.exists():
        dl1.download_button(
            "📥 Trade Log (CSV)",
            data=trade_log_path.read_bytes(),
            file_name="trade_log.csv",
            mime="text/csv",
            key="download_trade_log",
        )

    if report_path.exists():
        dl2.download_button(
            "📄 Run Report (TXT)",
            data=report_path.read_bytes(),
            file_name="run_report.txt",
            mime="text/plain",
            key="download_run_report",
        )

    if exec_log_path.exists():
        dl3.download_button(
            "🔍 Execution Log (JSON)",
            data=exec_log_path.read_bytes(),
            file_name="execution_log.json",
            mime="application/json",
            key="download_exec_log",
        )

    st.caption(f"Results saved to: `{recorder.directory}`")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    st.session_state.setdefault("view", "home")
    render_top_nav(st.session_state["view"])

    if st.session_state["view"] == "home":
        render_home()
        return

    st.title("PulseTrader Backtester")
    st.caption(
        "A mechanical opening-range breakout strategy with ATR manipulation "
        "filter, slingshot retest confirmation, and automated risk management."
    )
    st.caption("Weekly results are monitoring signals, not final conclusions.")

    default_cfg = load_default_config()
    cfg, start_date, end_date = build_sidebar(default_cfg)

    run_button = st.sidebar.button("▶  Run Backtest", type="primary", use_container_width=True)

    if run_button:
        if not cfg["instruments"]["equities"] and not cfg["instruments"].get("forex_csv_files"):
            st.error("Please select at least one instrument before running.")
            return

        if start_date >= end_date:
            st.error("Start date must be before end date.")
            return

        with st.spinner("Running backtest…"):
            try:
                bt = Backtester(cfg)
                result = bt.run(start_date, end_date)
            except Exception as exc:
                st.error(f"Backtest failed: {exc}")
                st.exception(exc)
                return

        version = default_cfg.get("version", "1.0")
        recorder = JournalRecorder(results_dir="results", version=version, config=cfg)
        recorder.save_trade_log(result.instrument_results)
        recorder.save_session_log(result.session_summaries)
        recorder.save_config_snapshot()

        halt_events = []
        all_trades = [t for trades in result.instrument_results.values() for t in trades]
        comparison = compare_targets(all_trades, cfg["account"]["starting_capital"])
        report_path = generate_run_report(
            instrument_results=result.instrument_results,
            session_summaries=result.session_summaries,
            metrics_2r=comparison["2r"],
            metrics_3r=comparison["3r"],
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

        st.session_state["last_run"] = {
            "cfg": cfg,
            "result": result,
            "recorder": recorder,
            "report_path": report_path,
            "exec_log_path": exec_log_path,
        }

    last_run = st.session_state.get("last_run")
    if not last_run:
        st.info(
            "Configure your parameters in the sidebar and press **Run Backtest** to begin. "
            "\n\n"
            "**Data sources:**  Equities are fetched automatically from Yahoo Finance.  "
            "For Forex instruments, drop OHLCV CSV files into the `data_files/` folder "
            "and add them to `config/settings.yaml`."
        )
        return
    render_results(
        last_run["cfg"],
        last_run["result"],
        last_run["recorder"],
        last_run["report_path"],
        last_run["exec_log_path"],
    )


if __name__ == "__main__":
    main()
