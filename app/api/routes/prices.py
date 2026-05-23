from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import datetime as dt

router = APIRouter(tags=["prices"])

COMMODITY_MAP = {
    "barley":    "barley",
    "cebada":    "barley",
    "aluminium": "aluminium",
    "aluminio":  "aluminium",
    "energy":    "energy",
    "energia":   "energy",
    "pet":       "pet",
}

UNITS = {
    "barley":    "EUR/MT",
    "aluminium": "USD/MT",
    "energy":    "EUR/MWh",
    "pet":       "USD/barrel",
}

SOURCES = {
    "barley":    "Damm CSV — weekly interpolated to daily",
    "aluminium": "Yahoo Finance ALI=F (LME aluminium futures)",
    "energy":    "OMIE — Iberian Electricity Market Operator (official)",
    "pet":       "Yahoo Finance BZ=F (Brent crude proxy)",
}


# ── 1. BARLEY ─────────────────────────────────────────────────────────────────

def fetch_barley(start: datetime, end: datetime) -> pd.DataFrame:
    df = pd.read_csv("app/data/train.csv", parse_dates=["ds"])[["ds", "y"]]
    df.columns = ["date", "price"]
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna().sort_values("date").reset_index(drop=True)

    daily_index = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    df_daily = (
        df.set_index("date")
        .reindex(daily_index)
        .interpolate(method="time")
        .reset_index()
    )
    df_daily.columns = ["date", "price"]

    mask = (df_daily["date"] >= pd.Timestamp(start)) & \
           (df_daily["date"] <= pd.Timestamp(end))
    return df_daily[mask].reset_index(drop=True)


# ── 2. ALUMINIUM ──────────────────────────────────────────────────────────────

def fetch_aluminium(start: datetime, end: datetime) -> pd.DataFrame:
    df = yf.download(
        "ALI=F",
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        raise ValueError("No aluminium data from Yahoo Finance")
    df = df[["Close"]].reset_index()
    df.columns = ["date", "price"]
    df["date"]  = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


# ── 3. ENERGY — OMIE official ─────────────────────────────────────────────────

def fetch_energy(start: datetime, end: datetime) -> pd.DataFrame:
    """
    Fetch Spanish electricity day-ahead price from OMIE
    using the OMIEData package (pip install OMIEData).
    Official source — no API key needed.
    """
    try:
        from OMIEData.DataImport.omie_marginalprice_importer import (
            OMIEMarginalPriceFileImporter,
        )
        from OMIEData.Enums.all_enums import DataTypeInMarginalPriceFile

        importer = OMIEMarginalPriceFileImporter(
            date_ini=dt.datetime(start.year, start.month, start.day),
            date_end=dt.datetime(end.year,   end.month,   end.day),
        )
        df_raw = importer.read_to_dataframe(
            data_type=DataTypeInMarginalPriceFile.PRICE_SPAIN
        )

        if df_raw.empty:
            raise ValueError("OMIEData returned empty dataframe")

        # OMIEData returns hourly data — aggregate to daily mean
        df_raw["date"] = pd.to_datetime(df_raw["DATETIME"]).dt.normalize()
        df_daily = (
            df_raw.groupby("date")["VALUE"]
            .mean()
            .reset_index()
        )
        df_daily.columns = ["date", "price"]
        df_daily = df_daily.sort_values("date").reset_index(drop=True)

        mask = (df_daily["date"] >= pd.Timestamp(start)) & \
               (df_daily["date"] <= pd.Timestamp(end))
        df = df_daily[mask].reset_index(drop=True)

        if not df.empty:
            print(f"  OMIE: {len(df)} daily points")
            return df

    except ImportError:
        print("  OMIEData not installed — run: pip install OMIEData")
    except Exception as e:
        print(f"  OMIE failed: {e}")

    # Fallback: Yahoo Finance natural gas (correlated with Spanish electricity)
    print("  Falling back to Yahoo Finance NG=F...")
    df = yf.download(
        "NG=F",
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        raise HTTPException(status_code=502, detail="All energy sources failed.")
    df = df[["Close"]].reset_index()
    df.columns = ["date", "price"]
    df["date"]  = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


# ── 4. PET ────────────────────────────────────────────────────────────────────

def fetch_pet(start: datetime, end: datetime) -> pd.DataFrame:
    df = yf.download(
        "BZ=F",
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        df = yf.download("CL=F", start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False,
                         auto_adjust=True)
    if df.empty:
        raise ValueError("No PET proxy data from Yahoo Finance")
    df = df[["Close"]].reset_index()
    df.columns = ["date", "price"]
    df["date"]  = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


FETCHERS = {
    "barley":    fetch_barley,
    "aluminium": fetch_aluminium,
    "energy":    fetch_energy,
    "pet":       fetch_pet,
}


# ── Stats helpers ─────────────────────────────────────────────────────────────

def compute_current(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 2:
        return {}
    df   = df.sort_values("date").reset_index(drop=True)
    spot = round(float(df["price"].iloc[-1]), 2)

    prev_1     = float(df["price"].iloc[-2])
    change_24h = round((spot - prev_1) / prev_1 * 100, 2) if prev_1 else 0.0

    last_date  = df["date"].iloc[-1]
    target_30d = last_date - timedelta(days=30)
    idx_30d    = (df["date"] - target_30d).abs().idxmin()
    price_30d  = float(df["price"].iloc[idx_30d])
    change_30d = round((spot - price_30d) / price_30d * 100, 2) if price_30d else 0.0

    last_5 = df["price"].tail(5).values
    trend  = ("up"   if last_5[-1] > last_5[0] else
              "down" if last_5[-1] < last_5[0] else "flat")

    return {
        "spot":         spot,
        "change24hPct": change_24h,
        "change30dPct": change_30d,
        "trend":        trend,
        "lastUpdated":  last_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def compute_historical(df: pd.DataFrame, range_label: str) -> dict:
    points = [
        {"date": row["date"].strftime("%Y-%m-%d"), "value": round(float(row["price"]), 2)}
        for _, row in df.iterrows()
    ]
    return {"range": range_label, "points": points}


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/prices/{commodity}")
def get_prices(
    commodity:   str,
    start_date:  str = Query(default=None, description="YYYY-MM-DD. Defaults to 6 months ago."),
    end_date:    str = Query(default=None, description="YYYY-MM-DD. Defaults to today."),
    range_label: str = Query(default="6m"),
) -> dict:
    key = commodity.lower().strip()
    if key not in COMMODITY_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown commodity '{commodity}'. "
                   f"Valid: {sorted(set(COMMODITY_MAP.keys()))}",
        )
    try:
        end   = datetime.strptime(end_date,   "%Y-%m-%d") if end_date   else datetime.now()
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else end - timedelta(days=180)
        if COMMODITY_MAP[key] == "barley":
            df_csv = pd.read_csv("app/data/train.csv", parse_dates=["ds"])
            csv_end   = df_csv["ds"].max()
            csv_start = csv_end - timedelta(days=180)
            end   = datetime.strptime(end_date,   "%Y-%m-%d") if end_date   else csv_end.to_pydatetime()
            start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else csv_start.to_pydatetime()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if start > end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    canonical = COMMODITY_MAP[key]
    try:
        df = FETCHERS[canonical](start, end)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch '{commodity}': {str(e)}")

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data for '{commodity}' between {start.date()} and {end.date()}."
        )

    return {
        "id":             canonical,
        "unit":           UNITS[canonical],
        "source":         SOURCES[canonical],
        "current":        compute_current(df),
        "historicalData": compute_historical(df, range_label),
    }