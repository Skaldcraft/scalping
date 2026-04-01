# config/changelog.md
# ====================
# Precision Scalping Utility — Change Manifest
#
# Every time the strategy logic, parameters, or architecture is modified,
# a new entry should be added here before running a backtest.
# The version string in settings.yaml must be incremented to match.
#
# This file serves as the longitudinal record that connects result sets
# to the exact logic version that produced them, enabling objective
# comparison of improvements over time.
#
# Format:
#   ## vX.Y — YYYY-MM-DD
#   ### Changed
#   - Description of what changed and why
#   ### Expected Impact
#   - Hypothesis about how this change affects performance

## v1.0 — Initial Release
### Architecture
- Four-module architecture: Data Ingestion, Signal Engine, Risk Management,
  Reporting & Journal.
- Unified hybrid ruleset combining Casper SMC (slingshot retest), ProRealAlgos
  (ATR manipulation filter + reversal patterns), and Jdub Trades (mean reversion
  fallback).

### Strategy Parameters
- Opening range: user-selectable (5 or 15 minutes).
- ATR period: 14-day.
- Manipulation threshold: 25% of daily ATR.
- Reward targets: 2:1 and 3:1 tracked concurrently.
- Retest rule: permissive (wick touch to boundary + close outside).
- Reversal patterns: Hammer, Inverted Hammer, Bullish/Bearish Engulfing.

### Risk Parameters
- Risk per trade: 1% of current equity.
- Daily loss limit: 5%.
- Profit Factor floor: 1.5 (activates after minimum 10 trades).

### Reporting
- Trade log CSV, session log CSV, run report (prose), execution log (JSON),
  config snapshot per run.

### Expected Baseline
- Target win rate: 70% (per Casper SMC retest model benchmark).
- Target Profit Factor: ≥ 1.5.
- Benchmark instruments: AAPL, NVDA, AMZN, QQQ, SPY.

---
# Future entries go above this line.
