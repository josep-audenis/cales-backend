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

BARLEY_CSV      = "app/data/train.csv"
BARLEY_MAX_DATE = datetime(2025, 11, 2)   # hardcoded fallback if CSV read fails


# ── Date helpers ──────────────────────────────────────────────────────────────

def _barley_max_date() -> datetime:
    """Return the last date in the barley CSV, falling back to the hardcoded value."""
    try:
        df = pd.read_csv(BARLEY_CSV, parse_dates=["ds"])
        return df["ds"].max().to_pydatetime()
    except Exception:
        return BARLEY_MAX_DATE


def _resolve_dates(end_date: str | None, days_back: int,
                   is_barley: bool) -> tuple[datetime, datetime]:
    """
    Resolve (start, end) from the user-facing params.
    - end_date: YYYY-MM-DD string or None (defaults to today / barley max)
    - days_back: positive int, how many days to go back from end
    - is_barley: if True, ceiling is the last date in the CSV
    """
    today    = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ceiling  = _barley_max_date() if is_barley else today

    if end_date is not None:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400,
                                detail="Invalid end_date format — use YYYY-MM-DD.")
        if end > ceiling:
            if is_barley:
                end = ceiling          # silently clamp to last available barley date
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"end_date {end.date()} is in the future. "
                        f"Maximum allowed: {ceiling.date()}."
                    ),
                )
    else:
        end = ceiling

    start = end - timedelta(days=days_back)
    return start, end


# ── 1. BARLEY ─────────────────────────────────────────────────────────────────

def fetch_barley(start: datetime, end: datetime) -> pd.DataFrame:
    df = pd.read_csv(BARLEY_CSV, parse_dates=["ds"])[["ds", "y"]]
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
            return df

    except ImportError:
        print("  OMIEData not installed — run: pip install OMIEData")
    except Exception as e:
        print(f"  OMIE failed: {e}")

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


def compute_historical(df: pd.DataFrame, start: datetime, end: datetime) -> dict:
    points = [
        {"date": row["date"].strftime("%Y-%m-%d"), "value": round(float(row["price"]), 2)}
        for _, row in df.iterrows()
    ]
    return {
        "start":  start.strftime("%Y-%m-%d"),
        "end":    end.strftime("%Y-%m-%d"),
        "points": points,
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/prices/{commodity}")
def get_prices(
    commodity: str,
    days_back: int  = Query(default=180, description="Number of days to look back. Must be a positive integer."),
    end_date:  str  = Query(default=None, description="End date YYYY-MM-DD. Cannot be in the future. Defaults to today (or last CSV date for barley)."),
) -> dict:

    # Validate days_back
    if days_back <= 0:
        raise HTTPException(status_code=400,
                            detail="days_back must be a positive integer.")

    # Validate commodity
    key = commodity.lower().strip()
    if key not in COMMODITY_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown commodity '{commodity}'. "
                   f"Valid: {sorted(set(COMMODITY_MAP.keys()))}",
        )

    canonical  = COMMODITY_MAP[key]
    is_barley  = canonical == "barley"
    start, end = _resolve_dates(end_date, days_back, is_barley)

    try:
        df = FETCHERS[canonical](start, end)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502,
                            detail=f"Failed to fetch '{commodity}': {str(e)}")

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
        "historicalData": compute_historical(df, start, end),
    }