"""
journal/recorder.py
===================
Persists all trade results and session summaries to structured files
in the results/ directory.  Each run is stored in a timestamped,
version-labelled subfolder to enable longitudinal comparison.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from data.models import TradeResult, SessionSummary

log = logging.getLogger(__name__)


def _trade_to_dict(t: TradeResult) -> dict:
    d = t.__dict__.copy()
    # Convert datetime objects to ISO strings for JSON serialisation
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _summary_to_dict(s: SessionSummary) -> dict:
    d = s.__dict__.copy()
    d["rejection_reasons"] = "; ".join(s.rejection_reasons)
    return d


class JournalRecorder:
    """
    Writes trade logs, session summaries, and config snapshots to disk.

    Parameters
    ----------
    results_dir : Root results directory (default 'results/').
    version     : Version string from settings.yaml (e.g. '1.0').
    config      : Full config dict — snapshotted alongside results.
    """

    def __init__(
        self,
        results_dir: str = "results",
        version: str     = "1.0",
        config: dict | None = None,
    ):
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{ts}_v{version}"
        self.run_dir = Path(results_dir) / folder_name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.version = version
        self.config  = config or {}
        log.info("Journal run directory: %s", self.run_dir)

    # ------------------------------------------------------------------

    def save_trade_log(
        self,
        instrument_results: Dict[str, List[TradeResult]],
    ) -> Path:
        """Write all trades to a single CSV: results/<run>/trade_log.csv"""
        rows = []
        for sym, trades in instrument_results.items():
            for t in trades:
                rows.append(_trade_to_dict(t))

        if not rows:
            log.warning("No trades to record in trade log.")
            path = self.run_dir / "trade_log.csv"
            trade_columns = list(TradeResult.__dataclass_fields__.keys())
            pd.DataFrame(columns=trade_columns).to_csv(path, index=False)
            return path

        df   = pd.DataFrame(rows)
        path = self.run_dir / "trade_log.csv"
        df.to_csv(path, index=False)
        log.info("Trade log saved: %s (%d trades)", path, len(rows))
        return path

    def save_session_log(
        self,
        session_summaries: Dict[str, List[SessionSummary]],
    ) -> Path:
        """Write all session summaries to results/<run>/session_log.csv"""
        rows = []
        for sym, summaries in session_summaries.items():
            for s in summaries:
                rows.append(_summary_to_dict(s))

        df   = pd.DataFrame(rows) if rows else pd.DataFrame()
        path = self.run_dir / "session_log.csv"
        df.to_csv(path, index=False)
        log.info("Session log saved: %s (%d sessions)", path, len(rows))
        return path

    def save_config_snapshot(self) -> Path:
        """Copy the active config into the run folder for reproducibility."""
        import yaml
        path = self.run_dir / "config_snapshot.yaml"
        with open(path, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)
        log.info("Config snapshot saved: %s", path)
        return path

    def save_changelog_snapshot(self, changelog_path: str | Path) -> Path:
        """Copy the changelog into the run folder for version traceability."""
        source = Path(changelog_path)
        path = self.run_dir / "changelog.md"
        if not source.exists():
            log.warning("Changelog not found, skipping copy: %s", source)
            return path
        shutil.copy2(source, path)
        log.info("Changelog snapshot saved: %s", path)
        return path

    def save_selection_snapshot(self, snapshot: dict) -> dict:
        """Persist pre-session selection output to JSON and CSV."""
        json_path = self.run_dir / "selection_snapshot.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

        csv_path = self.run_dir / "selection_snapshot.csv"
        rows = snapshot.get("evaluated", [])
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        log.info("Selection snapshot saved: %s, %s", json_path, csv_path)
        return {"json": json_path, "csv": csv_path}

    def save_selection_report(self, snapshot: dict) -> Path:
        """Write a short human-readable summary of the pre-session selection."""
        path = self.run_dir / "selection_report.txt"

        selected = snapshot.get("selected_symbols", [])
        rules = snapshot.get("rules", {})
        evaluated = snapshot.get("evaluated", [])

        lines = [
            "PulseTrader Pre-Session Selection Report",
            "=" * 44,
            f"Selection Date : {snapshot.get('selection_date', 'N/A')}",
            f"Top N          : {snapshot.get('top_n', 'N/A')}",
            f"Selected       : {', '.join(selected) if selected else 'none'}",
            "",
            "Rules",
            "-----",
            f"min_profit_factor : {rules.get('min_profit_factor')}",
            f"pf_missing_policy : {rules.get('pf_missing_policy', rules.get('require_pf_history'))}",
            f"max_spread        : {rules.get('max_spread')}",
            f"spread_missing    : {rules.get('spread_missing_policy', rules.get('require_spread_data'))}",
            f"overlap_priority  : {rules.get('overlap_priority')}",
            "",
            "Evaluated",
            "---------",
        ]

        for row in evaluated:
            reasons = row.get("reasons", [])
            reason_text = ", ".join(reasons) if reasons else "eligible"
            lines.append(
                f"{row.get('symbol')}: selected={row.get('selected')} rank={row.get('rank')} "
                f"atr14={row.get('atr14')} pf={row.get('profit_factor')} spread={row.get('spread')} "
                f"manip={row.get('manipulation_status')} gap={row.get('displacement_gap')} "
                f"reasons={reason_text}"
            )

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        log.info("Selection report saved: %s", path)
        return path

    @property
    def directory(self) -> Path:
        return self.run_dir
