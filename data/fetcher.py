"""
data/fetcher.py
===============
Unified data ingestion layer.

  - Equities / indices : fetched on demand via yfinance.
  - Forex              : loaded from user-supplied OHLCV CSV files.

Both paths return identically structured pandas DataFrames so that
all downstream engine modules are data-source agnostic.

Expected DataFrame columns (all float except timestamp):
    timestamp (DatetimeTZDtype, America/New_York), open, high, low, close, volume
"""

import hashlib
import logging
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

_CACHE_DIR = Path("data_files/_yfinance_cache")
_INTRADAY_TTL = timedelta(minutes=15)
_DAILY_TTL = timedelta(hours=20)


def _cache_key(symbol: str, interval: str, start: date, end: date) -> str:
    key_str = f"{symbol}|{interval}|{start}|{end}"
    return hashlib.sha1(key_str.encode()).hexdigest()[:16]


def _cache_path(symbol: str, interval: str, start: date, end: date) -> Path:
    key = _cache_key(symbol, interval, start, end)
    return _CACHE_DIR / f"{symbol}_{interval}_{key}.parquet"


def _read_cache(symbol: str, interval: str, start: date, end: date) -> Optional[pd.DataFrame]:
    path = _cache_path(symbol, interval, start, end)
    if not path.exists():
        return None
    try:
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        ttl = _INTRADAY_TTL if interval != "1d" else _DAILY_TTL
        if age > ttl:
            return None
        df = pd.read_parquet(path)
        log.debug("[%s] Cache hit: %s %s %s → %s (%s old)", symbol, interval, start, end, path.name, age)
        return df
    except Exception as exc:
        log.debug("Cache read failed for %s: %s", path, exc)
        return None


def _write_cache(df: pd.DataFrame, symbol: str, interval: str, start: date, end: date) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(symbol, interval, start, end)
        df.to_parquet(path, index=True)
        log.debug("[%s] Cached: %s %s %s → %s", symbol, interval, start, end, path.name)
    except Exception as exc:
        log.debug("Cache write failed for %s %s %s: %s", symbol, interval, start, exc)


# ---------------------------------------------------------------------------
# Column normalisation helpers
# ---------------------------------------------------------------------------

_REQUIRED_COLS = {"open", "high", "low", "close", "volume"}

def _normalise(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Standardise column names, timezone, and index for any raw DataFrame."""
    df = df.copy()
    df.columns = [c.lower().strip() for c in df.columns]

    # Accept 'adj close' from yfinance but rename to 'close'
    if "adj close" in df.columns and "close" not in df.columns:
        df.rename(columns={"adj close": "close"}, inplace=True)
    if "adj_close" in df.columns and "close" not in df.columns:
        df.rename(columns={"adj_close": "close"}, inplace=True)

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"[{symbol}] Missing columns after normalisation: {missing}")

    # Ensure DatetimeTZDtype in ET
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("America/New_York")
    else:
        df.index = df.index.tz_convert("America/New_York")

    df.index.name = "timestamp"
    df = df[list(_REQUIRED_COLS)].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_intraday(
    symbol: str,
    interval: str,          # "1m" | "5m" | "15m"
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Fetch intraday bars for an equity or index from Yahoo Finance.

    yfinance provides:
      - 1m bars : last 30 calendar days
      - 5m bars : last 60 calendar days  (up to ~730 days with chunking)
      - 15m bars: last 60 calendar days

    Results are cached locally in Parquet files with a 15-minute TTL for
    intraday data to reduce unnecessary API calls during repeated runs.
    """
    cached = _read_cache(symbol, interval, start, end)
    if cached is not None:
        return cached

    log.debug("yfinance fetch: %s %s %s → %s", symbol, interval, start, end)
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        interval=interval,
        start=str(start),
        end=str(end),
        auto_adjust=True,
        prepost=False,
    )
    if df.empty:
        raise ValueError(
            f"yfinance returned no data for {symbol} ({interval}) "
            f"between {start} and {end}. "
            "Check symbol name and ensure the date range is within yfinance limits."
        )
    df = _normalise(df, symbol)
    _write_cache(df, symbol, interval, start, end)
    return df


