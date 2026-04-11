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
    reasoning_memory: Optional[Dict[str, str]] = None,
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

    def _reason_from_rejections(reasons: List[str], manipulation_flagged: bool) -> str:
        if manipulation_flagged:
            return (
                "The system detected an institutional footprint. Big players are likely engineering liquidity, "
                "setting a trap before the opposite move proves itself."
            )
        if any(str(r).startswith("trend_not_aligned") for r in reasons):
            return (
                "The setup was skipped because the bigger trend did not support the smaller move, "
                "so we did not have the wind at our back."
            )
        if "displacement_gap_min_size_not_met" in reasons or "displacement_gap_min_body_not_met" in reasons:
            return (
                "The system detected a potential move, but the footprint was too light; "
                "candle body strength or displacement size did not show solid institutional intent."
            )
        if "no_signal_found" in reasons:
            return "No clean trigger reached confirmation quality, so the utility stayed patient and protected capital."
        if "outside_fib_zone" in reasons:
            return "Price was outside the preferred value zone, so the system avoided chasing extended movement."
        return "No execution-quality setup completed the full confirmation chain in this session."

    pf = metrics_2r.get("profit_factor")
    wr = float(metrics_2r.get("win_rate", 0.0))

    slingshot_count = sum(1 for s in summaries if bool(_get(s, "retest_confirmed", False)))
    displacement_count = sum(
        1 for s in summaries if str(_get(s, "trigger_candle", "") or "").lower() == "displacement_gap"
    )
    mean_reversion_count = sum(
        1 for s in summaries if str(_get(s, "mode_activated", "")).lower() == "mean_reversion"
    )

    rejection_text = [r for s in summaries for r in (_get(s, "rejection_reasons", []) or [])]
    chop_signals = sum(1 for r in rejection_text if r in ("no_signal_found", "invalid_dynamic_stop"))
    trend_mismatch_count = sum(1 for r in rejection_text if str(r).startswith("trend_not_aligned"))
    gap_size_rejections = sum(1 for r in rejection_text if r == "displacement_gap_min_size_not_met")
    gap_body_rejections = sum(1 for r in rejection_text if r == "displacement_gap_min_body_not_met")
    chop_ratio = (chop_signals / total_sessions) if total_sessions else 0.0
    manipulation_sessions = sum(1 for s in summaries if bool(_get(s, "manipulation_flagged", False)))
    manipulation_ratio = (manipulation_sessions / total_sessions) if total_sessions else 0.0
    fakeout_ratio = ((trend_mismatch_count + chop_signals) / total_sessions) if total_sessions else 0.0

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
            "The market printed more touch-and-turn confirmations than raw gap continuations. "
            "That means the Slingshot effect is dominant: price double-checked the boundary before snapping forward."
        )
    elif displacement_count > slingshot_count:
        pattern_clause = (
            "The market showed repeated displacement behavior, breaking through the door without looking back, "
            "which signals aggressive institutional momentum."
        )
    else:
        pattern_clause = (
            "Retest and displacement frequency are balanced, so the session is rotating between continuation and hesitation."
        )

    if chop_ratio >= 0.35:
        midpoint_clause = (
            "Price behavior is chopping through opening-range midpoint structure often enough to warn that spread and noise "
            "can erode the edge if entries are forced, with extra price friction around entries and exits."
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
            "A large share of sessions are printing overextended opening ranges, which often looks like institutional engineering "
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
    symbol_reasoning: dict[str, str] = dict(reasoning_memory or {})
    for sym in traced_equities:
        sym_rows = [s for s in summaries if str(_get(s, "instrument", "")).upper() == sym]
        sym_reasons = [r for s in sym_rows for r in (_get(s, "rejection_reasons", []) or [])]
        sym_manip = any(bool(_get(s, "manipulation_flagged", False)) for s in sym_rows)
        trend_mismatch = sum(1 for r in sym_reasons if str(r).startswith("trend_not_aligned"))
        no_signal = sum(1 for r in sym_reasons if str(r) == "no_signal_found")
        sym_stats = by_instrument.get(sym, {})
        sym_pnl = float(sym_stats.get("net_pnl", 0.0) or 0.0)
        if sym not in symbol_reasoning:
            symbol_reasoning[sym] = _reason_from_rejections(sym_reasons, sym_manip)

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
            "System calibration: favor patient boundary confirmation because touch-and-turn retests are currently giving cleaner follow-through than impulse chasing."
        )
        execution_model = "Trend Continuation (Slingshot Retest)"
    else:
        exec_focus = (
            "System calibration: favor displacement continuation only when momentum is clean and higher-timeframe alignment confirms institutional direction."
        )
        execution_model = "Displacement Continuation"

    if forex_sessions and dxy_rate >= 0.60:
        asset_focus = (
            "System calibration: forex majors currently show the clearest momentum translation under dollar pressure; that context supports more consistent continuation behavior."
        )
    elif top_symbol in ("QQQ", "SPY"):
        asset_focus = (
            "System calibration: index exposure is currently the steadier expression of trend, with less erratic liquidity than single-name tech bursts."
        )
    else:
        asset_focus = (
            f"System calibration: the cleanest footprint this run is centered on {top_symbol}; broader symbol spread can stay tighter while chop remains elevated."
        )

    volatility_focus = (
        "System calibration: when opening candles are stretched, treat that as potential institutional engineering and anchor decisions to the ATR manipulation framework before continuation entries."
    )

    standards = [
        "Risk Protection: The system already enforces position sizing so no single trade risks more than 1% of capital.",
        "Kill Switch: The system's safety protocols remain locked at 5% to protect base hits during choppy phases.",
        "Execution Discipline: The base-hit philosophy is always active, prioritizing repeatable small gains over oversized swings.",
    ]

    atr_threshold = float((config or {}).get("strategy", {}).get("manipulation_threshold_pct", 25.0))
    risk_pct_cfg = float((config or {}).get("account", {}).get("risk_per_trade_pct", 1.0))
    daily_loss_cfg = float((config or {}).get("account", {}).get("daily_loss_limit_pct", 5.0))

    if manipulation_ratio < 0.15 and mean_reversion_count > 0:
        atr_reco = (
            "ATR Manipulation Threshold: The current traps appear shallow; a 20% to 22% setting may capture high-probability flips that sit just under the default 25% trigger."
        )
    elif manipulation_ratio >= 0.40 and chop_ratio >= 0.30:
        atr_reco = (
            "ATR Manipulation Threshold: Keep 25% to 30% while trap frequency is elevated so the utility avoids false reversal activation in noisy sessions."
        )
    else:
        atr_reco = (
            f"ATR Manipulation Threshold: Keep at {atr_threshold:.0f}% while the current institutional engineering profile remains mixed."
        )

    entry_priority = str((config or {}).get("strategy", {}).get("trend_mode", {}).get("entry_priority", "retest_first"))
    if entry_priority == "retest_first" and slingshot_count > 0:
        execution_interpretation = (
            "The system used the Slingshot effect-waiting for the market to touch our level and turn-which confirmed the banks were really behind the move."
        )
        execution_reco = (
            "Execution Mode: The system used the Slingshot effect-waiting for the market to touch our level and turn-which confirmed the banks were really behind the move."
        )
    elif fakeout_ratio >= 0.35:
        execution_interpretation = (
            "Execution currently benefits from stronger confirmation before commitment, with retest behavior reducing exposure to stop-hunt noise."
        )
        execution_reco = (
            "Execution Mode: Current conditions are favoring stronger confirmation; leaning on retest_first can help the market prove intent before capital is exposed."
        )
    else:
        execution_interpretation = (
            "Execution remains balanced across displacement and retest confirmations while trend alignment drives quality."
        )
        execution_reco = (
            "Execution Mode: Current conditions support balanced use of displacement and retest logic while higher-timeframe alignment remains the primary quality gate."
        )

    disp_min_atr_pct = float((config or {}).get("strategy", {}).get("trend_mode", {}).get("displacement_min_atr_pct", 0))
    disp_min_body_pct = float((config or {}).get("strategy", {}).get("trend_mode", {}).get("displacement_min_body_pct", 0))

    if gap_size_rejections > 0 or gap_body_rejections > 0:
        gap_interpretation = (
            "The system detected a potential move, but the 'footprint' was too light. "
            "We avoided a potential trap because the candle did not show enough solid institutional power (body) or size (ATR%)."
        )
        gap_precision_reco = (
            f"Gap Precision: The system detected a potential move, but the 'footprint' was too light. "
            f"We avoided a potential trap because the candle did not show enough solid institutional power (body) or size (ATR%)."
        )
    elif fakeout_ratio >= 0.35 and wr < 0.50:
        gap_interpretation = (
            "The current market is favoring more solid confirmation; waiting for a larger gap or a cleaner candle body may help filter out these traps."
        )
        gap_precision_reco = (
            f"Gap Precision: The current market is favoring more solid confirmation; waiting for a larger gap or a cleaner candle body may help filter out these traps."
        )
    else:
        parts = []
        if disp_min_atr_pct > 0:
            parts.append(f"gaps under {disp_min_atr_pct:.0f}% of ATR are held out")
        if disp_min_body_pct > 0:
            parts.append(f"candles with body under {disp_min_body_pct:.0f}% of range are held out")
        if parts:
            filter_detail = "; " + ", ".join(parts) + "."
        else:
            filter_detail = ""

        gap_interpretation = (
            "No weak displacement candidates reached the entry window this period. "
            f"The configured gates kept the chart clear of noise.{filter_detail}"
        )
        gap_precision_reco = (
            "Gap Precision: No adjustment needed — the current displacement gates are holding noise out without blocking valid setups."
        )

    fakeout_interpretation = None
    if fakeout_ratio >= 0.35 and wr < 0.50:
        fakeout_interpretation = (
            "The current market is favoring more solid confirmation; waiting for a larger gap or a cleaner candle body may help filter out these traps."
        )

    if pf is None or pf < 1.5:
        risk_reco = (
            "Risk Parameters: The system continues to enforce the 1% risk-per-trade baseline; this remains the correct calibration while Profit Factor is not yet consistently above 1.5."
        )
    else:
        risk_reco = (
            f"Risk Parameters: The system remains anchored around {risk_pct_cfg:.1f}% risk per trade, preserving consistency while edge quality continues to stabilize."
        )

    if chop_ratio >= 0.35 or (pf is not None and pf < 1.0):
        daily_reco = (
            "Daily Loss Limit: The 5% cap remains a non-negotiable system guardrail; in painful sessions, a 3% operating cap can reduce drawdown while preserving capital."
        )
    else:
        daily_reco = (
            f"Daily Loss Limit: The system's safety protocols remain locked at {daily_loss_cfg:.0f}% as the active baseline guardrail."
        )

    asset_calibration = (
        "Asset Focus: Keep attention on symbols with the cleanest footprints and tighten Top-N breadth when broad participation becomes inconsistent."
    )

    return {
        "strategy_pulse": strategy_pulse,
        "strategic_focus": [exec_focus, asset_focus, volatility_focus, traced_line],
        "system_standards": standards,
        "settings_calibration": [atr_reco, execution_reco, gap_precision_reco, risk_reco, daily_reco, asset_calibration],
        "equity_actions": equity_actions,
        "symbol_reasoning": symbol_reasoning,
        "operator_card": {
            "execution_model": execution_model,
            "keep_symbols": keep_symbols,
            "reduce_symbols": reduce_symbols,
            "standby_symbols": standby_symbols,
            "execution_interpretation": execution_interpretation,
            "gap_interpretation": gap_interpretation,
            "fakeout_interpretation": fakeout_interpretation,
            "atr_recommendation": atr_reco,
            "risk_recommendation": risk_reco,
            "daily_loss_recommendation": daily_reco,
        },
        # Backward-compatible keys for older renderers.
        "translation": strategy_pulse,
        "focus": [exec_focus, asset_focus, volatility_focus, traced_line],
    }
