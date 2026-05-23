"""
Local price loader. Reads OHLC/close from CSV/parquet files under `data/prices/`.

Replaces CalaClient.get_prices for real price history. Cala MCP stays for
knowledge/news only.

Expected layout:
    data/prices/<material>.csv     columns: date,price   (date ISO, price float)
    data/prices/<material>.parquet (alternative)

TODO(wire):
  1. Drop CSV/parquet files into data/prices/ (e.g. extract ordi_data.zip).
  2. Swap CalaClient.get_prices() -> LocalPriceLoader().get_prices() in
     app/data/ingestion.py.
  3. Delete the price-REST path in app/clients/cala_client.py (Cala has no
     price endpoint).
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from app.clients.cala_client import CalaPricePoint

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prices"


class LocalPriceLoaderError(RuntimeError):
    pass


class LocalPriceLoader:
    def __init__(self, data_dir: Path = _DATA_DIR) -> None:
        self._dir = data_dir

    def get_prices(self, material: str, lookback_days: int = 365) -> list[CalaPricePoint]:
        path = self._resolve(material)
        if path is None:
            raise LocalPriceLoaderError(
                f"No price file for '{material}' under {self._dir}. "
                f"Expected {material}.csv or {material}.parquet."
            )
        points = self._read_csv(path) if path.suffix == ".csv" else self._read_parquet(path)
        cutoff = date.today() - timedelta(days=lookback_days)
        return [p for p in points if p.date >= cutoff]

    def _resolve(self, material: str) -> Path | None:
        for ext in (".csv", ".parquet"):
            p = self._dir / f"{material.lower()}{ext}"
            if p.exists():
                return p
        return None

    def _read_csv(self, path: Path) -> list[CalaPricePoint]:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [
                CalaPricePoint({"date": row["date"], "price": row["price"]})
                for row in reader
            ]

    def _read_parquet(self, path: Path) -> list[CalaPricePoint]:
        try:
            import pandas as pd
        except ImportError as e:
            raise LocalPriceLoaderError("pandas required for parquet") from e
        df = pd.read_parquet(path)
        return [
            CalaPricePoint({"date": str(d), "price": float(p)})
            for d, p in zip(df["date"], df["price"])
        ]
