"""
risk/circuit_breaker.py
=======================
Automated risk safeguards that function as a 'circuit breaker' for the
simulated trading account.

Two independent halt conditions are monitored:

  1. Daily Loss Limit    : If the session's realised losses exceed 5% of
                          the session-start equity, all new entries are
                          blocked for the remainder of that calendar day.

  2. Profit Factor Floor : If the rolling Profit Factor (Gross Profit /
                          Gross Loss) drops below 1.5 after a minimum of
                          10 trades, the system alerts and halts trading
                          until the user reviews and resets.

Both conditions are logged with the exact trade and timestamp that
triggered them, providing a precise audit trail.
"""

import logging
from typing import List, Optional

from data.models import TradeResult

log = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Stateful risk monitor.  Must be called after every trade resolution
    and reset at the start of each new calendar day.

    Parameters
    ----------
    starting_equity      : Account equity at the start of the backtest.
    daily_loss_limit_pct : Maximum daily drawdown before halt (default 5%).
    profit_factor_floor  : Minimum acceptable Profit Factor (default 1.5).
    min_trades_pf        : Minimum trades required before PF check activates.
    """

    def __init__(
        self,
        starting_equity: float,
        daily_loss_limit_pct: float = 5.0,
        profit_factor_floor: float  = 1.5,
        min_trades_pf: int          = 10,
    ):
        self.starting_equity      = starting_equity
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.profit_factor_floor  = profit_factor_floor
        self.min_trades_pf        = min_trades_pf

        # Daily state
        self._session_start_equity: float = starting_equity
        self._daily_pnl: float            = 0.0
        self._daily_halted: bool          = False
        self._daily_halt_reason: str      = ""

        # Rolling state across all sessions
        self._all_trades: List[TradeResult] = []
        self._pf_halted: bool               = False
        self._pf_halt_trade_id: str         = ""

        # Halt event log for audit trail
        self.halt_events: List[dict] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_halted(self) -> bool:
        """True if any circuit breaker is active."""
        return self._daily_halted or self._pf_halted

    def record_trade(self, trade: TradeResult) -> None:
        """
        Called after every resolved trade.  Updates daily P&L and
        rolling Profit Factor, triggering halts if thresholds are crossed.
        Uses 2R P&L as the primary accounting figure.
        """
        self._all_trades.append(trade)

        pnl = trade.pnl_2r or 0.0
        self._daily_pnl += pnl

        self._check_daily_loss_limit(trade)
        self._check_profit_factor(trade)

    def reset_daily(self, current_equity: float) -> None:
        """
        Called at the start of each new calendar session.
        Resets daily counters but preserves rolling Profit Factor state.
        """
        self._session_start_equity = current_equity
        self._daily_pnl            = 0.0
        self._daily_halted         = False
        self._daily_halt_reason    = ""

    def reset_profit_factor_halt(self) -> None:
        """
        Manual override — resets the PF circuit breaker after the user
        has reviewed performance.  Recorded in the halt_events log.
        """
        if self._pf_halted:
            self.halt_events.append({
                "type": "pf_halt_reset",
                "note": "Profit Factor halt manually cleared by user.",
            })
            self._pf_halted = False
            self._pf_halt_trade_id = ""

    def get_profit_factor(self) -> Optional[float]:
        """
        Rolling Profit Factor across all recorded trades.
        Returns None if there are no losing trades (undefined).
        Uses 2R P&L.
        """
        gross_profit = sum(t.pnl_2r for t in self._all_trades
                          if t.pnl_2r and t.pnl_2r > 0)
        gross_loss   = abs(sum(t.pnl_2r for t in self._all_trades
                              if t.pnl_2r and t.pnl_2r < 0))
        if gross_loss == 0:
            return None
        return round(gross_profit / gross_loss, 4)

    def get_status(self) -> dict:
        """Return a snapshot of current circuit-breaker state."""
        return {
            "daily_halted":         self._daily_halted,
            "daily_halt_reason":    self._daily_halt_reason,
            "pf_halted":            self._pf_halted,
            "pf_halt_trade_id":     self._pf_halt_trade_id,
            "rolling_profit_factor": self.get_profit_factor(),
            "total_trades_recorded": len(self._all_trades),
            "halt_events":          len(self.halt_events),
        }

    # ------------------------------------------------------------------
    # Private checkers
    # ------------------------------------------------------------------

    def _check_daily_loss_limit(self, trade: TradeResult) -> None:
        if self._daily_halted:
            return
        loss_limit = (self.daily_loss_limit_pct / 100.0) * self._session_start_equity
        if self._daily_pnl <= -loss_limit:
            self._daily_halted     = True
            self._daily_halt_reason = (
                f"Daily loss limit breached: realised loss "
                f"${abs(self._daily_pnl):.2f} exceeds "
                f"${loss_limit:.2f} ({self.daily_loss_limit_pct}% of "
                f"${self._session_start_equity:.2f})."
            )
            event = {
                "type":       "daily_loss_halt",
                "trade_id":   trade.trade_id,
                "session":    trade.session_date,
                "instrument": trade.instrument,
                "reason":     self._daily_halt_reason,
            }
            self.halt_events.append(event)
            log.warning("CIRCUIT BREAKER [Daily Loss] %s", self._daily_halt_reason)

    def _check_profit_factor(self, trade: TradeResult) -> None:
        if self._pf_halted:
            return
        if len(self._all_trades) < self.min_trades_pf:
            return

        pf = self.get_profit_factor()
        if pf is None:
            return

        if pf < self.profit_factor_floor:
            self._pf_halted       = True
            self._pf_halt_trade_id = trade.trade_id
            reason = (
                f"Profit Factor dropped to {pf:.3f}, below floor of "
                f"{self.profit_factor_floor} after {len(self._all_trades)} trades. "
                "Strategy is out of sync with current market conditions."
            )
            event = {
                "type":           "pf_floor_halt",
                "trade_id":       trade.trade_id,
                "session":        trade.session_date,
                "instrument":     trade.instrument,
                "profit_factor":  pf,
                "reason":         reason,
            }
            self.halt_events.append(event)
            log.warning("CIRCUIT BREAKER [Profit Factor] %s", reason)
