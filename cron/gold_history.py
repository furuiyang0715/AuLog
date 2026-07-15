from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pymongo.database import Database

COLLECTION = "gold_price_samples"


def ensure_indexes(db: Database) -> None:
    col = db[COLLECTION]
    col.create_index([("label", 1), ("date", 1)])
    col.create_index([("label", 1), ("sampled_at", -1)])


def save_price_record(
    db: Database,
    label: str,
    price: float,
    timestamp: datetime | None = None,
) -> None:
    ts = timestamp or datetime.now()
    db[COLLECTION].insert_one(
        {
            "label": label,
            "price": round(price, 2),
            "sampled_at": ts,
            "date": ts.strftime("%Y-%m-%d"),
        }
    )


def _rows_to_history(
    label: str,
    start_date: str,
    end_date: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {
            "label": label,
            "start_date": start_date,
            "end_date": end_date,
            "points": [],
            "summary": None,
        }

    points: list[dict[str, Any]] = []
    prices: list[float] = []
    for row in rows:
        price = float(row["price"])
        prices.append(price)
        sampled_at = row["sampled_at"]
        if isinstance(sampled_at, datetime):
            time_str = sampled_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(sampled_at)
        points.append({"time": time_str, "price": price})

    return {
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
        "points": points,
        "summary": {
            "count": len(prices),
            "high": max(prices),
            "low": min(prices),
            "open": prices[0],
            "close": prices[-1],
        },
    }


def get_day_history(db: Database, label: str, day: str) -> dict[str, Any]:
    rows = list(
        db[COLLECTION].find({"label": label, "date": day}).sort("sampled_at", 1)
    )
    payload = _rows_to_history(label, day, day, rows)
    payload["date"] = day
    return payload


def get_range_history(
    db: Database,
    label: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    rows = list(
        db[COLLECTION]
        .find({"label": label, "date": {"$gte": start_date, "$lte": end_date}})
        .sort("sampled_at", 1)
    )
    return _rows_to_history(label, start_date, end_date, rows)


def get_today_stats(db: Database, label: str) -> dict[str, Any] | None:
    today = date.today().strftime("%Y-%m-%d")
    rows = list(
        db[COLLECTION].find({"label": label, "date": today}).sort("sampled_at", 1)
    )
    if not rows:
        return None

    prices = [float(row["price"]) for row in rows]
    records: list[dict[str, Any]] = []
    for row in rows:
        sampled_at = row["sampled_at"]
        if isinstance(sampled_at, datetime):
            time_str = sampled_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(sampled_at)
        records.append({"time": time_str, "price": float(row["price"])})

    return {
        "high": max(prices),
        "low": min(prices),
        "count": len(prices),
        "first": prices[0],
        "last": prices[-1] if len(prices) > 1 else None,
        "records": records,
    }
