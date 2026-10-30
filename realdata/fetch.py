"""Download the open datasets used by the real-data evaluation into data/raw.

Sources (all public, no account needed):
- Azure LLM inference trace 2024 (CC-BY 4.0), May 10-19 2024, one week of
  request timestamps with input/output token counts for code and chat services.
  Cite: Stojkovic et al., "DynamoLLM", HPCA 2025.
- CAISO OASIS real-time 15-minute LMP at the SP15 trading hub, and CAISO
  5-minute system demand, via the gridstatus package.

ERCOT was the first choice for grid events but its public MIS endpoint returned
HTTP 403 from the development network, so CAISO is used instead.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
AZURE_URLS = {
    "code": "https://github.com/Azure/AzurePublicDataset/releases/download/dataset-llm-2024/AzureLLMInferenceTrace_code_1week.csv",
    "conv": "https://github.com/Azure/AzurePublicDataset/releases/download/dataset-llm-2024/AzureLLMInferenceTrace_conv_1week.csv",
}
CAISO_HUB = "TH_SP15_GEN-APND"


def fetch_azure(directory: Path = RAW / "azure_llm_2024") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, url in AZURE_URLS.items():
        target = directory / f"AzureLLMInferenceTrace_{name}_1week.csv"
        if target.exists() and target.stat().st_size > 0:
            continue
        urllib.request.urlretrieve(url, target)


def fetch_caiso(year: int, directory: Path = RAW / "caiso") -> None:
    import gridstatus

    directory.mkdir(parents=True, exist_ok=True)
    caiso = gridstatus.CAISO()
    months = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq="MS")
    price_path = directory / f"caiso_rt15_lmp_sp15_{year}.csv.gz"
    if not price_path.exists():
        frames = [caiso.get_lmp(start=start, end=end, market="REAL_TIME_15_MIN", locations=[CAISO_HUB])
                  for start, end in zip(months[:-1], months[1:])]
        prices = pd.concat(frames, ignore_index=True)
        prices[["Interval Start", "LMP"]].to_csv(price_path, index=False)
    load_path = directory / f"caiso_load_5min_{year}.csv.gz"
    if not load_path.exists():
        frames = [caiso.get_load(start=start, end=end) for start, end in zip(months[:-1], months[1:])]
        load = pd.concat(frames, ignore_index=True)
        load[["Interval Start", "Load"]].to_csv(load_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--skip-azure", action="store_true")
    args = parser.parse_args()
    if not args.skip_azure:
        fetch_azure()
    fetch_caiso(args.year)


if __name__ == "__main__":
    main()
