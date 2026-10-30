"""Turn the Azure LLM inference trace 2024 into a 5-minute utilization profile.

The trace has one row per request (timestamp, context tokens, generated tokens).
We bin token throughput into 5-minute intervals and normalize by the 99th
percentile, giving a utilization in [0, ~1]. Throughput is a proxy for GPU
power: DynamoLLM (HPCA 2025) shows inference cluster power rises with load
above a substantial idle floor. The mapping from utilization to MW is in
realdata.scenarios and is an explicit assumption, not a measurement.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "azure_llm_2024"
PROCESSED = ROOT / "data" / "processed"
BIN = "5min"


def _bin_file(path: Path) -> pd.DataFrame:
    parts = []
    for chunk in pd.read_csv(path, chunksize=2_000_000):
        # Timestamps are UTC ("2024-05-10 00:00:00.009930+00:00"); bin on the
        # minute prefix first, which is far faster than parsing every row.
        stamp = chunk["TIMESTAMP"].str.slice(0, 16)
        minute = stamp.str.slice(14, 16).astype(int) // 5 * 5
        key = stamp.str.slice(0, 14) + minute.map("{:02d}".format)
        grouped = chunk.assign(TIMESTAMP=key).groupby("TIMESTAMP").agg(
            requests=("ContextTokens", "size"),
            context_tokens=("ContextTokens", "sum"),
            generated_tokens=("GeneratedTokens", "sum"),
        )
        parts.append(grouped)
    binned = pd.concat(parts).groupby(level=0).sum()
    binned.index = pd.to_datetime(binned.index, utc=True)
    return binned


def build_profile(raw_dir: Path = RAW, cache: Path | None = PROCESSED / "azure_llm_2024_5min.csv.gz") -> pd.DataFrame:
    """Return 5-minute utilization for the code and chat services combined.

    The two services cover different days, so each is normalized by its own
    99th-percentile throughput and the facility utilization is the mean of
    the services observed in that interval. This keeps every traced day
    instead of only the overlap.
    """
    if cache is not None and cache.exists():
        frame = pd.read_csv(cache, index_col=0)
        frame.index = pd.to_datetime(frame.index, utc=True)
        return frame
    columns = {}
    for name in ("code", "conv"):
        frame = _bin_file(raw_dir / f"AzureLLMInferenceTrace_{name}_1week.csv")
        # Trim to the service's own span; interior empty bins are real zeros.
        index = pd.date_range(frame.index.min(), frame.index.max(), freq=BIN, tz="UTC")
        tokens = (frame["context_tokens"] + frame["generated_tokens"]).reindex(index, fill_value=0)
        columns[f"{name}_tokens"] = tokens
        columns[f"{name}_utilization"] = tokens / tokens.quantile(0.99)
    combined = pd.DataFrame(columns)
    combined["utilization"] = combined[[f"{name}_utilization" for name in ("code", "conv")]].mean(axis=1)
    combined.index.name = "interval_start_utc"
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(cache)
    return combined
