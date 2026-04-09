"""
journal/strategic_briefing.py
============================
Narrative translation layer that turns mechanical run outputs into a
senior strategic briefing for the PulseTrader pilot.
"""

from __future__ import annotations

from typing import Dict, List

from data.models import SessionSummary, TradeResult


def build_strategic_briefing(
    all_trades: List[TradeResult],
    session_summaries: Dict[str, List[SessionSummary]],
    metrics_2r: dict,
) -> dict:
    summaries = [s for v in session_summaries.values() for s in v]
    total_sessions = len(summaries)

    def _get(s, attr: str, default):
        return getattr(s, attr, default)

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
        pf_clause = "Profit Factor is not yet stable enough to classify the edge."
    elif pf < 1.5:
        pf_clause = f"Profit Factor at {pf:.2f} shows an unrewarding, inefficient tape for our mechanical rules."
    else:
        pf_clause = f"Profit Factor at {pf:.2f} suggests the institutional footprint is increasingly readable for base-hit execution."

    if 0.47 <= wr <= 0.53:
        wr_clause = (
            f"Win rate near {wr*100:.1f}% still reflects a coin-flip environment, "
            "so edge quality is not fully defined yet."
        )
    elif wr > 0.53:
        wr_clause = f"Win rate at {wr*100:.1f}% indicates execution quality is stabilizing above random flow."
    else:
        wr_clause = f"Win rate at {wr*100:.1f}% is below comfort, which means timing remains out of sync with session rhythm."

    if slingshot_count > displacement_count:
        pattern_clause = (
            "Homepage behavior is showing more slingshot effect retests than raw displacement, "
            "which favors patient boundary confirmation over breakout chasing."
        )
    elif displacement_count > slingshot_count:
        pattern_clause = (
            "The tape is printing more clean 1-minute displacement than retest cycles, "
            "a sign momentum legs are currently carrying genuine intent."
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
            "DXY context is acting as a directional anchor, and that momentum is creating a cleaner path for forex slingshot continuations."
        )
    elif forex_sessions:
        dxy_clause = (
            "DXY influence is mixed right now, so forex momentum bursts exist but lack persistent follow-through."
        )
    else:
        dxy_clause = "Forex exposure is limited in this sample, so DXY context is not yet a dominant driver."

    if trend_rate >= 0.60:
        htf_clause = (
            "Higher-timeframe alignment is generally supportive, so 1-minute entries are more often trading with the big-picture current."
        )
    else:
        htf_clause = (
            "Higher-timeframe alignment is inconsistent, meaning many 1-minute setups are still fighting broader flow."
        )

    if manipulation_ratio >= 0.40:
        reversal_clause = (
            "A meaningful share of sessions are printing overextended opening ranges, which is consistent with liquidity engineering "
            "before potential intraday flips in individual names."
        )
    else:
        reversal_clause = (
            "Opening ranges are not broadly overextended, so reversal pressure appears selective rather than market-wide."
        )

    translation = " ".join(
        [
            pf_clause,
            wr_clause,
            pattern_clause,
            midpoint_clause,
            dxy_clause,
            htf_clause,
            reversal_clause,
            "The strategic posture remains base-hit focused: protect capital while waiting for cleaner liquidity engineering and repeatable structure.",
        ]
    )

    by_instrument = metrics_2r.get("by_instrument", {}) or {}
    sorted_syms = sorted(by_instrument.items(), key=lambda kv: kv[1].get("net_pnl", 0), reverse=True)
    top_symbol = sorted_syms[0][0] if sorted_syms else "N/A"

    if slingshot_count >= displacement_count:
        exec_focus = (
            "Execution focus: favor confirmed retests at range boundaries; in this regime the slingshot effect is delivering cleaner institutional confirmation."
        )
    else:
        exec_focus = (
            "Execution focus: prioritize clean displacement with immediate intent, but only when higher-timeframe alignment is not fighting the move."
        )

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

    discipline_focus = (
        "Discipline focus: keep the 5% circuit-breaker and fixed 1% risk sizing as non-negotiable guardrails until Profit Factor reclaims and holds above 1.5."
    )

    return {
        "translation": translation,
        "focus": [exec_focus, asset_focus, discipline_focus],
    }
