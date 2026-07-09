from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import requests
from bson import ObjectId
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pymongo.collection import Collection

from app.auth import create_token, hash_password, user_id, verify_password
from app.auth import get_current_user as auth_get_current_user
from app.backup import export_user_data, import_user_data, parse_backup_json
from app.db import get_db
from app.gold_price import fetch_stats_gold_prices
from cron.gold_history import get_day_history

GOLD_HISTORY_LABELS = {"浙商黄金", "伦敦金"}
GOLD_HISTORY_UNITS = {
    "浙商黄金": "元/克",
    "伦敦金": "美元/盎司",
}

app = FastAPI(title="AuLog", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def ensure_indexes() -> None:
    db = get_db()
    db.users.create_index("username", unique=True)
    for name in ("t_records", "ing_records", "selled_records", "ing_allocations"):
        db[name].create_index("user_id")
    db.gold_price_samples.create_index([("label", 1), ("date", 1)])
    db.gold_price_samples.create_index([("label", 1), ("sampled_at", -1)])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail="无效的 ID")
    return ObjectId(value)


def serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            out["id"] = str(value)
        elif key == "user_id":
            continue
        elif key == "password_hash":
            continue
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def round2(value: float) -> float:
    return round(value, 2)


def _is_valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def ing_allocated_count(ing_id: ObjectId, allocations: Collection) -> float:
    total = 0.0
    for row in allocations.find({"ing_id": ing_id}):
        total += row["count"]
    return round2(total)


def t_allocated_count(t_id: ObjectId, allocations: Collection) -> float:
    total = 0.0
    for row in allocations.find({"target_type": "T_MATCH", "target_id": t_id}):
        total += row["count"]
    return round2(total)


def t_push_amount(t_id: ObjectId, allocations: Collection) -> float:
    total = 0.0
    for row in allocations.find({"target_type": "T_MATCH", "target_id": t_id}):
        total += row["amount"]
    return round2(total)


def enrich_t(doc: dict[str, Any], allocations: Collection) -> dict[str, Any]:
    item = serialize(doc) or {}
    count = float(item["count"])
    pop_amount = float(item["pop_amount"])
    allocated = t_allocated_count(doc["_id"], allocations)
    push = t_push_amount(doc["_id"], allocations)

    item["price"] = round2(pop_amount / count) if count else 0
    item["allocated_count"] = allocated
    item["remaining_count"] = round2(max(count - allocated, 0))
    item["push_amount"] = push if allocated > 0 else None
    if allocated > 0:
        matched_pop = round2(allocated * item["price"])
        item["gain"] = round2(matched_pop - push)
    else:
        item["gain"] = None

    if allocated <= 0:
        item["status"] = "OPEN"
    elif allocated + 1e-9 < count:
        item["status"] = "PARTIAL"
    else:
        item["status"] = "CLOSED"
    return item


def t_record_sort_ts(item: dict[str, Any]) -> float:
    sold_at = item.get("sold_at")
    if sold_at and isinstance(sold_at, str):
        if len(sold_at) == 10 and sold_at[4] == "-":
            try:
                return datetime.strptime(sold_at, "%Y-%m-%d").timestamp()
            except ValueError:
                pass
        if len(sold_at) == 4 and sold_at.isdigit():
            try:
                year = datetime.utcnow().year
                return datetime.strptime(f"{year}{sold_at}", "%Y%m%d").timestamp()
            except ValueError:
                pass
    for field in ("updated_at", "created_at"):
        val = item.get(field)
        if val and isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
    return 0.0


def sort_t_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            1 if r.get("status") == "CLOSED" else 0,
            -t_record_sort_ts(r),
            str(r.get("id", "")),
        ),
    )


def ing_record_sort_ts(item: dict[str, Any]) -> float:
    date = item.get("date")
    if date and isinstance(date, str):
        if len(date) == 10 and date[4] == "-":
            try:
                return datetime.strptime(date, "%Y-%m-%d").timestamp()
            except ValueError:
                pass
        if len(date) == 4 and date.isdigit():
            try:
                year = datetime.utcnow().year
                return datetime.strptime(f"{year}{date}", "%Y%m%d").timestamp()
            except ValueError:
                pass
    for field in ("updated_at", "created_at"):
        val = item.get(field)
        if val and isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
    return 0.0


