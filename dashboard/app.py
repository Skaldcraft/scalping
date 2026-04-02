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
from risk.circuit_breaker import CircuitBreaker

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
            .stMarkdown a,
            .stCaption a {
                color: #b6862c !important;
            }
            section[data-testid="stSidebar"] a:hover,
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
GUIDE_PATH = Path(__file__).resolve().parent.parent / "BEGINNER_GUIDE.md"

@st.cache_resource
def load_default_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

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

    st.sidebar.subheader("Universe & Selection")
    default_equities = default_cfg["instruments"].get("equities", [])
    tracked_universe = tracked_universe_symbols(default_cfg)
    pre_cfg = default_cfg.get("pre_session", {}) or {}
    pre_rules = pre_cfg.get("selection_rules", {}) or {}

    pre_session_enabled = st.sidebar.checkbox(
        "Enable Pre-Session Top-N Selector",
        value=bool(pre_cfg.get("enabled", False)),
        help="When enabled, the run trades only the session selection (Top-N) instead of the full master universe list.",
    )
    selector_top_n = st.sidebar.number_input(
        "Top-N Symbols",
        min_value=1,
        max_value=10,
        value=int(pre_cfg.get("top_n", 3)),
        step=1,
    )
    freeze_daily = st.sidebar.checkbox(
        "Freeze Daily Selection",
        value=bool(pre_cfg.get("freeze_daily_selection", True)),
        help="Reuses the first computed selection for the same date on subsequent intraday runs.",
    )

    pf_missing_policy = st.sidebar.selectbox(
        "PF Missing Policy",
        options=["allow", "reject"],
        index=["allow", "reject"].index(str(pre_rules.get("pf_missing_policy", "allow"))),
        help="How to handle symbols with missing Profit Factor history.",
    )
    spread_missing_policy = st.sidebar.selectbox(
        "Spread Missing Policy",
        options=["allow", "reject"],
        index=["allow", "reject"].index(str(pre_rules.get("spread_missing_policy", "allow"))),
        help="How to handle symbols without spread data.",
    )

    pf_lookback_trades_raw = st.sidebar.number_input(
        "PF Lookback Trades (0 = all)",
        min_value=0,
        max_value=500,
        value=int(pre_rules.get("pf_lookback_trades") or 0),
        step=5,
    )
    pf_lookback_trades = None if pf_lookback_trades_raw == 0 else int(pf_lookback_trades_raw)

    with st.sidebar.expander("Legacy Behavior", expanded=False):
        legacy_require_pf = st.checkbox(
            "Legacy toggle: require PF history",
            value=bool(pre_rules.get("require_pf_history", False)),
        )
        legacy_require_spread = st.checkbox(
            "Legacy toggle: require spread data",
            value=bool(pre_rules.get("require_spread_data", False)),
        )

    st.sidebar.markdown("**Tracked Universe**")
    if tracked_universe:
        st.sidebar.caption(", ".join(tracked_universe))
    else:
        st.sidebar.caption("No tracked universe configured yet.")

    with st.sidebar.expander("Single Symbol Override", expanded=False):
        st.caption("Run one tracked symbol for this backtest only. Does not change saved config.")
        single_symbol_enabled = st.checkbox(
            "Use one tracked symbol",
            value=False,
        )
        single_symbol_input = st.text_input(
            "Tracked Symbol",
            value="",
            placeholder="AAPL",
            help="Enter one symbol from the tracked universe shown above.",
            disabled=not single_symbol_enabled,
        ).strip().upper()
        valid_single_symbol = single_symbol_input in tracked_universe if single_symbol_input else False
        if single_symbol_enabled and single_symbol_input and not valid_single_symbol:
            st.warning("Symbol not found in tracked universe.")
        if single_symbol_enabled and valid_single_symbol:
            st.success(f"Single-symbol run ready: {single_symbol_input}")

    st.session_state.setdefault("custom_symbols_raw", "")
    st.session_state.setdefault("selected_equities", list(default_equities or tracked_universe))
    with st.sidebar.expander("Research Overrides", expanded=False):
        st.caption("Use only for testing custom subsets. Normal runs use the tracked universe above.")
        research_override_enabled = st.checkbox(
            "Override universe for this run",
            value=False,
        )
        custom_symbols_raw = st.text_input(
            "Research Symbols",
            value=st.session_state["custom_symbols_raw"],
            placeholder="TSLA, AMD, INTC",
            help="Comma-separated symbols added only for research-mode runs.",
            disabled=not research_override_enabled,
        )
        custom_symbols = parse_custom_symbols(custom_symbols_raw)
        equity_options = list(dict.fromkeys([
            *tracked_universe,
            "AAPL", "NVDA", "AMZN", "MSFT", "GOOGL", "META", "QQQ", "SPY",
            *[sym.upper() for sym in default_equities],
            *custom_symbols,
        ]))
        equities = st.multiselect(
            "Research Universe",
            options=equity_options,
            default=st.session_state["selected_equities"],
            disabled=not research_override_enabled,
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

    trend_mode_cfg = (default_cfg.get("strategy", {}) or {}).get("trend_mode", {}) or {}
    allow_gap_entry = st.sidebar.checkbox(
        "Enable Displacement Gap Entries",
        value=bool(trend_mode_cfg.get("allow_displacement_gap_entry", True)),
    )
    entry_priority = st.sidebar.selectbox(
        "Trend Entry Priority",
        options=["retest_first", "gap_first"],
        index=["retest_first", "gap_first"].index(str(trend_mode_cfg.get("entry_priority", "retest_first"))),
    )
    displacement_min_atr_pct = st.sidebar.slider(
        "Gap Min Size (% of ATR14)",
        min_value=0.0,
        max_value=15.0,
        value=float(trend_mode_cfg.get("displacement_min_atr_pct", 3.0)),
        step=0.5,
    )
    displacement_min_body_pct = st.sidebar.slider(
        "Gap Bar Min Body (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(trend_mode_cfg.get("displacement_min_body_pct", 60.0)),
        step=5.0,
    )

    session_end = "11:00"
    st.sidebar.caption("Session Gate is fixed at 11:00 ET for alignment with automation.")

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

    cfg.setdefault("pre_session", {})["enabled"] = pre_session_enabled
    cfg["pre_session"]["top_n"] = int(selector_top_n)
    cfg["pre_session"]["freeze_daily_selection"] = freeze_daily
    cfg["pre_session"].setdefault("selection_rules", {})
    cfg["pre_session"]["selection_rules"]["pf_missing_policy"] = pf_missing_policy
    cfg["pre_session"]["selection_rules"]["spread_missing_policy"] = spread_missing_policy
    cfg["pre_session"]["selection_rules"]["pf_lookback_trades"] = pf_lookback_trades
    cfg["pre_session"]["selection_rules"]["require_pf_history"] = legacy_require_pf
    cfg["pre_session"]["selection_rules"]["require_spread_data"] = legacy_require_spread

    cfg["session"]["end_time"]   = session_end
    cfg["commissions"]["per_trade_flat"] = commission
    if single_symbol_enabled and valid_single_symbol:
        cfg["instruments"]["equities"] = [single_symbol_input]
        cfg["instruments"]["custom_symbols"] = []
    elif research_override_enabled:
        cfg["instruments"]["equities"] = equities
        cfg["instruments"]["custom_symbols"] = custom_symbols
    else:
        cfg["instruments"]["equities"] = tracked_universe or default_equities
        cfg["instruments"]["custom_symbols"] = []

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

    trade_logs = sorted(results_dir.rglob("trade_log.csv")) if results_dir.exists() else []
    for trade_log in trade_logs:
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
        st.plotly_chart(_sparkline_figure(overall, "Portfolio Weekly Net P&L"), width="stretch")
    else:
        st.info("No weekly data yet for the portfolio overview.")

    if not symbols:
        st.info("No master-universe symbols configured yet.")
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
                st.info("No data yet")


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
        else:
            st.info("No weekly batch report found yet.")

    st.divider()
    st.write("Use the tabs above to move between `PulseTrader`, `Backtest`, and `How it works`.")


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
            st.info("Most common no-trade reasons in this run:")
            for reason, count in sorted_reasons[:5]:
                st.write(f"- {reason}: {count}")

        for w in result.validation_warnings:
            st.warning(w)
        return

    comparison = compare_targets(all_trades, cfg["account"]["starting_capital"])
    metrics_2r = comparison["2r"]
    metrics_3r = comparison["3r"]

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

        st.dataframe(filtered, width="stretch", height=400)

    st.subheader("Download Results")
    dl1, dl2, dl3 = st.columns(3)
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
    auto_refresh_enabled = st.sidebar.checkbox(
        "Auto-refresh page",
        value=True,
        help="Reload the interface every 15 minutes so the latest background run appears automatically.",
    )
    if auto_refresh_enabled:
        enable_dashboard_auto_refresh(15)
    st.sidebar.caption("Use `Run Backtest` below if you want an immediate update right now.")

    page_labels = {
        "pulse": "🏠 PulseTrader",
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

    else:
        render_how_it_works()


if __name__ == "__main__":
    main()
