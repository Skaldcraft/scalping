"""
selector/pre_session_selector.py
================================
Deterministic pre-session Top-N instrument selection.
"""

from __future__ import annotations

import logging
from datetime import date

from selector.provider import SelectionDataProvider

log = logging.getLogger(__name__)


def _normalise_universe(cfg: dict) -> list[dict]:
    pre_cfg = cfg.get("pre_session", {})
    raw_universe = pre_cfg.get("universe", [])

    universe: list[dict] = []
    if raw_universe:
        for item in raw_universe:
            if isinstance(item, str):
                universe.append({"symbol": item, "asset_class": "equity"})
            elif isinstance(item, dict) and item.get("symbol"):
                universe.append(
                    {
                        "symbol": str(item["symbol"]),
                        "asset_class": str(item.get("asset_class", "equity")),
                    }
                )
    else:
        for sym in cfg.get("instruments", {}).get("equities", []):
            universe.append({"symbol": sym, "asset_class": "equity"})

    deduped: list[dict] = []
    seen: set[str] = set()
    for item in universe:
        sym = item["symbol"]
        if sym in seen:
            continue
        seen.add(sym)
        deduped.append(item)

    return deduped


def run_pre_session_selection(
    cfg: dict,
    as_of_date: date,
    provider: SelectionDataProvider,
) -> dict:
    """
    Select instruments for the session and return a full audit snapshot.

    Selection pipeline:
      1. Evaluate ATR, PF, and spread for every universe symbol.
      2. Apply PF/spread eligibility filters.
      3. Rank eligible symbols by ATR desc, spread asc, PF desc.
      4. Return top N symbols.
    """
    pre_cfg = cfg.get("pre_session", {})
    rules = pre_cfg.get("selection_rules", {})

    top_n = int(pre_cfg.get("top_n", 3))
    min_pf = float(rules.get("min_profit_factor", 1.5))

    pf_missing_policy = str(rules.get("pf_missing_policy", "allow")).lower()
    if pf_missing_policy not in {"allow", "reject"}:
        pf_missing_policy = "reject" if bool(rules.get("require_pf_history", False)) else "allow"

    max_spread = rules.get("max_spread")
    max_spread = float(max_spread) if max_spread is not None else None
    spread_missing_policy = str(rules.get("spread_missing_policy", "allow")).lower()
    if spread_missing_policy not in {"allow", "reject"}:
        spread_missing_policy = "reject" if bool(rules.get("require_spread_data", False)) else "allow"

    evaluated = []
    eligible = []
    overlap_signals = pre_cfg.get("overlap_signals", {})

    for item in _normalise_universe(cfg):
        symbol = item["symbol"]
        asset_class = item["asset_class"]
        reasons = []

        atr14 = provider.get_atr14(symbol, as_of_date)
        pf = provider.get_profit_factor(symbol, as_of_date)
        spread = provider.get_spread(symbol, as_of_date)

        if atr14 is None:
            reasons.append("missing_atr")

        if pf is None:
            if pf_missing_policy == "reject":
                reasons.append("missing_pf")
        elif pf < min_pf:
            reasons.append("pf_below_threshold")

        if spread is None:
            if spread_missing_policy == "reject":
                reasons.append("missing_spread")
        elif max_spread is not None and spread > max_spread:
            reasons.append("spread_above_threshold")

        overlap_meta = overlap_signals.get(symbol, {}) if isinstance(overlap_signals, dict) else {}
        manipulation_status = bool(overlap_meta.get("manipulation_status", False))
        displacement_gap = bool(overlap_meta.get("displacement_gap", False))

        eligible_flag = len(reasons) == 0

        row = {
            "symbol": symbol,
            "asset_class": asset_class,
            "atr14": atr14,
            "profit_factor": pf,
            "spread": spread,
            "manipulation_status": manipulation_status,
            "displacement_gap": displacement_gap,
            "eligible": eligible_flag,
            "reasons": reasons,
        }
        evaluated.append(row)

        if eligible_flag:
            eligible.append(row)

    def _sort_key(row: dict):
        manipulation_score = 1 if row.get("manipulation_status") else 0
        displacement_score = 1 if row.get("displacement_gap") else 0
        atr = row["atr14"] if row["atr14"] is not None else float("-inf")
        spread = row["spread"] if row["spread"] is not None else float("inf")
        pf = row["profit_factor"] if row["profit_factor"] is not None else float("-inf")
        return (-manipulation_score, -displacement_score, spread, -pf, -atr)

    ranked = sorted(eligible, key=_sort_key)
    selected = ranked[:top_n]

    selected_symbols = [row["symbol"] for row in selected]
    selected_set = set(selected_symbols)

    for idx, row in enumerate(selected, start=1):
        row["rank"] = idx

    for row in evaluated:
        if row["symbol"] in selected_set:
            row["selected"] = True
            row["rank"] = selected_symbols.index(row["symbol"]) + 1
        else:
            row["selected"] = False
            row.setdefault("rank", None)

    excluded = [row for row in evaluated if not row["selected"]]

    snapshot = {
        "selection_date": str(as_of_date),
        "top_n": top_n,
        "selected_symbols": selected_symbols,
        "selected": selected,
        "excluded": excluded,
        "evaluated": evaluated,
        "rules": {
            "min_profit_factor": min_pf,
            "pf_missing_policy": pf_missing_policy,
            "max_spread": max_spread,
            "spread_missing_policy": spread_missing_policy,
            "overlap_priority": [
                "manipulation_status",
                "displacement_gap",
                "spread",
                "profit_factor",
                "atr14",
            ],
        },
    }

    log.info(
        "Pre-session selection (%s): selected %s",
        as_of_date,
        ", ".join(selected_symbols) if selected_symbols else "none",
    )

    return snapshot
