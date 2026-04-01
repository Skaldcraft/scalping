"""
risk/position_sizer.py
======================
Standalone position sizing utilities used by trade.py.
Kept as a separate module so sizing logic can be modified independently
of trade resolution logic.
"""


def get_current_equity(starting_capital: float, realised_pnl: float) -> float:
    """Return current account equity after realised P&L."""
    return starting_capital + realised_pnl


def max_position_size(
    account_equity: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float,
    commission: float = 0.0,
    max_leverage: float = 1.0,
) -> float:
    """
    Calculate the maximum permissible position size subject to both
    risk-per-trade and leverage constraints.

    Parameters
    ----------
    account_equity : Current account value.
    entry_price    : Planned entry price.
    stop_loss      : Mechanical stop-loss price.
    risk_pct       : Maximum fraction of equity to risk (e.g., 1.0 = 1%).
    commission     : Flat commission deducted from risk budget.
    max_leverage   : Maximum position value as multiple of equity (default 1×).
    """
    risk_amount   = (risk_pct / 100.0) * account_equity - commission
    stop_distance = abs(entry_price - stop_loss)

    if stop_distance == 0 or risk_amount <= 0:
        return 0.0

    risk_sized    = risk_amount / stop_distance
    leverage_cap  = (account_equity * max_leverage) / entry_price

    return round(min(risk_sized, leverage_cap), 4)
