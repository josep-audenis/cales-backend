# app/db/updater.py
from datetime import datetime, timedelta, timezone
from app.db.models import Session, Commodity, PricePoint
from app.api.routes.prices import (
    fetch_barley, fetch_aluminium, fetch_energy, fetch_pet
)


def update_prices():
    db    = Session()
    end   = datetime.now()
    start = end - timedelta(days=180)

    fetchers = {
        "barley":    fetch_barley,
        "aluminium": fetch_aluminium,
        "energy":    fetch_energy,
        "pet":       fetch_pet,
    }

    for cid, fetcher in fetchers.items():
        print(f"Updating {cid}...")
        try:
            df = fetcher(start, end)
            if df.empty:
                print(f"  No data for {cid}")
                continue

            c = db.get(Commodity, cid)
            if not c:
                print(f"  Commodity {cid} not found in DB — run seed first")
                continue

            # Delete old price points and replace
            db.query(PricePoint).filter_by(commodity_id=cid).delete()
            for _, row in df.iterrows():
                # Fix 1: handle both Timestamp and string dates robustly
                date_val = row["date"]
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)[:10]

                db.add(PricePoint(
                    commodity_id=cid,
                    date=date_str,
                    value=round(float(row["price"]), 2),
                ))

            # Update current stats
            df = df.sort_values("date").reset_index(drop=True)
            last      = df.iloc[-1]
            prev      = df.iloc[-2] if len(df) > 1 else last

            # 30d change
            target_30d = last["date"] - timedelta(days=30)
            idx_30d    = (df["date"] - target_30d).abs().idxmin()
            price_30d  = float(df["price"].iloc[idx_30d])

            c.spot           = round(float(last["price"]), 2)
            c.change_24h_pct = round(
                (float(last["price"]) - float(prev["price"])) /
                float(prev["price"]) * 100, 2
            ) if float(prev["price"]) else 0.0
            c.change_30d_pct = round(
                (float(last["price"]) - price_30d) /
                price_30d * 100, 2
            ) if price_30d else 0.0

            last_5  = df["price"].tail(5).values
            c.trend = ("up"   if last_5[-1] > last_5[0] else
                       "down" if last_5[-1] < last_5[0] else "flat")

            # Fix 2: timezone-aware datetime instead of deprecated utcnow()
            c.last_price_update = datetime.now(timezone.utc)

            db.commit()
            print(f"  {cid}: {len(df)} points | "
                  f"spot={c.spot} | "
                  f"24h={c.change_24h_pct:+.2f}% | "
                  f"30d={c.change_30d_pct:+.2f}% | "
                  f"trend={c.trend}")

        except Exception as e:
            print(f"  {cid} failed: {e}")
            db.rollback()

    db.close()
    print("\nPrice update complete")


if __name__ == "__main__":
    update_prices()