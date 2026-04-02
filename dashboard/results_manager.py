from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

import pandas as pd

TRASH_DIR_NAME = "_trash"


def _safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _format_bytes(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(size_bytes, 0))
    unit = units[0]
    for candidate in units:
        unit = candidate
        if value < 1024 or candidate == units[-1]:
            break
        value /= 1024.0
    return f"{value:.1f} {unit}"


def _folder_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists() or not path.is_dir():
        return 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _run_timestamp(path: Path) -> datetime | None:
    stamp = path.name.split("_v", 1)[0]
    parsed = pd.to_datetime(stamp, format="%Y%m%d_%H%M%S", errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _summarize_trade_log(run_dir: Path) -> tuple[int, float, str]:
    trade_log = run_dir / "trade_log.csv"
    if not trade_log.exists():
        return 0, 0.0, ""

    df = _safe_read_csv(trade_log)
    if df.empty:
        return 0, 0.0, ""

    trades = len(df)
    pnl = float(df.get("pnl_2r", pd.Series(dtype=float)).fillna(0).sum()) if "pnl_2r" in df.columns else 0.0
    symbols = ""
    if "instrument" in df.columns:
        unique_symbols = sorted({str(s).upper() for s in df["instrument"].dropna().astype(str) if s})
        symbols = ", ".join(unique_symbols[:8])
        if len(unique_symbols) > 8:
            symbols += f" (+{len(unique_symbols) - 8})"

    return trades, pnl, symbols


def _is_managed_active_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name
    if name.startswith("_"):
        return False
    if name.startswith("batch_"):
        return True
    return (path / "trade_log.csv").exists()


def _is_managed_trash_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name
    if name.startswith("batch_"):
        return True
    return (path / "trade_log.csv").exists() or "_v" in name


def _dir_kind(path: Path) -> str:
    if path.name.startswith("batch_"):
        return "weekly_batch"
    return "backtest"


def _record_for_dir(path: Path, status: str) -> dict:
    trades, net_pnl, symbols = _summarize_trade_log(path)
    size_bytes = _folder_size_bytes(path)
    ts = _run_timestamp(path)
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return {
        "id": path.name,
        "path": str(path),
        "kind": _dir_kind(path),
        "status": status,
        "timestamp": ts.isoformat(timespec="seconds") if ts else "",
        "modified": modified.isoformat(timespec="seconds"),
        "trades": trades,
        "net_pnl_2r": round(net_pnl, 2),
        "symbols": symbols,
        "size_bytes": size_bytes,
        "size": _format_bytes(size_bytes),
    }


def list_results(results_dir: Path) -> tuple[list[dict], list[dict]]:
    active_records: list[dict] = []
    trash_records: list[dict] = []

    if results_dir.exists():
        for child in results_dir.iterdir():
            if _is_managed_active_dir(child):
                active_records.append(_record_for_dir(child, status="active"))

    trash_dir = results_dir / TRASH_DIR_NAME
    if trash_dir.exists():
        for child in trash_dir.iterdir():
            if _is_managed_trash_dir(child):
                trash_records.append(_record_for_dir(child, status="trash"))

    active_records.sort(key=lambda r: r["modified"], reverse=True)
    trash_records.sort(key=lambda r: r["modified"], reverse=True)
    return active_records, trash_records


def move_items_to_trash(results_dir: Path, item_ids: list[str]) -> tuple[int, list[str]]:
    trash_dir = results_dir / TRASH_DIR_NAME
    trash_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    skipped: list[str] = []

    for item_id in item_ids:
        source = results_dir / item_id
        if not source.exists() or not source.is_dir() or source.name.startswith("_"):
            skipped.append(item_id)
            continue

        target = trash_dir / item_id
        if target.exists():
            target = trash_dir / f"{item_id}_{datetime.now().strftime('%H%M%S')}"

        try:
            shutil.move(str(source), str(target))
            moved += 1
        except Exception:
            skipped.append(item_id)

    return moved, skipped


def restore_items_from_trash(results_dir: Path, item_ids: list[str]) -> tuple[int, list[str]]:
    trash_dir = results_dir / TRASH_DIR_NAME
    restored = 0
    skipped: list[str] = []

    for item_id in item_ids:
        source = trash_dir / item_id
        if not source.exists() or not source.is_dir():
            skipped.append(item_id)
            continue

        target = results_dir / item_id
        if target.exists():
            target = results_dir / f"{item_id}_{datetime.now().strftime('%H%M%S')}"

        try:
            shutil.move(str(source), str(target))
            restored += 1
        except Exception:
            skipped.append(item_id)

    return restored, skipped


def delete_items_permanently(results_dir: Path, item_ids: list[str]) -> tuple[int, list[str], int]:
    trash_dir = results_dir / TRASH_DIR_NAME
    deleted = 0
    skipped: list[str] = []
    reclaimed_bytes = 0

    for item_id in item_ids:
        target = trash_dir / item_id
        if not target.exists() or not target.is_dir():
            skipped.append(item_id)
            continue

        try:
            reclaimed_bytes += _folder_size_bytes(target)
            shutil.rmtree(target)
            deleted += 1
        except Exception:
            skipped.append(item_id)

    return deleted, skipped, reclaimed_bytes


def delete_active_items(results_dir: Path, item_ids: list[str]) -> tuple[int, list[str], int]:
    """Permanently delete active (non-trash) result folders."""
    deleted = 0
    skipped: list[str] = []
    reclaimed_bytes = 0

    for item_id in item_ids:
        target = results_dir / item_id
        if not target.exists() or not target.is_dir() or target.name.startswith("_"):
            skipped.append(item_id)
            continue

        try:
            reclaimed_bytes += _folder_size_bytes(target)
            shutil.rmtree(target)
            deleted += 1
        except Exception:
            skipped.append(item_id)

    return deleted, skipped, reclaimed_bytes


def summarize(active_records: list[dict], trash_records: list[dict]) -> dict:
    active_size = sum(r.get("size_bytes", 0) for r in active_records)
    trash_size = sum(r.get("size_bytes", 0) for r in trash_records)
    return {
        "total_runs": len(active_records),
        "total_size": _format_bytes(active_size + trash_size),
        "trash_count": len(trash_records),
        "reclaimable": _format_bytes(trash_size),
    }