def sort_ing_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            1 if r.get("allocation_status") == "FULLY_ALLOCATED" else 0,
            -ing_record_sort_ts(r),
            str(r.get("id", "")),
        ),
    )


def enrich_ing(doc: dict[str, Any], allocations: Collection) -> dict[str, Any]:
    item = serialize(doc) or {}
    count = float(item["count"])
    allocated = ing_allocated_count(doc["_id"], allocations)
    to_t = round2(
        sum(
            row["count"]
            for row in allocations.find(
                {"ing_id": doc["_id"], "target_type": "T_MATCH"}
            )
        )
    )
    to_selled = round2(
        sum(
            row["count"]
            for row in allocations.find(
                {"ing_id": doc["_id"], "target_type": "SELLED"}
            )
        )
    )

    item["allocated_count"] = allocated
    item["remaining_count"] = round2(max(count - allocated, 0))
    item["allocated_to_t"] = to_t
    item["allocated_to_selled"] = to_selled
    item["is_change"] = to_t > 0
    if allocated <= 0:
        item["allocation_status"] = "UNALLOCATED"
    elif allocated + 1e-9 < count:
        item["allocation_status"] = "PARTIAL"
    else:
        item["allocation_status"] = "FULLY_ALLOCATED"
    return item


def enrich_selled(doc: dict[str, Any]) -> dict[str, Any]:
    item = serialize(doc) or {}
    buy_amount = float(item["buy_amount"])
    sell_amount = float(item["sell_amount"])
    count = float(item["count"])
    item["gain"] = round2(sell_amount - buy_amount)
    item["buy_price"] = round2(buy_amount / count) if count else 0
    item["sell_price"] = round2(sell_amount / count) if count else 0
    return item


