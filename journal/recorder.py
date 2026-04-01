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
            pd.DataFrame().to_csv(path, index=False)
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

    @property
    def directory(self) -> Path:
        return self.run_dir