def fetch_daily(
    symbol: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Fetch daily OHLCV bars used for ATR calculation.

    Results are cached locally in Parquet files with a 20-hour TTL for
    daily data (new bar only appears after market close).
    """
    cached = _read_cache(symbol, "1d", start, end)
    if cached is not None:
        return cached

    log.debug("yfinance daily fetch: %s %s → %s", symbol, start, end)
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        interval="1d",
        start=str(start),
        end=str(end),
        auto_adjust=True,
        prepost=False,
    )
    if df.empty:
        raise ValueError(f"yfinance returned no daily data for {symbol}.")
    df = _normalise(df, symbol)
    _write_cache(df, symbol, "1d", start, end)
    return df


_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_dataframe(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Neutralize formula injection in DataFrame string columns.

    Spreadsheet formula injection occurs when cell values start with =, +, -,
    or @. This function strips those prefixes and prepends a space to prevent
    the value from being interpreted as a formula when the DataFrame is
    exported to CSV and opened in Excel or Google Sheets.

    Parameters
    ----------
    df       : DataFrame loaded from user-supplied CSV.
    symbol   : Ticker label for logging context.

    Returns
    -------
    DataFrame with sanitized string values.
    """
    sanitized_count = 0
    for col in df.columns:
        if df[col].dtype == object:
            before = df[col].astype(str)
            after = before.apply(_strip_formula_prefix)
            changed = (before != after)
            if changed.any():
                sanitized_count += int(changed.sum())
                df[col] = after

    if sanitized_count > 0:
        log.warning(
            "[%s] CSV sanitized: %d cell(s) had formula-prefix values "
            "(=, +, -, @). These have been neutralized to prevent "
            "spreadsheet injection. Verify data integrity manually.",
            symbol, sanitized_count
        )

    return df


def _strip_formula_prefix(value: str) -> str:
    """Strip formula injection prefix from a cell value."""
    s = str(value).strip()
    if s and s[0] in _FORMULA_PREFIXES:
        return " " + s
    return s


def load_csv(
    filepath: str,
    symbol: str,
    datetime_col: str = "timestamp",
    datetime_format: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load a user-supplied CSV file of intraday OHLCV data (typically Forex).

    Expected CSV format (column names are case-insensitive):
        timestamp, open, high, low, close, volume

    The timestamp column should be parseable by pandas (ISO 8601 preferred).
    If the CSV has no volume column a synthetic zero-volume column is added
    so that downstream modules remain schema-consistent.

    Parameters
    ----------
    filepath       : Path to the CSV file.
    symbol         : Ticker label used in log messages and error context.
    datetime_col   : Name of the datetime column in the CSV (default 'timestamp').
    datetime_format: Optional strptime format string for non-standard dates.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(
            f"[{symbol}] CSV not found: {filepath}\n"
            "Place your Forex data file in the data_files/ directory and "
            "update config/settings.yaml with the correct path."
        )

    log.debug("Loading CSV: %s (%s)", filepath, symbol)
    df = pd.read_csv(filepath, engine="python")

    df = _sanitize_dataframe(df, symbol)
    df.columns = [c.lower().strip() for c in df.columns]

    # Detect datetime column
    dt_col = datetime_col.lower()
    if dt_col not in df.columns:
        # Try common alternatives
        for candidate in ("date", "datetime", "time", "Date", "Datetime"):
            if candidate.lower() in df.columns:
                dt_col = candidate.lower()
                break
        else:
            raise ValueError(
                f"[{symbol}] Cannot find a datetime column in {filepath}. "
                f"Columns found: {list(df.columns)}"
            )

    df[dt_col] = pd.to_datetime(df[dt_col], format=datetime_format, utc=False)
    df = df.set_index(dt_col)
    df.index.name = "timestamp"

    # Synthetic volume if absent
    if "volume" not in df.columns:
        log.warning("[%s] No volume column found in CSV; setting volume=0.", symbol)
        df["volume"] = 0.0

    return _normalise(df, symbol)


def fetch_intraday_chunked(
    symbol: str,
    interval: str,
    start: date,
    end: date,
    chunk_days: int = 58,
) -> pd.DataFrame:
    """
    Fetch intraday data over long date ranges by splitting into rolling
    chunks that fit within yfinance's per-request limits.

    Each chunk is fetched via fetch_intraday() and benefits from the
    shared Parquet cache, so repeated runs across overlapping windows
    only hit the API for genuinely new data.
    """
    interval_norm = interval.strip().lower()
    effective_chunk_days = chunk_days
    if interval_norm == "1m":
        # Yahoo currently limits 1m requests to short windows.
        effective_chunk_days = min(chunk_days, 7)
    elif interval_norm in ("5m", "15m"):
        effective_chunk_days = min(chunk_days, 58)

    delta = (end - start).days
    if delta <= effective_chunk_days:
        return fetch_intraday(symbol, interval, start, end)

    chunks = []
    n_chunks = math.ceil(delta / effective_chunk_days)
    log.info(
        "[%s] Date range (%d days) split into %d chunks of %d days.",
        symbol, delta, n_chunks, effective_chunk_days,
    )
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + pd.Timedelta(days=effective_chunk_days), end)
        try:
            chunk = fetch_intraday(symbol, interval, chunk_start, chunk_end)
            chunks.append(chunk)
        except ValueError as exc:
            log.warning("Chunk %s → %s returned no data: %s", chunk_start, chunk_end, exc)
        chunk_start = chunk_end + pd.Timedelta(days=1)

    if not chunks:
        raise ValueError(f"[{symbol}] All chunks returned empty data.")

    combined = pd.concat(chunks)
    combined = combined[~combined.index.duplicated(keep="first")]
    return combined.sort_index()
