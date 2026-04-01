"""
journal/run_report.py
=====================
Generates an objective, third-person prose narrative describing what the
Precision Scalping Utility did during a backtesting run.

The report is written as a factual record of the utility's behaviour,
covering scope, mode activation, signal filtering, circuit-breaker events,
and a comparative summary of 2R vs 3R performance.  It is designed to
serve as a readable audit trail and as an input for identifying
improvements across successive versions.

Output: plain-text file saved to results/<run>/run_report.txt
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from data.models import TradeResult, SessionSummary


def generate_run_report(
    instrument_results:  Dict[str, List[TradeResult]],
    session_summaries:   Dict[str, List[SessionSummary]],
    metrics_2r:          dict,
    metrics_3r:          dict,
    circuit_halt_events: List[dict],
    config:              dict,
    start_date:          str,
    end_date:            str,
    version:             str,
    run_dir:             Path,
) -> Path:
    """
    Composes and writes the run report.  Returns the path to the saved file.
    """
    lines = _compose(
        instrument_results, session_summaries, metrics_2r, metrics_3r,
        circuit_halt_events, config, start_date, end_date, version,
    )

    path = run_dir / "run_report.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def _compose(
    instrument_results, session_summaries, metrics_2r, metrics_3r,
    circuit_halt_events, config, start_date, end_date, version,
) -> List[str]:

    all_trades = [t for trades in instrument_results.values() for t in trades]
    all_summaries = [s for sums in session_summaries.values() for s in sums]
    instruments   = list(instrument_results.keys())
    generated_at  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "=" * 72,
        "PRECISION SCALPING UTILITY — BACKTEST RUN REPORT",
        f"Version: {version}",
        f"Generated: {generated_at}",
        "=" * 72,
        "",

        # ------------------------------------------------------------------
        "1. RUN SCOPE",
        "-" * 40,
    ]

    lines += [
        f"The utility evaluated trading sessions between {start_date} and "
        f"{end_date} across {len(instruments)} instrument(s): "
        f"{', '.join(instruments)}.",
        "",
        f"The opening range was defined by the first "
        f"{config['opening_range']['candle_size_minutes']}-minute candle of "
        f"each New York session (9:30 AM ET).  The active trading window "
        f"extended to {config['session']['end_time']} ET.",
        "",
        f"Starting capital: ${config['account']['starting_capital']:,.2f}.  "
        f"Risk per trade: {config['account']['risk_per_trade_pct']}% of "
        f"current equity.  Commission per trade: "
        f"${config['commissions']['per_trade_flat']:.2f}.",
        "",
    ]

    # ------------------------------------------------------------------
    lines += ["2. SESSION ACTIVITY BY INSTRUMENT", "-" * 40]

    for sym in instruments:
        sym_summaries = session_summaries.get(sym, [])
        sym_trades    = instrument_results.get(sym, [])
        total_sessions = len(sym_summaries)
        traded_sessions = sum(1 for s in sym_summaries if s.trade_executed)
        no_trade_sessions = total_sessions - traded_sessions

        breakout_sessions    = sum(1 for s in sym_summaries if s.mode_activated == "breakout")
        manipulation_sessions = sum(1 for s in sym_summaries if s.mode_activated == "manipulation")
        mr_sessions          = sum(1 for s in sym_summaries if s.mode_activated == "mean_reversion")
        no_trade_mode        = sum(1 for s in sym_summaries if s.mode_activated == "no_trade")

        lines += [
            f"  {sym}:",
            f"    Total sessions evaluated  : {total_sessions}",
            f"    Sessions with a trade      : {traded_sessions}",
            f"    Sessions with no signal    : {no_trade_sessions}",
            f"    Breakout Mode activations  : {breakout_sessions}",
            f"    Manipulation Mode activations: {manipulation_sessions}",
            f"    Mean Reversion activations : {mr_sessions}",
            f"    No-Trade sessions          : {no_trade_mode}",
            "",
        ]

    # ------------------------------------------------------------------
    lines += ["3. SIGNAL FILTERING FUNNEL", "-" * 40]

    total_sessions = len(all_summaries)
    had_or         = sum(1 for s in all_summaries if s.or_high > 0)
    had_atr        = sum(1 for s in all_summaries if s.atr_14 > 0)
    manip_flagged  = sum(1 for s in all_summaries if s.manipulation_flagged)
    breakout_fired = sum(1 for s in all_summaries if s.breakout_signal_fired)
    retest_conf    = sum(1 for s in all_summaries if s.retest_confirmed)
    pattern_conf   = sum(1 for s in all_summaries if s.pattern_confirmed)
    trades_placed  = sum(1 for s in all_summaries if s.trade_executed)

    lines += [
        f"The following table describes how sessions progressed through the",
        f"utility's signal filtering pipeline across all instruments combined.",
        "",
        f"  Total sessions evaluated                 : {total_sessions}",
        f"  Sessions with a valid opening range      : {had_or}",
        f"  Sessions with sufficient ATR data        : {had_atr}",
        f"  Sessions flagged as manipulation candles : {manip_flagged} "
        f"({_pct(manip_flagged, had_atr)}% of ATR-valid sessions)",
        f"  Sessions with a breakout/MR signal       : {breakout_fired}",
        f"  Sessions where retest was confirmed      : {retest_conf}",
        f"  Sessions where reversal pattern confirmed: {pattern_conf}",
        f"  Trades executed                          : {trades_placed}",
        "",
        f"The overall signal-to-session ratio was {_pct(trades_placed, total_sessions)}%, "
        f"meaning the utility remained out of the market for "
        f"{100 - _pct(trades_placed, total_sessions)}% of all evaluated sessions, "
        f"consistent with the strategy's emphasis on high-probability setups.",
        "",
    ]

    # ------------------------------------------------------------------
    lines += ["4. CIRCUIT BREAKER EVENTS", "-" * 40]

    if not circuit_halt_events:
        lines += [
            "No circuit breaker events were triggered during this backtest run.",
            "",
        ]
    else:
        lines += [
            f"The circuit breaker was triggered {len(circuit_halt_events)} time(s) "
            f"during this run:",
            "",
        ]
        for i, evt in enumerate(circuit_halt_events, 1):
            lines += [
                f"  Event {i}: {evt.get('type', 'unknown').replace('_', ' ').title()}",
                f"    Session   : {evt.get('session', 'N/A')}",
                f"    Instrument: {evt.get('instrument', 'N/A')}",
                f"    Reason    : {evt.get('reason', 'N/A')}",
                "",
            ]

    # ------------------------------------------------------------------
    lines += ["5. PERFORMANCE SUMMARY", "-" * 40]

    def fmt_metrics(m: dict, label: str) -> List[str]:
        pf = m.get("profit_factor")
        sr = m.get("sharpe_ratio")
        return [
            f"  {label} Reward Target:",
            f"    Trades       : {m.get('total_trades', 0)}",
            f"    Win Rate     : {m.get('win_rate', 0)*100:.1f}%",
            f"    Profit Factor: {pf:.3f}" if pf else "    Profit Factor: N/A",
            f"    Net P&L      : ${m.get('net_pnl', 0):,.2f}",
            f"    Max Drawdown : ${m.get('max_drawdown', 0):,.2f} "
            f"({m.get('max_drawdown_pct', 0)*100:.1f}%)",
            f"    Sharpe Ratio : {sr:.3f}" if sr else "    Sharpe Ratio : N/A",
            "",
        ]

    lines += fmt_metrics(metrics_2r, "2:1")
    lines += fmt_metrics(metrics_3r, "3:1")

    # Comparative verdict
    pf2 = metrics_2r.get("profit_factor")
    pf3 = metrics_3r.get("profit_factor")
    if pf2 and pf3:
        if pf3 > pf2:
            verdict = (
                f"The 3:1 reward target produced a higher Profit Factor ({pf3:.3f} vs "
                f"{pf2:.3f}), suggesting that the strategy's winning trades have "
                f"sufficient momentum to reach extended targets."
            )
        elif pf2 > pf3:
            verdict = (
                f"The 2:1 reward target produced a higher Profit Factor ({pf2:.3f} vs "
                f"{pf3:.3f}), suggesting that locking in profits at a closer target "
                f"is more reliable for this strategy and market regime."
            )
        else:
            verdict = "Both reward targets produced identical Profit Factors."
        lines += [verdict, ""]

    # ------------------------------------------------------------------
    lines += ["6. MODE PERFORMANCE BREAKDOWN", "-" * 40]

    for mode_key, mode_label in [
        ("breakout", "Breakout Mode"),
        ("manipulation", "Manipulation Mode"),
        ("mean_reversion", "Mean Reversion Mode"),
    ]:
        m2 = metrics_2r.get("by_mode", {}).get(mode_key, {})
        if m2:
            lines += [
                f"  {mode_label}:",
                f"    Trades   : {m2.get('trades', 0)}",
                f"    Win Rate : {m2.get('win_rate', 0)*100:.1f}%",
                f"    Net P&L  : ${m2.get('net_pnl', 0):,.2f}",
                "",
            ]

    # ------------------------------------------------------------------
    lines += ["7. NOTES FOR STRATEGY REFINEMENT", "-" * 40]

    notes = []

    pf2 = metrics_2r.get("profit_factor")
    if pf2 and pf2 < 1.5:
        notes.append(
            "The 2:1 Profit Factor is below the 1.5 benchmark.  Consider "
            "tightening the ATR manipulation threshold or requiring additional "
            "volume confirmation before entry."
        )

    wr = metrics_2r.get("win_rate", 0)
    if wr < 0.55:
        notes.append(
            f"Win rate of {wr*100:.1f}% is below the 70% benchmark cited in the "
            "strategy documentation.  Review whether the retest confirmation "
            "criteria are being applied consistently."
        )

    mr = metrics_2r.get("by_mode", {}).get("mean_reversion", {})
    if mr and mr.get("net_pnl", 0) < 0:
        notes.append(
            "Mean Reversion Mode produced negative net P&L.  This mode is a "
            "fallback and may benefit from stricter activation criteria or "
            "a tighter stop-loss relative to the OR midpoint."
        )

    if not notes:
        notes.append(
            "No immediate refinement flags identified.  Continue monitoring "
            "Profit Factor and Win Rate as the dataset grows."
        )

    for note in notes:
        lines += [f"  - {note}", ""]

    lines += ["=" * 72, "END OF REPORT", "=" * 72]

    return lines


def _pct(numerator, denominator) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 1)
