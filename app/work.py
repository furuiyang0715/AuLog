from __future__ import annotations

import calendar
import re
from datetime import datetime
from typing import Any, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database

from app.auth import user_id
from app.db import get_db

router = APIRouter(prefix="/api/work", tags=["work"])

HOURS_PER_DAY = 15.0
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DAY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


class WorkSalaryBody(BaseModel):
    month: str
    amount: float = Field(gt=0)


class WorkDayBody(BaseModel):
    working: bool


def round2(value: float) -> float:
    return round(float(value), 2)


def require_month(value: str) -> str:
    if not value or not _MONTH_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="月份必须是 YYYY-MM")
    return value


def require_day(value: str) -> str:
    if not value or not _DAY_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="日期必须是有效的 YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效日期") from exc
    return value


def split_month(month: str) -> tuple[int, int]:
    year, month_n = month.split("-")
    return int(year), int(month_n)


def format_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def prev_month_of(month: str) -> str:
    year, month_n = split_month(month)
    if month_n == 1:
        return format_month(year - 1, 12)
    return format_month(year, month_n - 1)


def days_in_month(month: str) -> int:
    year, month_n = split_month(month)
    return calendar.monthrange(year, month_n)[1]


def month_date_range(month: str) -> tuple[str, str]:
    return f"{month}-01", f"{month}-{days_in_month(month):02d}"


def list_work_dates(db: Database, uid: ObjectId, month: str) -> list[str]:
    start, end = month_date_range(month)
    rows = db.work_days.find(
        {"user_id": uid, "date": {"$gte": start, "$lte": end}},
        {"date": 1},
    )
    return sorted(row["date"] for row in rows)


def get_salary(db: Database, uid: ObjectId, month: str) -> float | None:
    doc = db.work_salaries.find_one({"user_id": uid, "month": month})
    if not doc:
        return None
    return round2(doc["amount"])


def month_summary(db: Database, uid: ObjectId, month: str) -> dict[str, Any]:
    prev_month = prev_month_of(month)
    prev_salary = get_salary(db, uid, prev_month)
    work_dates = list_work_dates(db, uid, month)
    prev_work_dates = list_work_dates(db, uid, prev_month)
    prev_days = days_in_month(prev_month)

    if prev_work_dates:
        rate_basis: Literal["attendance", "calendar"] = "attendance"
        base_days = len(prev_work_dates)
    else:
        rate_basis = "calendar"
        base_days = prev_days

    base_hours = round2(base_days * HOURS_PER_DAY)
    hourly_rate = None
    daily_estimate = None
    month_total = None
    if prev_salary is not None and base_hours > 0:
        hourly_rate = round2(prev_salary / base_hours)
        daily_estimate = round2(hourly_rate * HOURS_PER_DAY)
        month_total = round2(daily_estimate * len(work_dates))

    return {
        "month": month,
        "prev_month": prev_month,
        "days_in_month": days_in_month(month),
        "days_in_prev_month": prev_days,
        "hours_per_day": HOURS_PER_DAY,
        "prev_salary": prev_salary,
        "work_dates": work_dates,
        "prev_work_count": len(prev_work_dates),
        "rate_basis": rate_basis,
        "base_days": base_days,
        "base_hours": base_hours,
        "hourly_rate": hourly_rate,
        "daily_estimate": daily_estimate,
        "month_total": month_total,
    }


@router.get("/month")
def get_work_month(month: str, uid: ObjectId = Depends(user_id)):
    month = require_month(month)
    return month_summary(get_db(), uid, month)


@router.put("/salary")
def upsert_work_salary(body: WorkSalaryBody, uid: ObjectId = Depends(user_id)):
    month = require_month(body.month)
    db = get_db()
    amount = round2(body.amount)
    now = datetime.utcnow()
    existing = db.work_salaries.find_one({"user_id": uid, "month": month})
    if existing:
        db.work_salaries.update_one(
            {"_id": existing["_id"]},
            {"$set": {"amount": amount, "updated_at": now}},
        )
    else:
        db.work_salaries.insert_one(
            {
                "user_id": uid,
                "month": month,
                "amount": amount,
                "created_at": now,
            }
        )
    return {"ok": True, "month": month, "amount": amount}


@router.put("/days/{day}")
def set_work_day(day: str, body: WorkDayBody, uid: ObjectId = Depends(user_id)):
    day = require_day(day)
    db = get_db()
    existing = db.work_days.find_one({"user_id": uid, "date": day})
    if body.working:
        if not existing:
            db.work_days.insert_one(
                {
                    "user_id": uid,
                    "date": day,
                    "hours": HOURS_PER_DAY,
                    "created_at": datetime.utcnow(),
                }
            )
    elif existing:
        db.work_days.delete_one({"_id": existing["_id"]})
    return month_summary(db, uid, day[:7])
