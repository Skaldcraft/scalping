"""
dashboard/app.py
================
Streamlit web dashboard for the Precision Scalping Utility backtester.

Run with:
    python -m streamlit run dashboard/app.py

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

import copy
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
import streamlit.components.v1 as components
import yaml

from data.models import TradeResult
from engine.backtester import Backtester
from journal.metrics import compare_targets
from journal.recorder import JournalRecorder
from journal.run_report import generate_run_report
from journal.execution_log import generate_execution_log
from journal.strategic_briefing import build_strategic_briefing
from risk.circuit_breaker import CircuitBreaker
from dashboard.results_manager import (
    delete_items_permanently,
    list_results,
    move_items_to_trash,
    restore_items_from_trash,
    summarize as summarize_results,
)

logging.basicConfig(level=logging.INFO)

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results"
WEEKLY_HISTORY_START = date(2026, 3, 9)

st.markdown(
    """
    <style>
            :root {
                --pulse-panel-border: rgba(98, 68, 24, 0.22);
                --pulse-panel-bg: rgba(98, 68, 24, 0.08);
                --pulse-tab-border: rgba(98, 68, 24, 0.22);
                --pulse-tab-bg: rgba(98, 68, 24, 0.06);
                --pulse-tab-active: linear-gradient(90deg, rgba(201, 156, 58, 0.24), rgba(34, 154, 120, 0.18));
            }
            @media (prefers-color-scheme: dark) {
                :root {
                    --pulse-panel-border: rgba(233, 190, 102, 0.22);
                    --pulse-panel-bg: rgba(233, 190, 102, 0.10);
                    --pulse-tab-border: rgba(233, 190, 102, 0.22);
                    --pulse-tab-bg: rgba(233, 190, 102, 0.08);
                    --pulse-tab-active: linear-gradient(90deg, rgba(201, 156, 58, 0.28), rgba(34, 154, 120, 0.20));
                }
            }
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
        color: inherit;
        opacity: 0.78;
        font-size: 0.92rem;
      }
      .theme-note {
        color: inherit;
        opacity: 0.88;
        font-size: 0.95rem;
      }
      .theme-note--small {
        font-size: 0.9rem;
                opacity: 0.9;
      }
      .soft-panel {
        padding: 0.9rem 1rem;
        border-radius: 14px;
                border: 1px solid var(--pulse-panel-border);
                background: var(--pulse-panel-bg);
        color: inherit;
      }
      [data-testid="stAppSkipLink"],
      a[href="#main-content"],
      a[href="#main"] {
        display: none !important;
      }
      h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
      }
      div[data-testid="stButton"] > button[kind="secondary"] {
        border-radius: 999px;
      }
      div[data-baseweb="tab-list"] {
        gap: 0.45rem;
        margin-bottom: 0.35rem;
      }
      button[data-baseweb="tab"] {
        height: 2.35rem;
        padding: 0.15rem 0.95rem;
        border-radius: 999px;
                border: 1px solid var(--pulse-tab-border);
                background: var(--pulse-tab-bg);
        color: inherit !important;
                opacity: 0.92;
        font-size: 1.08rem !important;
        font-weight: 600 !important;
                filter: none;
      }
      button[data-baseweb="tab"][aria-selected="true"] {
                background: var(--pulse-tab-active);
        color: inherit !important;
        opacity: 1;
      }
            section[data-testid="stSidebar"] a,
            [data-testid="stMarkdownContainer"] a,
            .stMarkdown a,
            .stCaption a {
                color: #b6862c !important;
            }
            section[data-testid="stSidebar"] a:visited,
            [data-testid="stMarkdownContainer"] a:visited,
            .stMarkdown a:visited,
            .stCaption a:visited {
                color: #b6862c !important;
            }
            section[data-testid="stSidebar"] a:hover,
            [data-testid="stMarkdownContainer"] a:hover,
            .stMarkdown a:hover,
            .stCaption a:hover {
                color: #d6a84f !important;
            }
            section[data-testid="stSidebar"] [data-baseweb="select"] *:focus,
            section[data-testid="stSidebar"] input:focus,
            section[data-testid="stSidebar"] textarea:focus,
            section[data-testid="stSidebar"] [data-baseweb="tag"],
            section[data-testid="stSidebar"] [aria-selected="true"] {
                box-shadow: 0 0 0 1px rgba(201, 156, 58, 0.55) !important;
                border-color: rgba(201, 156, 58, 0.65) !important;
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
USER_PREFS_PATH = Path(__file__).resolve().parent.parent / "config" / "user_prefs.json"
GUIDE_PATH = Path(__file__).resolve().parent.parent / "BEGINNER_GUIDE.md"

@st.cache_resource
def load_default_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_user_prefs() -> dict:
    """Load persisted sidebar settings from user_prefs.json."""
    if USER_PREFS_PATH.exists():
        try:
            return json.loads(USER_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_user_prefs(prefs: dict) -> None:
    """Persist sidebar settings to user_prefs.json."""
    try:
        USER_PREFS_PATH.write_text(
            json.dumps(prefs, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass

@st.cache_data
def load_beginner_guide() -> str:
    if GUIDE_PATH.exists():
        return GUIDE_PATH.read_text(encoding="utf-8")
    return (
        "# How it works\n\n"
        "The beginner guide is not available yet, but the Backtest tab is ready to use."
    )


def enable_dashboard_auto_refresh(interval_minutes: int = 15):
    interval_ms = max(1, interval_minutes) * 60 * 1000
    st.sidebar.caption(
        f"Auto-refresh is active. The dashboard will reload every {interval_minutes} minutes to pick up new scheduled results."
    )
    components.html(
        f"""
        <script>
            window.setTimeout(function() {{
                window.parent.location.reload();
            }}, {interval_ms});
        </script>
        """,
        height=0,
    )

# ---------------------------------------------------------------------------
# Sidebar — parameter controls
# ---------------------------------------------------------------------------

def build_sidebar(default_cfg: dict) -> tuple[dict, date, date]:
    st.sidebar.title("Backtest Controls")

    _prefs = load_user_prefs()

    st.sidebar.subheader("Date Range")
    _default_start = (
        date.fromisoformat(_prefs["start_date"])
        if "start_date" in _prefs
        else date.today() - timedelta(days=90)
    )
    _default_end = (
        date.fromisoformat(_prefs["end_date"])
        if "end_date" in _prefs
        else date.today() - timedelta(days=1)
    )
    start_date = st.sidebar.date_input(
        "Start Date",
        value=_default_start,
        max_value=date.today() - timedelta(days=2),
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=_default_end,
        max_value=date.today(),
    )


    st.sidebar.subheader("Equity Selection")
    default_equities = default_cfg["instruments"].get("equities", [])
    tracked_universe = tracked_universe_symbols(default_cfg)
    st.sidebar.caption("All equities in the universe will be analyzed by default. To analyze only specific equities, select them below.")


    # Multi-select for override, always update session state
    selected_equities = st.sidebar.multiselect(
        "Select equities to analyze (optional)",
        options=tracked_universe,
        default=st.session_state.get("selected_equities", []),
        help="Leave empty to analyze all equities. Select one or more to override.",
        key="selected_equities"
    )
    # Reset button
    if st.sidebar.button("Reset selection to all", help="Reset to analyze all equities."):
        st.session_state["selected_equities"] = []


    st.sidebar.subheader("Strategy")
    or_minutes = st.sidebar.selectbox(
        "Opening Range Candle",
        options=[5, 15],
        index=[5, 15].index(int(_prefs.get("or_minutes", default_cfg["opening_range"]["candle_size_minutes"]))),
        format_func=lambda x: f"{x}-minute",
    )

    manip_threshold = st.sidebar.slider(
        "ATR Manipulation Threshold (%)",
        min_value=15, max_value=40,
        value=int(_prefs.get("manip_threshold", default_cfg["strategy"]["manipulation_threshold_pct"])),
        step=1,
    )

    trend_mode_cfg = (default_cfg.get("strategy", {}) or {}).get("trend_mode", {}) or {}
    allow_gap_entry = st.sidebar.checkbox(
        "Enable Displacement Gap Entries",
        value=bool(_prefs.get("allow_gap_entry", trend_mode_cfg.get("allow_displacement_gap_entry", True))),
    )
    entry_priority = st.sidebar.selectbox(
        "Trend Entry Priority",
        options=["retest_first", "gap_first"],
        index=["retest_first", "gap_first"].index(str(_prefs.get("entry_priority", trend_mode_cfg.get("entry_priority", "retest_first")))),
    )
    displacement_min_atr_pct = st.sidebar.slider(
        "Gap Min Size (% of ATR14)",
        min_value=0.0,
        max_value=15.0,
        value=float(_prefs.get("displacement_min_atr_pct", trend_mode_cfg.get("displacement_min_atr_pct", 3.0))),
        step=0.5,
    )
    displacement_min_body_pct = st.sidebar.slider(
        "Gap Bar Min Body (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(_prefs.get("displacement_min_body_pct", trend_mode_cfg.get("displacement_min_body_pct", 60.0))),
        step=5.0,
    )

    session_end = "11:00"
    st.sidebar.caption("Session Gate is fixed at 11:00 ET for alignment with automation.")

    st.sidebar.subheader("Risk Management")
    starting_capital = st.sidebar.number_input(
        "Starting Capital ($)",
        min_value=1000, max_value=1_000_000,
        value=int(_prefs.get("starting_capital", default_cfg["account"]["starting_capital"])),
        step=1000,
    )
    risk_pct = st.sidebar.slider(
        "Risk Per Trade (%)",
        min_value=0.25, max_value=3.0,
        value=float(_prefs.get("risk_pct", default_cfg["account"]["risk_per_trade_pct"])),
        step=0.25,
    )
    daily_loss_pct = st.sidebar.slider(
        "Daily Loss Limit (%)",
        min_value=1.0, max_value=10.0,
        value=float(_prefs.get("daily_loss_pct", default_cfg["account"]["daily_loss_limit_pct"])),
        step=0.5,
    )
    commission = st.sidebar.number_input(
        "Commission Per Trade ($)",
        min_value=0.0, max_value=10.0,
        value=float(_prefs.get("commission", default_cfg["commissions"]["per_trade_flat"])),
        step=0.25,
    )

    # Build config override
    cfg = copy.deepcopy(default_cfg)
    cfg["account"] = {
        "starting_capital":   starting_capital,
        "risk_per_trade_pct": risk_pct,
        "daily_loss_limit_pct": daily_loss_pct,
    }
    cfg["opening_range"] = {"candle_size_minutes": or_minutes}
    cfg.setdefault("strategy", {})["atr_period"] = 14
    cfg["strategy"]["manipulation_threshold_pct"] = manip_threshold
    cfg["strategy"]["reward_ratios"] = [2, 3]
    cfg["strategy"].setdefault("trend_mode", {})
    cfg["strategy"]["trend_mode"]["allow_displacement_gap_entry"] = allow_gap_entry
    cfg["strategy"]["trend_mode"]["entry_priority"] = entry_priority
    cfg["strategy"]["trend_mode"]["displacement_min_atr_pct"] = displacement_min_atr_pct
    cfg["strategy"]["trend_mode"]["displacement_min_body_pct"] = displacement_min_body_pct

    cfg["session"]["end_time"]   = session_end
    cfg["commissions"]["per_trade_flat"] = commission

    # If user selected specific equities, use only those; else use all
    # Use the current selection for the run
    equities_to_run = st.session_state.get("selected_equities", [])
    if equities_to_run:
        cfg["instruments"]["equities"] = equities_to_run
    else:
        cfg["instruments"]["equities"] = tracked_universe or default_equities
    cfg["instruments"]["custom_symbols"] = []

    save_user_prefs({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "or_minutes": int(or_minutes),
        "manip_threshold": int(manip_threshold),
        "allow_gap_entry": allow_gap_entry,
        "entry_priority": entry_priority,
        "displacement_min_atr_pct": float(displacement_min_atr_pct),
        "displacement_min_body_pct": float(displacement_min_body_pct),
        "starting_capital": int(starting_capital),
        "risk_pct": float(risk_pct),
        "daily_loss_pct": float(daily_loss_pct),
        "commission": float(commission),
    })

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
            line=dict(color="#C99C3A", width=2, dash="dash"),
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


def tracked_universe_symbols(default_cfg: dict) -> list[str]:
    pre_cfg = default_cfg.get("pre_session", {}) or {}
    raw_universe = pre_cfg.get("universe", [])
    symbols: list[str] = []

    for item in raw_universe:
        if isinstance(item, str):
            symbols.append(item.upper())
        elif isinstance(item, dict) and item.get("symbol"):
            symbols.append(str(item["symbol"]).upper())

    if symbols:
        return list(dict.fromkeys(symbols))

    base = list(default_cfg.get("instruments", {}).get("equities", []))
    return list(dict.fromkeys(sym.upper() for sym in base if sym))


def tracked_universe_entries(default_cfg: dict) -> list[dict]:
    pre_cfg = default_cfg.get("pre_session", {}) or {}
    raw_universe = pre_cfg.get("universe", [])
    entries: list[dict] = []

    for item in raw_universe:
        if isinstance(item, str):
            entries.append({"symbol": item.upper(), "asset_class": "equity"})
        elif isinstance(item, dict) and item.get("symbol"):
            entries.append(
                {
                    "symbol": str(item["symbol"]).upper(),
                    "asset_class": str(item.get("asset_class", "equity")).lower(),
                }
            )

    if entries:
        return entries

    return [
        {"symbol": sym.upper(), "asset_class": "equity"}
        for sym in default_cfg.get("instruments", {}).get("equities", [])
        if sym
    ]


def _display_symbol(symbol: str) -> str:
    display_map = {
        "EURUSD=X": "EUR/USD",
        "GBPUSD=X": "GBP/USD",
        "JPY=X": "USD/JPY",
        "XAUUSD=X": "XAU/USD (Gold)",
    }
    return display_map.get(symbol.upper(), symbol.upper())


def grouped_tracked_universe(default_cfg: dict) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for entry in tracked_universe_entries(default_cfg):
        asset_class = entry.get("asset_class", "equity")
        groups.setdefault(asset_class, []).append(_display_symbol(entry["symbol"]))
    return groups


def _display_asset_class(asset_class: str) -> str:
    label_map = {
        "equity": "Equities",
        "index": "Indices",
        "forex": "Forex",
        "metal": "Gold / Metals",
    }
    return label_map.get(asset_class.lower(), asset_class.replace("_", " ").title())


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


def _safe_read_csv(path: Path) -> pd.DataFrame:
    """Read CSV safely and return an empty DataFrame on empty/corrupt files."""
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


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
            trade_df = _safe_read_csv(run_dir / "trade_log.csv")
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
    trade_df = _safe_read_csv(run_dir / "trade_log.csv")
    if trade_df.empty:
        return None

    cfg = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text()) if (run_dir / "config_snapshot.yaml").exists() else load_default_config()
    trades = [_trade_result_from_row(row) for _, row in trade_df.iterrows()]
    metrics = compare_targets(trades, cfg["account"]["starting_capital"])
    metrics_2r = metrics["2r"]
    metrics_3r = metrics["3r"]

    session_count = 0
    if (run_dir / "session_log.csv").exists():
        session_count = len(_safe_read_csv(run_dir / "session_log.csv"))

    return {
        "run_dir": run_dir,
        "version": cfg.get("version", "?"),
        "trades": metrics_2r.get("total_trades", 0),
        "sessions": session_count,
        "win_rate_2r": metrics_2r.get("win_rate", 0) * 100,
        "profit_factor_2r": metrics_2r.get("profit_factor"),
        "net_pnl_2r": metrics_2r.get("net_pnl", 0),
        "win_rate_3r": metrics_3r.get("win_rate", 0) * 100,
        "profit_factor_3r": metrics_3r.get("profit_factor"),
        "net_pnl_3r": metrics_3r.get("net_pnl", 0),
        "drawdown_pct": metrics_2r.get("max_drawdown_pct", 0) * 100,
    }


def load_selection_snapshot(run_dir: Path) -> dict | None:
    snapshot_path = run_dir / "selection_snapshot.json"
    if not snapshot_path.exists():
        return None
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return None


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
        df = _safe_read_csv(weekly_csv)
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
    latest_session_date = None

    trade_logs = sorted(results_dir.rglob("trade_log.csv")) if results_dir.exists() else []
    for trade_log in trade_logs:
        if "_trash" in trade_log.parts:
            continue
        try:
            trade_df = _safe_read_csv(trade_log)
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

            if latest_session_date is None or session_dt.date() > latest_session_date:
                latest_session_date = session_dt.date()

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

    return {
        "overall": overall,
        "by_symbol": by_symbol,
        "latest_session_date": latest_session_date.isoformat() if latest_session_date else None,
    }


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
        st.plotly_chart(_sparkline_figure(overall, "Portfolio Weekly Net P&L"), width="stretch")
    else:
        st.caption("No weekly data yet for the portfolio overview.")

    if not symbols:
        st.caption("No master-universe symbols configured yet.")
        return

    st.write("Per-symbol weekly performance")
    cols = st.columns(2)
    for idx, symbol in enumerate(symbols):
        with cols[idx % 2]:
            points = by_symbol.get(symbol, [])
            st.markdown(f"**{symbol}**")
            if points:
                st.plotly_chart(_sparkline_figure(points, f"{symbol} Weekly Net P&L"), width="stretch")
                latest = points[-1]
                st.caption(
                    f"Latest week {latest['week']}: ${latest['net_pnl']:,.2f} | "
                    f"Trades: {latest['trades']} | Win Rate: {latest['win_rate']:.1f}%"
                )
            else:
                st.caption("No data yet")


def render_how_it_works():
    st.title("How it works")
    st.caption(
        "A beginner-friendly guide to scalping, backtesting, and using PulseTrader with confidence."
    )

    st.markdown(
        """
        <div style="padding: 1rem 1.1rem; border-radius: 16px; border: 1px solid rgba(201,156,58,0.24); background: linear-gradient(135deg, rgba(201,156,58,0.18), rgba(34,154,120,0.12)); margin-bottom: 0.85rem;">
            <h3 style="margin:0 0 0.35rem 0;">Start here</h3>
            <p style="margin:0;">
                PulseTrader helps you study how a rule-based scalping idea would have behaved on past market data.
                It is designed for learning, review, and disciplined testing — not for automatic live order placement.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### What it studies")
        st.write("Opening-range setups near the New York market open.")
    with c2:
        st.markdown("### What it does")
        st.write("Runs backtests, compares outcomes, and saves clear result files.")
    with c3:
        st.markdown("### What it is not")
        st.write("It is not a broker connection and does not place live trades for you.")

    st.divider()
    st.markdown(load_beginner_guide())


def render_home():
    st.write("")

    st.subheader("Tracked Universe")
    live_symbols = tracked_universe_symbols(load_default_config())
    grouped_universe = grouped_tracked_universe(load_default_config())
    if grouped_universe:
        u1, u2 = st.columns(2)
        group_items = list(grouped_universe.items())
        for idx, (group_name, symbols) in enumerate(group_items):
            with (u1 if idx % 2 == 0 else u2):
                st.markdown(f"**{_display_asset_class(group_name)}**")
                st.write(", ".join(symbols))

        total_symbols = sum(len(symbols) for symbols in grouped_universe.values())
        st.caption(
            f"PulseTrader tracks {total_symbols} instruments across equities, indices, forex, and gold. "
            "Normal runs use this fixed universe; only the pre-session selector decides which symbols are traded in the session."
        )
    else:
        st.caption("No tracked universe configured yet.")

    st.caption("Use Research Overrides in the Backtest sidebar only when testing custom subsets.")
    st.markdown(
        "<div class='theme-note theme-note--small'>"
        "Weekly results are directional and informational. They are not final conclusions, but a way to monitor how the strategy is behaving over time."
        "</div>",
        unsafe_allow_html=True,
    )

    latest_run = load_latest_run_summary(RESULTS_PATH)
    latest_batch = load_latest_batch_summary(RESULTS_PATH)
    long_view = build_long_view(RESULTS_PATH, limit=8)
    weekly_overview = build_weekly_equity_overview(RESULTS_PATH, live_symbols)
    last_data_date = weekly_overview.get("latest_session_date") or "N/A"

    c1, c2, c3 = st.columns(3)
    c1.metric("Saved Weeks", len(long_view.get("recent", [])))
    c2.metric("Batch Report", "Available" if latest_batch else "None")
    c3.metric("Last Data Date", last_data_date)

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
                st.caption(f"Custom symbols added to universe: {', '.join(custom_symbols)}")

            pre_cfg = latest_cfg.get("pre_session", {}) or {}
            selection_snapshot = load_selection_snapshot(latest_run["run_dir"])
            if pre_cfg.get("enabled", False):
                st.markdown("**Pre-Session Selection**")
                ps1, ps2, ps3, ps4 = st.columns(4)
                selected_symbols = (selection_snapshot or {}).get("selected_symbols", [])
                evaluated = (selection_snapshot or {}).get("evaluated", [])
                excluded_count = max(0, len(evaluated) - len(selected_symbols))
                ps1.metric("Selector", "Enabled")
                ps2.metric("Top-N", int(pre_cfg.get("top_n", 3)))
                ps3.metric("Selected", len(selected_symbols))
                ps4.metric("Excluded", excluded_count)

                if selected_symbols:
                    st.caption(f"Session symbols: {', '.join(selected_symbols)}")
                else:
                    st.caption("No selection snapshot found for this run.")

                rules = (selection_snapshot or {}).get("rules", {})
                if rules:
                    st.caption(
                        "Policies: "
                        f"PF missing={rules.get('pf_missing_policy', 'allow')}, "
                        f"Spread missing={rules.get('spread_missing_policy', 'allow')}"
                    )

    weekly_rows = long_view.get("recent", [])
    charts_tab, history_tab, summary_tab = st.tabs(["Weekly Charts", "Weekly History", "Weekly Summary"])

    with charts_tab:
        render_weekly_equity_overview(live_symbols, RESULTS_PATH)

    with history_tab:
        if weekly_rows:
            st.dataframe(pd.DataFrame(weekly_rows), width="stretch", hide_index=True)
        else:
            st.caption("No weekly history found yet.")

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
                st.dataframe(summary_df, width="stretch", hide_index=True)

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
        elif weekly_rows:
            derived_rows = []
            for row in weekly_rows:
                week_key = str(row.get("week", ""))
                week_start = ""
                week_end = ""
                try:
                    year_str, week_str = week_key.split("-W")
                    week_start_date = datetime.fromisocalendar(int(year_str), int(week_str), 1).date()
                    week_end_date = week_start_date + timedelta(days=4)
                    week_start = week_start_date.isoformat()
                    week_end = week_end_date.isoformat()
                except Exception:
                    week_start = week_key

                derived_rows.append(
                    {
                        "week_start": week_start,
                        "week_end": week_end,
                        "trades": int(row.get("trades", 0) or 0),
                        "win_rate_2r": float(row.get("avg_win_rate", 0) or 0),
                        "net_pnl_2r": float(row.get("net_pnl", 0) or 0),
                    }
                )

            recent_weeks = derived_rows[:3]
            avg_win = mean(x["win_rate_2r"] for x in recent_weeks) if recent_weeks else 0
            total_pnl = sum(x["net_pnl_2r"] for x in recent_weeks) if recent_weeks else 0
            b1, b2, b3 = st.columns(3)
            b1.metric("Weeks", len(recent_weeks))
            b2.metric("Avg Win Rate", f"{avg_win:.2f}%")
            b3.metric("Total P&L", f"${total_pnl:,.2f}")
            st.dataframe(pd.DataFrame(recent_weeks), width="stretch", hide_index=True)
            st.caption("Showing run-based weekly summary because no active weekly batch report is available.")
        else:
            st.caption("No weekly batch report found yet.")

    st.divider()
    st.write("Use the tabs above to move between `PulseTrader`, `Results Manager`, `Backtest`, and `How it works`.")


def render_results_manager():
    st.title("Results Manager")
    st.caption("Browse and clean saved runs from the interface.")

    # Deferred feedback from post-rerun messages
    for _key, _fn in [("rm_msg_success", st.success), ("rm_msg_warning", st.warning)]:
        if _key in st.session_state:
            _fn(st.session_state.pop(_key))

    active_records, trash_records = list_results(RESULTS_PATH)
    summary = summarize_results(active_records, trash_records)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Runs", summary["total_runs"])
    m2.metric("Total Size", summary["total_size"])
    m3.metric("In Trash", summary["trash_count"])
    m4.metric("Reclaimable", summary["reclaimable"])

    search = st.text_input(
        "Search results",
        value="",
        placeholder="TSLA, 20260402, batch_2026...",
        help="Search by folder name or symbols found in trade logs.",
    ).strip().lower()

    def _matches(record: dict) -> bool:
        if not search:
            return True
        return search in record.get("id", "").lower() or search in record.get("symbols", "").lower()

    # Radio-based tab navigation: persists across st.rerun() via session_state
    tab_choice = st.radio(
        "",
        ["Backtests", "Weekly Batches", "Trash"],
        horizontal=True,
        label_visibility="collapsed",
        key="rm_tab_radio",
    )
    st.divider()

    def _checkbox_table(rows: list[dict], id_col: str, key: str) -> list[str]:
        df = pd.DataFrame([{"Select": False, **row} for row in rows])
        edited = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={"Select": st.column_config.CheckboxColumn(" ", default=False)},
            key=key,
        )
        return list(edited.loc[edited["Select"], id_col])

    def _soft_delete_confirm(yes_key: str, no_key: str) -> tuple[bool, bool]:
        st.warning("This will move all listed items to Trash. Are you sure?")
        ca, cb = st.columns(2)
        return ca.button("Yes, move all to Trash", key=yes_key), cb.button("Cancel", key=no_key)

    def _perm_delete_confirm(yes_key: str, no_key: str) -> tuple[bool, bool]:
        st.warning("This will **permanently** delete all listed items. Are you sure?")
        ca, cb = st.columns(2)
        return ca.button("Yes, permanently delete all", key=yes_key), cb.button("Cancel", key=no_key)

    # ------------------------------------------------------------------
    if tab_choice == "Backtests":
        backtests = [r for r in active_records if r.get("kind") == "backtest" and _matches(r)]
        if backtests:
            rows = [
                {
                    "Run": r["id"],
                    "Trades": r["trades"],
                    "Net P&L (2R)": r["net_pnl_2r"],
                    "Symbols": r["symbols"],
                    "Size": r["size"],
                }
                for r in backtests
            ]
            selected = _checkbox_table(rows, "Run", "rm_bt_editor")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Move selected to Trash", key="rm_bt_del_sel"):
                    if not selected:
                        st.error("Check at least one row to move.")
                    else:
                        moved, skipped = move_items_to_trash(RESULTS_PATH, selected)
                        st.session_state["rm_msg_success"] = f"Moved {moved} run(s) to Trash."
                        if skipped:
                            st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                        st.rerun()
            with c2:
                if st.button("Move all to Trash", key="rm_bt_del_all"):
                    st.session_state["rm_bt_confirm_all"] = True
            if st.session_state.get("rm_bt_confirm_all"):
                confirmed, cancelled = _soft_delete_confirm("rm_bt_confirm_yes", "rm_bt_confirm_no")
                if confirmed:
                    moved, skipped = move_items_to_trash(RESULTS_PATH, [r["id"] for r in backtests])
                    st.session_state["rm_bt_confirm_all"] = False
                    st.session_state["rm_msg_success"] = f"Moved {moved} run(s) to Trash."
                    if skipped:
                        st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                    st.rerun()
                if cancelled:
                    st.session_state["rm_bt_confirm_all"] = False
                    st.rerun()
        else:
            st.caption("No backtests match your search.")

    # ------------------------------------------------------------------
    elif tab_choice == "Weekly Batches":
        batches = [r for r in active_records if r.get("kind") == "weekly_batch" and _matches(r)]
        if batches:
            rows = [
                {
                    "Batch": r["id"],
                    "Updated": r["modified"],
                    "Trades": r["trades"],
                    "Net P&L (2R)": r["net_pnl_2r"],
                    "Symbols": r["symbols"],
                    "Size": r["size"],
                }
                for r in batches
            ]
            selected = _checkbox_table(rows, "Batch", "rm_wk_editor")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Move selected to Trash", key="rm_wk_del_sel"):
                    if not selected:
                        st.error("Check at least one row to move.")
                    else:
                        moved, skipped = move_items_to_trash(RESULTS_PATH, selected)
                        st.session_state["rm_msg_success"] = f"Moved {moved} batch(es) to Trash."
                        if skipped:
                            st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                        st.rerun()
            with c2:
                if st.button("Move all to Trash", key="rm_wk_del_all"):
                    st.session_state["rm_wk_confirm_all"] = True
            if st.session_state.get("rm_wk_confirm_all"):
                confirmed, cancelled = _soft_delete_confirm("rm_wk_confirm_yes", "rm_wk_confirm_no")
                if confirmed:
                    moved, skipped = move_items_to_trash(RESULTS_PATH, [r["id"] for r in batches])
                    st.session_state["rm_wk_confirm_all"] = False
                    st.session_state["rm_msg_success"] = f"Moved {moved} batch(es) to Trash."
                    if skipped:
                        st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                    st.rerun()
                if cancelled:
                    st.session_state["rm_wk_confirm_all"] = False
                    st.rerun()
        else:
            st.caption("No weekly batches match your search.")

    # ------------------------------------------------------------------
    elif tab_choice == "Trash":
        trash_filtered = [r for r in trash_records if _matches(r)]
        if trash_filtered:
            rows = [
                {
                    "Item": r["id"],
                    "Type": r["kind"],
                    "Updated": r["modified"],
                    "Trades": r["trades"],
                    "Net P&L (2R)": r["net_pnl_2r"],
                    "Size": r["size"],
                }
                for r in trash_filtered
            ]
            selected = _checkbox_table(rows, "Item", "rm_tr_editor")

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Restore selected", key="rm_tr_restore"):
                    if not selected:
                        st.error("Check at least one row to restore.")
                    else:
                        restored, skipped = restore_items_from_trash(RESULTS_PATH, selected)
                        st.session_state["rm_msg_success"] = f"Restored {restored} item(s)."
                        if skipped:
                            st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                        st.rerun()
            with c2:
                if st.button("Delete selected", key="rm_tr_del_sel"):
                    if not selected:
                        st.error("Check at least one row to delete.")
                    else:
                        deleted, skipped, reclaimed = delete_items_permanently(RESULTS_PATH, selected)
                        reclaimed_mb = reclaimed / (1024 * 1024)
                        st.session_state["rm_msg_success"] = f"Permanently deleted {deleted} item(s). Reclaimed {reclaimed_mb:.2f} MB."
                        if skipped:
                            st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                        st.rerun()
            with c3:
                if st.button("Delete all", key="rm_tr_del_all"):
                    st.session_state["rm_tr_confirm_all"] = True
            if st.session_state.get("rm_tr_confirm_all"):
                confirmed, cancelled = _perm_delete_confirm("rm_tr_confirm_yes", "rm_tr_confirm_no")
                if confirmed:
                    all_ids = [r["id"] for r in trash_filtered]
                    deleted, skipped, reclaimed = delete_items_permanently(RESULTS_PATH, all_ids)
                    reclaimed_mb = reclaimed / (1024 * 1024)
                    st.session_state["rm_tr_confirm_all"] = False
                    st.session_state["rm_msg_success"] = f"Permanently deleted {deleted} item(s). Reclaimed {reclaimed_mb:.2f} MB."
                    if skipped:
                        st.session_state["rm_msg_warning"] = f"Skipped: {', '.join(skipped)}"
                    st.rerun()
                if cancelled:
                    st.session_state["rm_tr_confirm_all"] = False
                    st.rerun()
        else:
            st.caption("Trash is empty.")



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
    def _load_reasoning_memory() -> dict:
        diagnostics_csv = recorder.directory / "execution_diagnostics.csv"
        if not diagnostics_csv.exists():
            return {}
        try:
            df = pd.read_csv(diagnostics_csv)
        except Exception:
            return {}
        if "instrument" not in df.columns or "Reasoning and Logic" not in df.columns:
            return {}

        memory = {}
        for _, row in df.iterrows():
            sym = str(row.get("instrument", "")).strip().upper()
            reason = str(row.get("Reasoning and Logic", "")).strip()
            if sym and reason and reason.lower() != "nan":
                memory[sym] = reason
        return memory

    reasoning_memory = _load_reasoning_memory()

    def _build_briefing(all_trades_payload, metrics_payload):
        try:
            return build_strategic_briefing(
                all_trades=all_trades_payload,
                session_summaries=result.session_summaries,
                metrics_2r=metrics_payload,
                config=cfg,
                reasoning_memory=reasoning_memory,
            )
        except TypeError:
            return build_strategic_briefing(
                all_trades=all_trades_payload,
                session_summaries=result.session_summaries,
                metrics_2r=metrics_payload,
            )

    def _render_operator_card(briefing_payload):
        card = briefing_payload.get("operator_card") or {}
        if not card:
            return

        keep_symbols = card.get("keep_symbols") or []
        reduce_symbols = card.get("reduce_symbols") or []
        standby_symbols = card.get("standby_symbols") or []

        def _symbol_text(symbols):
            return ", ".join(symbols) if symbols else "None"

        st.subheader("Operator Card")

        st.markdown(
            """
            <style>
            .op-shell {
                border: 1px solid rgba(120,120,120,0.55);
                border-radius: 12px;
                padding: 14px;
                background: linear-gradient(145deg, rgba(120,120,120,0.14), rgba(120,120,120,0.06));
            }
            .op-badge {
                display: inline-block;
                padding: 4px 10px;
                margin-right: 8px;
                margin-bottom: 8px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 600;
            }
            .op-keep {
                background: rgba(22,163,74,0.18);
                border: 1px solid rgba(22,163,74,0.35);
            }
            .op-reduce {
                background: rgba(220,38,38,0.16);
                border: 1px solid rgba(220,38,38,0.30);
            }
            .op-standby {
                background: rgba(217,119,6,0.18);
                border: 1px solid rgba(217,119,6,0.32);
            }
            .op-slider-box {
                border: 1px solid rgba(120,120,120,0.60);
                border-radius: 10px;
                padding: 10px 12px;
                margin-bottom: 8px;
                background: rgba(120,120,120,0.14);
            }
            .op-slider-title {
                font-size: 12px;
                color: inherit;
                opacity: 0.92;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 4px;
            }
            .op-slider-value {
                font-size: 14px;
                font-weight: 600;
                color: inherit;
                line-height: 1.4;
            }
            .op-state-badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 999px;
                border: 1px solid transparent;
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 8px;
            }
            .op-state-confirmed {
                background: rgba(22,163,74,0.18);
                border-color: rgba(22,163,74,0.35);
            }
            .op-state-balanced {
                background: rgba(217,119,6,0.18);
                border-color: rgba(217,119,6,0.32);
            }
            .op-state-risk {
                background: rgba(220,38,38,0.16);
                border-color: rgba(220,38,38,0.30);
            }
            .op-interpret-box {
                border: 1px solid rgba(120,120,120,0.28);
                border-radius: 10px;
                padding: 10px 12px;
                margin-bottom: 8px;
                background: rgba(255,255,255,0.02);
            }
            .op-tag {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 700;
                margin-bottom: 6px;
                border: 1px solid transparent;
                text-transform: uppercase;
                letter-spacing: 0.02em;
            }
            .op-tag-confirmed {
                background: rgba(22,163,74,0.18);
                border-color: rgba(22,163,74,0.35);
            }
            .op-tag-balanced {
                background: rgba(217,119,6,0.18);
                border-color: rgba(217,119,6,0.32);
            }
            .op-tag-risk {
                background: rgba(220,38,38,0.16);
                border-color: rgba(220,38,38,0.30);
            }
            .op-interpret-confirmed {
                border-color: rgba(22,163,74,0.40);
                background: rgba(22,163,74,0.08);
            }
            .op-interpret-balanced {
                border-color: rgba(217,119,6,0.40);
                background: rgba(217,119,6,0.08);
            }
            .op-interpret-risk {
                border-color: rgba(220,38,38,0.36);
                background: rgba(220,38,38,0.08);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        execution_interp = str(card.get("execution_interpretation") or "")
        gap_interp = str(card.get("gap_interpretation") or "")
        fakeout_interp = str(card.get("fakeout_interpretation") or "")
        gap_interp_lower = gap_interp.lower()

        if fakeout_interp or "footprint' was too light" in gap_interp_lower:
            state_label = "Noise / Trap Risk"
            state_class = "op-state-risk"
        elif "slingshot effect" in execution_interp.lower():
            state_label = "Confirmed Slingshot"
            state_class = "op-state-confirmed"
        else:
            state_label = "Balanced Confirmation"
            state_class = "op-state-balanced"

        st.markdown(
            f'<span class="op-state-badge {state_class}">Session State: {state_label}</span>',
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Best Model", card.get("execution_model") or "N/A")
        m2.metric("Keep", str(len(keep_symbols)))
        m3.metric("Reduce", str(len(reduce_symbols)))
        m4.metric("Standby", str(len(standby_symbols)))

        st.markdown(
            (
                '<div class="op-shell">'
                f'<span class="op-badge op-keep">KEEP: {_symbol_text(keep_symbols)}</span>'
                f'<span class="op-badge op-reduce">REDUCE: {_symbol_text(reduce_symbols)}</span>'
                f'<span class="op-badge op-standby">STANDBY: {_symbol_text(standby_symbols)}</span>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown("**Slider Recommendations**")
        st.markdown(
            (
                '<div class="op-slider-box">'
                '<div class="op-slider-title">ATR Stop</div>'
                f'<div class="op-slider-value">{card.get("atr_recommendation", "N/A")}</div>'
                '</div>'
                '<div class="op-slider-box">'
                '<div class="op-slider-title">Risk Per Trade</div>'
                f'<div class="op-slider-value">{card.get("risk_recommendation", "N/A")}</div>'
                '</div>'
                '<div class="op-slider-box">'
                '<div class="op-slider-title">Daily Loss Limit</div>'
                f'<div class="op-slider-value">{card.get("daily_loss_recommendation", "N/A")}</div>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )

        interp_rows = []
        if execution_interp:
            exec_class = (
                "op-interpret-confirmed"
                if "slingshot effect" in execution_interp.lower()
                else "op-interpret-balanced"
            )
            exec_tag = "CONFIRMED" if exec_class == "op-interpret-confirmed" else "CAUTION"
            exec_tag_class = "op-tag-confirmed" if exec_tag == "CONFIRMED" else "op-tag-balanced"
            interp_rows.append((execution_interp, exec_class, exec_tag, exec_tag_class))
        if gap_interp:
            gap_class = (
                "op-interpret-risk"
                if ("too light" in gap_interp_lower or "filter out these traps" in gap_interp_lower)
                else "op-interpret-balanced"
            )
            gap_tag = "RISK" if gap_class == "op-interpret-risk" else "CAUTION"
            gap_tag_class = "op-tag-risk" if gap_tag == "RISK" else "op-tag-balanced"
            interp_rows.append((gap_interp, gap_class, gap_tag, gap_tag_class))
        if fakeout_interp:
            interp_rows.append((fakeout_interp, "op-interpret-risk", "RISK", "op-tag-risk"))

        if interp_rows:
            st.markdown("**Session Interpretation**")
            st.markdown(
                "".join(
                    [
                        f'<div class="op-interpret-box {css_class}">'
                        f'<div><span class="op-tag {tag_css_class}">{tag_label}</span></div>'
                        f'<div class="op-slider-value">{line}</div>'
                        '</div>'
                        for line, css_class, tag_label, tag_css_class in interp_rows
                    ]
                ),
                unsafe_allow_html=True,
            )

    def _render_symbol_reasoning(briefing_payload, *, key_suffix: str):
        reasoning = briefing_payload.get("symbol_reasoning") or {}
        if not reasoning:
            return

        st.markdown("**Journal Memory: Reasoning and Logic**")
        for sym, reason in reasoning.items():
            st.write(f"- {sym}: {reason}")

        symbols = sorted(reasoning.keys())
        if not symbols:
            return

        st.markdown("**Why Was Symbol Skipped?**")
        chosen = st.selectbox(
            "Choose a symbol to view its skip/execution explanation",
            options=symbols,
            key=f"skip_reason_symbol_{key_suffix}",
        )
        st.info(reasoning.get(chosen, "No reasoning available for this symbol in this run."))

    def _build_briefing_document(briefing_payload) -> str:
        lines = [
            "Strategic Briefing",
            "=" * 48,
            "",
            "The Strategy's Pulse",
            briefing_payload.get("strategy_pulse", ""),
            "",
            "Strategic Focus",
        ]

        for line in briefing_payload.get("strategic_focus", []) or []:
            lines.append(f"- {line}")

        lines += ["", "System Standards (Auto-Enforced)"]
        for line in briefing_payload.get("system_standards", []) or []:
            lines.append(f"- {line}")

        lines += ["", "Dashboard Calibration Recommendations"]
        for line in briefing_payload.get("settings_calibration", []) or []:
            lines.append(f"- {line}")

        reasoning = briefing_payload.get("symbol_reasoning") or {}
        if reasoning:
            lines += ["", "Journal Memory: Reasoning and Logic"]
            for sym, reason in reasoning.items():
                lines.append(f"- {sym}: {reason}")

        actions = briefing_payload.get("equity_actions") or []
        if actions:
            lines += ["", "Equities Requiring Action"]
            for line in actions:
                lines.append(f"- {line}")

        lines += ["", "=" * 48]
        return "\n".join(lines)

    def _render_briefing_download(briefing_payload, *, key_suffix: str):
        doc_text = _build_briefing_document(briefing_payload)
        st.download_button(
            "Download Strategic Briefing (TXT)",
            data=doc_text.encode("utf-8"),
            file_name="strategic_briefing.txt",
            mime="text/plain",
            key=f"download_strategic_briefing_{key_suffix}",
        )

    def _render_execution_diagnostics(exec_path: Path):
        if not exec_path or not exec_path.exists():
            return

        try:
            payload = json.loads(exec_path.read_text(encoding="utf-8"))
        except Exception:
            st.warning("Execution diagnostics could not be loaded.")
            return

        st.subheader("Execution Diagnostics")

        gate_counts = ((payload.get("aggregate") or {}).get("gate_status_counts") or {})
        if gate_counts:
            gate_rows = []
            for gate_name, counts in gate_counts.items():
                gate_rows.append({
                    "Gate": gate_name,
                    "Passed": int(counts.get("passed", 0)),
                    "Failed": int(counts.get("failed", 0)),
                    "Skipped": int(counts.get("skipped", 0)),
                    "Unknown": int(counts.get("unknown", 0)),
                })
            st.caption("Gate pass/fail summary")
            st.dataframe(pd.DataFrame(gate_rows), width="stretch", hide_index=True)

        sessions = payload.get("sessions", []) or []
        if sessions:
            session_rows = []
            for s in sessions:
                row = {
                    "Date": s.get("session_date"),
                    "Instrument": s.get("instrument"),
                    "Mode": ((s.get("phase_1") or {}).get("mode_activated") or "").replace("_", " ").title(),
                    "Trigger": (s.get("phase_1") or {}).get("trigger_candle") or "—",
                    "Trade Executed": bool(s.get("trade_executed", False)),
                    "Rejection Reasons": "; ".join(s.get("rejection_reasons", []) or []),
                }

                for gate in s.get("decision_trace", []) or []:
                    gate_name = str(gate.get("gate", "")).replace("_", " ").title()
                    row[f"Gate: {gate_name}"] = gate.get("status", "")

                session_rows.append(row)

            st.caption("Session-level decision trace")
            st.dataframe(pd.DataFrame(session_rows), width="stretch", height=320)

    all_trades = [
        t for trades in result.instrument_results.values() for t in trades
    ]

    empty_metrics = {"profit_factor": None, "win_rate": 0.0, "by_instrument": {}}

    if not all_trades:
        briefing = _build_briefing(all_trades_payload=[], metrics_payload=empty_metrics)
        _render_operator_card(briefing)

        reason_counts = {}
        for summaries in result.session_summaries.values():
            for summary in summaries:
                for reason in summary.rejection_reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

        st.warning(
            "The backtest completed but produced no trades.  "
            "Check date range, pre-session selection, filters, and data availability. "
            "Validation warnings (if any) are shown below."
        )

        if reason_counts:
            sorted_reasons = sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)
            st.caption("Most common no-trade reasons in this run:")
            for reason, count in sorted_reasons[:5]:
                st.write(f"- {reason}: {count}")

        for w in result.validation_warnings:
            st.warning(w)

        st.subheader("Strategic Briefing")
        _render_briefing_download(briefing, key_suffix="no_trade")
        st.markdown(f"**The Strategy's Pulse**\n\n{briefing['strategy_pulse']}")
        st.markdown("**Strategic Focus**")
        for line in briefing["strategic_focus"]:
            st.write(f"- {line}")
        st.markdown("**System Standards (Auto-Enforced)**")
        for line in briefing["system_standards"]:
            st.write(f"- {line}")
        st.markdown("**Dashboard Calibration Recommendations**")
        for line in briefing["settings_calibration"]:
            st.write(f"- {line}")
        _render_symbol_reasoning(briefing, key_suffix="no_trade")
        if briefing.get("equity_actions"):
            st.markdown("**Equities Requiring Action**")
            for line in briefing["equity_actions"]:
                st.write(f"- {line}")

        _render_execution_diagnostics(exec_log_path)

        diagnostics_csv = recorder.directory / "execution_diagnostics.csv"
        if diagnostics_csv.exists():
            st.download_button(
                "Execution Diagnostics (CSV)",
                data=diagnostics_csv.read_bytes(),
                file_name="execution_diagnostics.csv",
                mime="text/csv",
                key="download_exec_diagnostics_no_trade",
            )
        return

    comparison = compare_targets(all_trades, cfg["account"]["starting_capital"])
    metrics_2r = comparison["2r"]
    metrics_3r = comparison["3r"]
    briefing = _build_briefing(all_trades_payload=all_trades, metrics_payload=metrics_2r)

    _render_operator_card(briefing)

    if result.validation_warnings:
        with st.expander("Data Validation Warnings"):
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
        width="stretch",
    )

    mode_fig = mode_bar_chart(metrics_2r)
    if mode_fig:
        st.plotly_chart(mode_fig, width="stretch")

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

            st.dataframe(pd.DataFrame(recent_weeks), width="stretch", hide_index=True)
        else:
            st.caption("No saved weekly history found yet for the long-view summary.")
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

        st.dataframe(filtered, width="stretch", height=400)

    st.subheader("Strategic Briefing")
    _render_briefing_download(briefing, key_suffix="with_trades")
    st.markdown(f"**The Strategy's Pulse**\n\n{briefing['strategy_pulse']}")
    st.markdown("**Strategic Focus**")
    for line in briefing["strategic_focus"]:
        st.write(f"- {line}")
    st.markdown("**System Standards (Auto-Enforced)**")
    for line in briefing["system_standards"]:
        st.write(f"- {line}")
    st.markdown("**Dashboard Calibration Recommendations**")
    for line in briefing["settings_calibration"]:
        st.write(f"- {line}")
    _render_symbol_reasoning(briefing, key_suffix="with_trades")
    if briefing.get("equity_actions"):
        st.markdown("**Equities Requiring Action**")
        for line in briefing["equity_actions"]:
            st.write(f"- {line}")

    st.subheader("Download Results")
    dl1, dl2, dl3, dl4 = st.columns(4)
    trade_log_path = recorder.directory / "trade_log.csv"
    if trade_log_path.exists():
        dl1.download_button(
            "Trade Log (CSV)",
            data=trade_log_path.read_bytes(),
            file_name="trade_log.csv",
            mime="text/csv",
            key="download_trade_log",
        )

    if report_path.exists():
        dl2.download_button(
            "Run Report (TXT)",
            data=report_path.read_bytes(),
            file_name="run_report.txt",
            mime="text/plain",
            key="download_run_report",
        )

    if exec_log_path.exists():
        dl3.download_button(
            "Execution Log (JSON)",
            data=exec_log_path.read_bytes(),
            file_name="execution_log.json",
            mime="application/json",
            key="download_exec_log",
        )

    diagnostics_csv = recorder.directory / "execution_diagnostics.csv"
    if diagnostics_csv.exists():
        dl4.download_button(
            "Execution Diagnostics (CSV)",
            data=diagnostics_csv.read_bytes(),
            file_name="execution_diagnostics.csv",
            mime="text/csv",
            key="download_exec_diagnostics",
        )

    _render_execution_diagnostics(exec_log_path)

    selection_json = recorder.directory / "selection_snapshot.json"
    selection_csv = recorder.directory / "selection_snapshot.csv"
    selection_report = recorder.directory / "selection_report.txt"
    if selection_json.exists() or selection_csv.exists() or selection_report.exists():
        st.subheader("Pre-Session Artifacts")
        s1, s2, s3 = st.columns(3)
        if selection_json.exists():
            s1.download_button(
                "Selection Snapshot (JSON)",
                data=selection_json.read_bytes(),
                file_name="selection_snapshot.json",
                mime="application/json",
                key="download_selection_json",
            )
        if selection_csv.exists():
            s2.download_button(
                "Selection Snapshot (CSV)",
                data=selection_csv.read_bytes(),
                file_name="selection_snapshot.csv",
                mime="text/csv",
                key="download_selection_csv",
            )
        if selection_report.exists():
            s3.download_button(
                "Selection Report (TXT)",
                data=selection_report.read_bytes(),
                file_name="selection_report.txt",
                mime="text/plain",
                key="download_selection_report",
            )

    st.caption(f"Results saved to: `{recorder.directory}`")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    st.sidebar.markdown("### Automation")
    st.sidebar.caption(
        "Background updates run every 15 minutes during 09:25–11:00 ET through the scheduled task."
    )

    query_auto = st.query_params.get("auto_refresh", "1")
    if isinstance(query_auto, list):
        query_auto = query_auto[0]
    default_auto_refresh = str(query_auto).lower() not in {"0", "false", "no", "off"}

    auto_refresh_enabled = st.sidebar.checkbox(
        "Auto-refresh page",
        value=default_auto_refresh,
        help="Reload the interface every 15 minutes so the latest background run appears automatically.",
        key="pref_auto_refresh",
    )
    auto_refresh_param = "1" if auto_refresh_enabled else "0"
    if st.query_params.get("auto_refresh") != auto_refresh_param:
        st.query_params["auto_refresh"] = auto_refresh_param

    if auto_refresh_enabled:
        enable_dashboard_auto_refresh(15)
    st.sidebar.caption("Use `Run Backtest` below if you want an immediate update right now.")

    page_labels = {
        "pulse": "🏠 PulseTrader",
        "results": "🗂️ Results Manager",
        "backtest": "📊 Backtest",
        "guide": "📘 How it works",
    }
    page_keys = list(page_labels.keys())
    query_page = st.query_params.get("page", "pulse")
    if isinstance(query_page, list):
        query_page = query_page[0]
    if query_page not in page_labels:
        query_page = "pulse"

    selected_label = st.radio(
        "Page",
        options=[page_labels[k] for k in page_keys],
        index=page_keys.index(query_page),
        horizontal=True,
        label_visibility="collapsed",
    )
    selected_page = next(k for k, v in page_labels.items() if v == selected_label)
    if st.query_params.get("page") != selected_page:
        st.query_params["page"] = selected_page

    if selected_page == "pulse":
        render_home()

    elif selected_page == "backtest":
        st.title("PulseTrader Backtester")
        st.caption(
            "A selection-driven opening-range strategy with pre-session Top-N ranking, "
            "retest/gap trend entries, and automated risk management."
        )
        st.caption("Weekly results are monitoring signals, not final conclusions.")

        default_cfg = load_default_config()
        cfg, start_date, end_date = build_sidebar(default_cfg)

        st.sidebar.markdown("### Manual Update")
        run_button = st.sidebar.button("Run Backtest", type="primary", width="stretch")

        if run_button:
            if not cfg["instruments"]["equities"] and not cfg["instruments"].get("forex_csv_files"):
                st.error("Please configure at least one symbol in the master universe before running.")
                return

            if start_date >= end_date:
                st.error("Start date must be before end date.")
                return

            with st.spinner("Loading market data and updating the view..."):
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
            st.markdown(
                """
                <div class="soft-panel">
                    <strong>Start here.</strong> Configure your parameters in the sidebar and press <strong>Run Backtest</strong> to begin.<br><br>
                    <strong>Selection model:</strong> The tracked universe defines the full instrument pool. If pre-session selection is enabled, only the session Top-N selection is traded for that run.<br><br>
                    <strong>Data sources:</strong> Equities are fetched automatically from Yahoo Finance. For Forex instruments, place OHLCV CSV files in <code>data_files/</code> and add them to <code>config/settings.yaml</code>.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            render_results(
                last_run["cfg"],
                last_run["result"],
                last_run["recorder"],
                last_run["report_path"],
                last_run["exec_log_path"],
            )

    elif selected_page == "results":
        render_results_manager()

    else:
        render_how_it_works()


if __name__ == "__main__":
    main()