def get_ing_or_404(
    ing_id: str, ing_col: Collection, uid: ObjectId
) -> dict[str, Any]:
    doc = ing_col.find_one({"_id": oid(ing_id), "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="进货记录不存在")
    return doc


def get_t_or_404(t_id: str, t_col: Collection, uid: ObjectId) -> dict[str, Any]:
    doc = t_col.find_one({"_id": oid(t_id), "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="倒T 记录不存在")
    return doc


def get_alloc_or_404(
    allocation_id: str, alloc_col: Collection, uid: ObjectId
) -> dict[str, Any]:
    doc = alloc_col.find_one({"_id": oid(allocation_id), "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="分配记录不存在")
    return doc


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AuthBody(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class TCreate(BaseModel):
    mark: str = ""
    count: float = Field(gt=0)
    pop_amount: float = Field(gt=0)
    sold_at: Optional[str] = None


class IngCreate(BaseModel):
    date: str
    mark: str = ""
    price: float = Field(gt=0)
    count: float = Field(gt=0)
    amount: Optional[float] = None


class TMatchAllocation(BaseModel):
    ing_id: str
    t_id: str
    count: float = Field(gt=0)


class SelledAllocation(BaseModel):
    ing_id: str
    date: str
    mark: str = ""
    count: float = Field(gt=0)
    sell_price: float = Field(gt=0)


def auth_response(user: dict[str, Any]) -> dict[str, str]:
    username = user["username"]
    token = create_token(user["_id"], username)
    return {"token": token, "username": username}


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------


@app.post("/api/auth/register", status_code=201)
def register(body: AuthBody):
    db = get_db()
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.users.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="用户名已存在")
    doc = {
        "username": username,
        "password_hash": hash_password(body.password),
        "created_at": datetime.utcnow(),
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return auth_response(doc)


@app.post("/api/auth/login")
def login(body: AuthBody):
    db = get_db()
    username = body.username.strip()
    user = db.users.find_one({"username": username})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return auth_response(user)


@app.get("/api/auth/me")
def me(current_user: dict[str, Any] = Depends(auth_get_current_user)):
    return serialize(current_user)


# ---------------------------------------------------------------------------
# Routes — 倒T
# ---------------------------------------------------------------------------


@app.get("/api/t-records")
def list_t_records(uid: ObjectId = Depends(user_id)):
    db = get_db()
    allocations = db.ing_allocations
    rows = [
        enrich_t(doc, allocations)
        for doc in db.t_records.find({"user_id": uid})
    ]
    return sort_t_records(rows)


@app.post("/api/t-records", status_code=201)
def create_t_record(body: TCreate, uid: ObjectId = Depends(user_id)):
    db = get_db()
    doc = {
        "user_id": uid,
        "mark": body.mark.strip(),
        "count": round2(body.count),
        "pop_amount": round2(body.pop_amount),
        "sold_at": body.sold_at,
        "created_at": datetime.utcnow(),
    }
    result = db.t_records.insert_one(doc)
    doc["_id"] = result.inserted_id
    return enrich_t(doc, db.ing_allocations)


@app.patch("/api/t-records/{record_id}")
def update_t_record(record_id: str, body: TCreate, uid: ObjectId = Depends(user_id)):
    db = get_db()
    doc = get_t_or_404(record_id, db.t_records, uid)
    allocations = db.ing_allocations
    allocated = t_allocated_count(doc["_id"], allocations)
    new_count = round2(body.count)

    if new_count + 1e-9 < allocated:
        raise HTTPException(
            status_code=400,
            detail=f"克数不能小于已配对克数 {allocated} 克",
        )

    update = {
        "mark": body.mark.strip(),
        "count": new_count,
        "pop_amount": round2(body.pop_amount),
        "sold_at": body.sold_at,
        "updated_at": datetime.utcnow(),
    }
    db.t_records.update_one({"_id": doc["_id"], "user_id": uid}, {"$set": update})
    doc.update(update)
    return enrich_t(doc, allocations)


@app.delete("/api/t-records/{record_id}")
def delete_t_record(record_id: str, uid: ObjectId = Depends(user_id)):
    db = get_db()
    _id = oid(record_id)
    get_t_or_404(record_id, db.t_records, uid)
    if db.ing_allocations.count_documents(
        {"user_id": uid, "target_type": "T_MATCH", "target_id": _id}
    ):
        raise HTTPException(status_code=400, detail="已有配对分配，无法删除")
    result = db.t_records.delete_one({"_id": _id, "user_id": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — ing
# ---------------------------------------------------------------------------


@app.get("/api/ing-records")
def list_ing_records(uid: ObjectId = Depends(user_id)):
    db = get_db()
    allocations = db.ing_allocations
    rows = [
        enrich_ing(doc, allocations)
        for doc in db.ing_records.find({"user_id": uid})
    ]
    return sort_ing_records(rows)


@app.post("/api/ing-records", status_code=201)
def create_ing_record(body: IngCreate, uid: ObjectId = Depends(user_id)):
    db = get_db()
    amount = round2(body.amount if body.amount is not None else body.price * body.count)
    doc = {
        "user_id": uid,
        "date": body.date.strip(),
        "mark": body.mark.strip(),
        "price": round2(body.price),
        "count": round2(body.count),
        "amount": amount,
        "created_at": datetime.utcnow(),
    }
    result = db.ing_records.insert_one(doc)
    doc["_id"] = result.inserted_id
    return enrich_ing(doc, db.ing_allocations)


@app.patch("/api/ing-records/{record_id}")
def update_ing_record(record_id: str, body: IngCreate, uid: ObjectId = Depends(user_id)):
    db = get_db()
    doc = get_ing_or_404(record_id, db.ing_records, uid)
    allocations = db.ing_allocations
    allocated = ing_allocated_count(doc["_id"], allocations)
    new_count = round2(body.count)
    new_price = round2(body.price)

    if new_count + 1e-9 < allocated:
        raise HTTPException(
            status_code=400,
            detail=f"克数不能小于已分配克数 {allocated} 克",
        )

    amount = round2(body.amount if body.amount is not None else new_price * new_count)
    update = {
        "date": body.date.strip(),
        "mark": body.mark.strip(),
        "price": new_price,
        "count": new_count,
        "amount": amount,
        "updated_at": datetime.utcnow(),
    }
    db.ing_records.update_one({"_id": doc["_id"], "user_id": uid}, {"$set": update})

    for alloc in allocations.find({"user_id": uid, "ing_id": doc["_id"], "target_type": "T_MATCH"}):
        new_amount = round2(float(alloc["count"]) * new_price)
        allocations.update_one({"_id": alloc["_id"]}, {"$set": {"amount": new_amount}})

    doc.update(update)
    return enrich_ing(doc, allocations)


@app.delete("/api/ing-records/{record_id}")
def delete_ing_record(record_id: str, uid: ObjectId = Depends(user_id)):
    db = get_db()
    _id = oid(record_id)
    get_ing_or_404(record_id, db.ing_records, uid)
    if db.ing_allocations.count_documents({"user_id": uid, "ing_id": _id}):
        raise HTTPException(status_code=400, detail="已有分配记录，无法删除")
    result = db.ing_records.delete_one({"_id": _id, "user_id": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — selled
# ---------------------------------------------------------------------------


@app.get("/api/selled-records")
def list_selled_records(uid: ObjectId = Depends(user_id)):
    db = get_db()
    rows = [
        enrich_selled(doc)
        for doc in db.selled_records.find({"user_id": uid}).sort("_id", -1)
    ]
    return rows


@app.delete("/api/selled-records/{record_id}")
def delete_selled_record(record_id: str, uid: ObjectId = Depends(user_id)):
    db = get_db()
    _id = oid(record_id)
    if not db.selled_records.find_one({"_id": _id, "user_id": uid}):
        raise HTTPException(status_code=404, detail="记录不存在")
    if db.ing_allocations.count_documents(
        {"user_id": uid, "target_type": "SELLED", "target_id": _id}
    ):
        db.ing_allocations.delete_many(
            {"user_id": uid, "target_type": "SELLED", "target_id": _id}
        )
    result = db.selled_records.delete_one({"_id": _id, "user_id": uid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — 分配
# ---------------------------------------------------------------------------


@app.get("/api/allocations")
def list_allocations(uid: ObjectId = Depends(user_id)):
    db = get_db()
    rows = [
        serialize(doc)
        for doc in db.ing_allocations.find({"user_id": uid}).sort("_id", -1)
    ]
    return rows


@app.post("/api/allocations/t-match", status_code=201)
def allocate_to_t(body: TMatchAllocation, uid: ObjectId = Depends(user_id)):
    db = get_db()
    ing = get_ing_or_404(body.ing_id, db.ing_records, uid)
    t_doc = get_t_or_404(body.t_id, db.t_records, uid)
    allocations = db.ing_allocations

    ing_remaining = round2(float(ing["count"]) - ing_allocated_count(ing["_id"], allocations))
    if body.count > ing_remaining + 1e-9:
        raise HTTPException(status_code=400, detail=f"进货剩余克数不足，仅剩 {ing_remaining} 克")

    t_remaining = round2(float(t_doc["count"]) - t_allocated_count(t_doc["_id"], allocations))
    if body.count > t_remaining + 1e-9:
        raise HTTPException(status_code=400, detail=f"倒T 剩余可配对克数不足，仅剩 {t_remaining} 克")

    t_count = float(t_doc["count"])
    t_sell_price = float(t_doc["pop_amount"]) / t_count if t_count else 0
    ing_buy_price = float(ing["price"])
    if t_sell_price + 1e-9 < ing_buy_price:
        raise HTTPException(
            status_code=400,
            detail=(
                f"倒T 卖价 {round2(t_sell_price)} 低于进货价 {round2(ing_buy_price)}，"
                "不接受亏损配对"
            ),
        )

    amount = round2(body.count * ing_buy_price)
    alloc = {
        "user_id": uid,
        "ing_id": ing["_id"],
        "target_type": "T_MATCH",
        "target_id": t_doc["_id"],
        "count": round2(body.count),
        "amount": amount,
        "created_at": datetime.utcnow(),
    }
    result = db.ing_allocations.insert_one(alloc)
    alloc["_id"] = result.inserted_id

    return {
        "allocation": serialize(alloc),
        "t_record": enrich_t(t_doc, allocations),
        "ing_record": enrich_ing(ing, allocations),
    }


@app.post("/api/allocations/selled", status_code=201)
def allocate_to_selled(body: SelledAllocation, uid: ObjectId = Depends(user_id)):
    db = get_db()
    ing = get_ing_or_404(body.ing_id, db.ing_records, uid)
    allocations = db.ing_allocations

    ing_remaining = round2(float(ing["count"]) - ing_allocated_count(ing["_id"], allocations))
    if body.count > ing_remaining + 1e-9:
        raise HTTPException(status_code=400, detail=f"进货剩余克数不足，仅剩 {ing_remaining} 克")

    buy_price = float(ing["price"])
    buy_amount = round2(body.count * buy_price)
    sell_amount = round2(body.count * body.sell_price)

    selled_doc = {
        "user_id": uid,
        "date": body.date.strip(),
        "mark": body.mark.strip() or ing.get("mark", ""),
        "buy_price": round2(buy_price),
        "count": round2(body.count),
        "buy_amount": buy_amount,
        "sell_price": round2(body.sell_price),
        "sell_amount": sell_amount,
        "created_at": datetime.utcnow(),
    }
    selled_result = db.selled_records.insert_one(selled_doc)
    selled_doc["_id"] = selled_result.inserted_id

    alloc = {
        "user_id": uid,
        "ing_id": ing["_id"],
        "target_type": "SELLED",
        "target_id": selled_doc["_id"],
        "count": round2(body.count),
        "amount": buy_amount,
        "created_at": datetime.utcnow(),
    }
    alloc_result = db.ing_allocations.insert_one(alloc)
    alloc["_id"] = alloc_result.inserted_id

    return {
        "allocation": serialize(alloc),
        "selled_record": enrich_selled(selled_doc),
        "ing_record": enrich_ing(ing, allocations),
    }


@app.delete("/api/allocations/{allocation_id}")
def delete_allocation(allocation_id: str, uid: ObjectId = Depends(user_id)):
    db = get_db()
    alloc = get_alloc_or_404(allocation_id, db.ing_allocations, uid)

    if alloc["target_type"] == "SELLED":
        db.selled_records.delete_one(
            {"_id": alloc["target_id"], "user_id": uid}
        )

    db.ing_allocations.delete_one({"_id": alloc["_id"], "user_id": uid})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — 统计
# ---------------------------------------------------------------------------


@app.get("/api/stats/gold-price/history")
def get_gold_price_history(
    date: str,
    label: str = "浙商黄金",
    uid: ObjectId = Depends(user_id),
):
    del uid
    if not _is_valid_date(date):
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD")
    if label not in GOLD_HISTORY_LABELS:
        raise HTTPException(status_code=400, detail=f"不支持的品种: {label}")

    db = get_db()
    payload = get_day_history(db, label, date)
    payload["unit"] = GOLD_HISTORY_UNITS[label]
    return payload


@app.get("/api/stats/gold-price")
def get_gold_price(refresh: bool = False, uid: ObjectId = Depends(user_id)):
    del uid
    try:
        return fetch_stats_gold_prices(force=refresh)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"获取金价失败: {exc}") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"解析金价失败: {exc}") from exc


# ---------------------------------------------------------------------------
# Routes — 数据存档
# ---------------------------------------------------------------------------


def _content_disposition_attachment(filename: str) -> str:
    """HTTP 头只能用 latin-1；中文用户名需用 RFC 5987 的 filename*。"""
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "aulog-backup.json"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    utf8_name = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"


@app.get("/api/data/export")
def export_data(
    current_user: dict[str, Any] = Depends(auth_get_current_user),
    uid: ObjectId = Depends(user_id),
):
    db = get_db()
    payload = export_user_data(db, uid, current_user["username"])
    filename = f"aulog-backup-{current_user['username']}-{datetime.utcnow():%Y%m%d-%H%M%S}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )


@app.post("/api/data/import")
async def import_data(
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(auth_get_current_user),
    uid: ObjectId = Depends(user_id),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="请上传 .json 备份文件")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="备份文件为空")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="备份文件不能超过 10MB")

    payload = parse_backup_json(raw)
    db = get_db()
    counts = import_user_data(db, uid, payload)

    backup_user = payload.get("username")
    return {
        "ok": True,
        "backup_username": backup_user,
        "current_username": current_user["username"],
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# Static frontend (Vue build in static/dist)
# ---------------------------------------------------------------------------

root_dir = os.path.dirname(os.path.dirname(__file__))
static_dir = os.path.join(root_dir, "static")
dist_dir = os.path.join(static_dir, "dist")
assets_dir = os.path.join(dist_dir, "assets")

if os.path.isdir(dist_dir):
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index():
        index_path = os.path.join(dist_dir, "index.html")
        if not os.path.isfile(index_path):
            raise HTTPException(status_code=404, detail="前端未构建，请运行 cd frontend && npm run build")
        return FileResponse(index_path)
else:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        legacy_index = os.path.join(static_dir, "index.html")
        if os.path.isfile(legacy_index):
            return FileResponse(legacy_index)
        raise HTTPException(
            status_code=404,
            detail="前端未构建，请运行 cd frontend && npm install && npm run build",
        )
