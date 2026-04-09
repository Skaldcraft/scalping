"""
journal/strategic_briefing.py
============================
Narrative translation layer that turns mechanical run outputs into a
senior strategic briefing for the PulseTrader pilot.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from data.models import SessionSummary, TradeResult


def build_strategic_briefing(
    all_trades: List[TradeResult],
    session_summaries: Dict[str, List[SessionSummary]],
    metrics_2r: dict,
    config: Optional[dict] = None,
) -> dict:
    summaries = [s for v in session_summaries.values() for s in v]
    total_sessions = len(summaries)

    def _get(s, attr: str, default):
        return getattr(s, attr, default)

    def _is_equity_symbol(sym: str) -> bool:
        s = sym.upper().strip()
        if not s:
            return False
        if s in {"SPY", "QQQ"}:
            return False
        if "=X" in s or "/" in s:
            return False
        return True

    pf = metrics_2r.get("profit_factor")
    wr = float(metrics_2r.get("win_rate", 0.0))

    slingshot_count = sum(1 for s in summaries if bool(_get(s, "retest_confirmed", False)))
    displacement_count = sum(
        1 for s in summaries if str(_get(s, "trigger_candle", "") or "").lower() == "displacement_gap"
    )

    rejection_text = [r for s in summaries for r in (_get(s, "rejection_reasons", []) or [])]
    chop_signals = sum(1 for r in rejection_text if r in ("no_signal_found", "invalid_dynamic_stop"))
    chop_ratio = (chop_signals / total_sessions) if total_sessions else 0.0
    manipulation_sessions = sum(1 for s in summaries if bool(_get(s, "manipulation_flagged", False)))
    manipulation_ratio = (manipulation_sessions / total_sessions) if total_sessions else 0.0

    forex_pairs = {"EURUSD", "EURUSD=X", "GBPUSD", "GBPUSD=X"}
    forex_sessions = [s for s in summaries if str(_get(s, "instrument", "")).upper() in forex_pairs]
    forex_dxy_confirm = sum(1 for s in forex_sessions if bool(_get(s, "dxy_filter_confirmed", False)))
    dxy_rate = (forex_dxy_confirm / len(forex_sessions)) if forex_sessions else 0.0

    trend_checked = [
        s
        for s in summaries
        if bool(_get(s, "trade_executed", False))
        or any(r.startswith("trend_not_aligned") for r in (_get(s, "rejection_reasons", []) or []))
    ]
    trend_aligned_count = sum(1 for s in trend_checked if bool(_get(s, "trend_aligned", False)))
    trend_rate = (trend_aligned_count / len(trend_checked)) if trend_checked else 0.0

    if pf is None:
        pf_clause = "Profit Factor is still too early to tell if the strategy is hitting its stride yet."
    elif pf < 1.5:
        pf_clause = (
            f"Profit Factor at {pf:.2f} tells us our wins are not quite covering our losses yet, "
            "so this tape is still inefficient for our rules."
        )
    else:
        pf_clause = (
            f"Profit Factor at {pf:.2f} suggests the strategy is starting to hit its stride, "
            "with clearer institutional footprints on the board."
        )

    if 0.47 <= wr <= 0.53:
        wr_clause = (
            f"Win rate near {wr*100:.1f}% still looks like a coin flip, "
            "which means timing has not locked into a repeatable rhythm yet."
        )
    elif wr > 0.53:
        wr_clause = f"Win rate at {wr*100:.1f}% indicates execution quality is stabilizing above random flow."
    else:
        wr_clause = f"Win rate at {wr*100:.1f}% is below comfort, which means timing remains out of sync with session rhythm."

    if slingshot_count > displacement_count:
        pattern_clause = (
            "The homepage is showing more 'market bouncing off a wall' behavior than 'breaking through a door' behavior, "
            "so patience around confirmed retests is paying better than chasing first impulses."
        )
    elif displacement_count > slingshot_count:
        pattern_clause = (
            "The tape is printing more 'breaking through a door' moves than bounces, "
            "which usually means momentum is real and not just noise."
        )
    else:
        pattern_clause = (
            "Retest and displacement frequency are balanced, so the session is rotating between continuation and hesitation."
        )

    if chop_ratio >= 0.35:
        midpoint_clause = (
            "Price behavior is chopping through opening-range midpoint structure often enough to warn that spread and noise "
            "can erode the edge if entries are forced."
        )
    else:
        midpoint_clause = (
            "Opening-range midpoint behavior is relatively disciplined, suggesting better respect for structural levels."
        )

    if forex_sessions and dxy_rate >= 0.60:
        dxy_clause = (
            "DXY is acting like a strong current in the river, and that momentum is making forex continuation setups cleaner."
        )
    elif forex_sessions:
        dxy_clause = (
            "DXY influence is mixed right now, so forex momentum bursts exist but lack persistent follow-through."
        )
    else:
        dxy_clause = "Forex exposure is limited in this sample, so DXY context is not yet a dominant driver."

    if trend_rate >= 0.60:
        htf_clause = (
            "Higher-timeframe alignment is mostly supportive, so many 1-minute entries are trading with the wind at our back."
        )
    else:
        htf_clause = (
            "Higher-timeframe alignment is inconsistent, meaning many 1-minute setups are still fighting broader flow."
        )

    if manipulation_ratio >= 0.40:
        reversal_clause = (
            "A large share of sessions are printing overextended opening ranges, which often looks like big banks setting traps "
            "before an intraday flip."
        )
    else:
        reversal_clause = (
            "Opening ranges are not broadly overextended, so reversal pressure appears selective rather than market-wide."
        )

    strategy_pulse = " ".join(
        [
            pf_clause,
            wr_clause,
            pattern_clause,
            midpoint_clause,
            dxy_clause,
            htf_clause,
            reversal_clause,
            "The mission stays the same: no home runs, just consistent base hits when structure is clean.",
        ]
    )

    by_instrument = metrics_2r.get("by_instrument", {}) or {}
    sorted_syms = sorted(by_instrument.items(), key=lambda kv: kv[1].get("net_pnl", 0), reverse=True)
    top_symbol = sorted_syms[0][0] if sorted_syms else "N/A"

    traced_equities = sorted(
        {str(_get(s, "instrument", "")).upper() for s in summaries if _is_equity_symbol(str(_get(s, "instrument", "")))}
    )

    equity_actions: list[str] = []
    keep_symbols: list[str] = []
    reduce_symbols: list[str] = []
    standby_symbols: list[str] = []
    for sym in traced_equities:
        sym_rows = [s for s in summaries if str(_get(s, "instrument", "")).upper() == sym]
        sym_reasons = [r for s in sym_rows for r in (_get(s, "rejection_reasons", []) or [])]
        trend_mismatch = sum(1 for r in sym_reasons if str(r).startswith("trend_not_aligned"))
        no_signal = sum(1 for r in sym_reasons if str(r) == "no_signal_found")
        sym_stats = by_instrument.get(sym, {})
        sym_pnl = float(sym_stats.get("net_pnl", 0.0) or 0.0)

        if trend_mismatch > 0:
            equity_actions.append(f"{sym}: De-prioritize until higher-timeframe alignment returns.")
            reduce_symbols.append(sym)
        elif no_signal > 0 and sym_pnl <= 0:
            equity_actions.append(f"{sym}: Watch only; avoid forcing entries in chop.")
            standby_symbols.append(sym)
        elif sym_pnl > 0:
            equity_actions.append(f"{sym}: Keep in active rotation; structure is holding.")
            keep_symbols.append(sym)
        else:
            equity_actions.append(f"{sym}: Monitor for clean retest confirmation before activation.")
            standby_symbols.append(sym)

    traced_line = (
        "Traced equities: " + (", ".join(traced_equities) if traced_equities else "none in this sample")
    )

    if slingshot_count >= displacement_count:
        exec_focus = (
            "Execution: prioritize the Trend Continuation model by waiting for price to touch the boundary and turn without closing back inside."
        )
        execution_model = "Trend Continuation (Slingshot Retest)"
    else:
        exec_focus = (
            "Execution: prioritize clean displacement moves, but only when higher-timeframe flow is aligned so momentum is not fighting the bigger picture."
        )
        execution_model = "Displacement Continuation"

    if forex_sessions and dxy_rate >= 0.60:
        asset_focus = (
            "Asset focus: forex majors currently show the clearest momentum translation under dollar pressure; that context supports more consistent continuation behavior."
        )
    elif top_symbol in ("QQQ", "SPY"):
        asset_focus = (
            "Asset focus: index exposure is currently the steadier expression of trend, with less erratic liquidity than single-name tech bursts."
        )
    else:
        asset_focus = (
            f"Asset focus: keep priority on symbols showing stable footprint this run (current leader: {top_symbol}) and reduce exposure to names trapped in painful chop."
        )

    volatility_focus = (
        "Volatility check: when opening candles are stretched, treat that as potential trap behavior and respect the 25% ATR manipulation framework before forcing continuation entries."
    )

    standards = [
        "Risk Protection: The system already enforces position sizing so no single trade risks more than 1% of capital.",
        "Kill Switch: The system enforces a 5% daily loss limit as a non-negotiable safety baseline.",
        "Execution Discipline: The base-hit philosophy is always active, prioritizing repeatable small gains over oversized swings.",
    ]

    atr_threshold = float((config or {}).get("strategy", {}).get("manipulation_threshold_pct", 25.0))
    risk_pct_cfg = float((config or {}).get("account", {}).get("risk_per_trade_pct", 1.0))
    daily_loss_cfg = float((config or {}).get("account", {}).get("daily_loss_limit_pct", 5.0))

    if manipulation_ratio < 0.15 and slingshot_count > 0:
        atr_reco = (
            "ATR Manipulation Threshold: Consider testing 20% to 22% because reversal behavior appears without frequent manipulation-mode activation."
        )
    elif manipulation_ratio >= 0.40 and chop_ratio >= 0.30:
        atr_reco = (
            "ATR Manipulation Threshold: Keep 25% for now; large opening traps are present and a looser threshold may invite more fake reversals."
        )
    else:
        atr_reco = (
            f"ATR Manipulation Threshold: Keep at {atr_threshold:.0f}% while the current trap profile remains mixed."
        )

    if pf is None or pf < 1.0:
        risk_reco = (
            "Risk Per Trade: Keep at 1% or lower until results prove that wins are consistently paying for losses."
        )
    else:
        risk_reco = (
            f"Risk Per Trade: Maintain around {risk_pct_cfg:.1f}% while edge quality improves, avoiding any increase until Profit Factor stays above 1.5."
        )

    if chop_ratio >= 0.35:
        daily_reco = (
            "Daily Loss Limit: Keep the hard 5% system baseline, and consider a tighter 3% operating cap in choppy sessions to reduce drawdown."
        )
    else:
        daily_reco = (
            f"Daily Loss Limit: Maintain at {daily_loss_cfg:.0f}% as the standard safety protocol."
        )

    return {
        "strategy_pulse": strategy_pulse,
        "strategic_focus": [exec_focus, asset_focus, volatility_focus, traced_line],
        "system_standards": standards,
        "settings_calibration": [atr_reco, risk_reco, daily_reco],
        "equity_actions": equity_actions,
        "operator_card": {
            "execution_model": execution_model,
            "keep_symbols": keep_symbols,
            "reduce_symbols": reduce_symbols,
            "standby_symbols": standby_symbols,
            "atr_recommendation": atr_reco,
            "risk_recommendation": risk_reco,
            "daily_loss_recommendation": daily_reco,
        },
        # Backward-compatible keys for older renderers.
        "translation": strategy_pulse,
        "focus": [exec_focus, asset_focus, volatility_focus, traced_line],
    }
