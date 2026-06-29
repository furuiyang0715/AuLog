from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Literal, Optional

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pymongo.collection import Collection

from app.db import get_db

app = FastAPI(title="AuLog", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def round2(value: float) -> float:
    return round(value, 2)


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


def get_ing_or_404(ing_id: str, ing_col: Collection) -> dict[str, Any]:
    doc = ing_col.find_one({"_id": oid(ing_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="进货记录不存在")
    return doc


def get_t_or_404(t_id: str, t_col: Collection) -> dict[str, Any]:
    doc = t_col.find_one({"_id": oid(t_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="倒T 记录不存在")
    return doc


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Routes — 倒T
# ---------------------------------------------------------------------------


@app.get("/api/t-records")
def list_t_records():
    db = get_db()
    allocations = db.ing_allocations
    rows = [enrich_t(doc, allocations) for doc in db.t_records.find().sort("_id", -1)]
    return rows


@app.post("/api/t-records", status_code=201)
def create_t_record(body: TCreate):
    db = get_db()
    doc = {
        "mark": body.mark.strip(),
        "count": round2(body.count),
        "pop_amount": round2(body.pop_amount),
        "sold_at": body.sold_at,
        "created_at": datetime.utcnow(),
    }
    result = db.t_records.insert_one(doc)
    doc["_id"] = result.inserted_id
    return enrich_t(doc, db.ing_allocations)


@app.delete("/api/t-records/{record_id}")
def delete_t_record(record_id: str):
    db = get_db()
    _id = oid(record_id)
    if db.ing_allocations.count_documents({"target_type": "T_MATCH", "target_id": _id}):
        raise HTTPException(status_code=400, detail="已有配对分配，无法删除")
    result = db.t_records.delete_one({"_id": _id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — ing
# ---------------------------------------------------------------------------


@app.get("/api/ing-records")
def list_ing_records():
    db = get_db()
    allocations = db.ing_allocations
    rows = [
        enrich_ing(doc, allocations) for doc in db.ing_records.find().sort("_id", -1)
    ]
    return rows


@app.post("/api/ing-records", status_code=201)
def create_ing_record(body: IngCreate):
    db = get_db()
    amount = round2(body.amount if body.amount is not None else body.price * body.count)
    doc = {
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


@app.delete("/api/ing-records/{record_id}")
def delete_ing_record(record_id: str):
    db = get_db()
    _id = oid(record_id)
    if db.ing_allocations.count_documents({"ing_id": _id}):
        raise HTTPException(status_code=400, detail="已有分配记录，无法删除")
    result = db.ing_records.delete_one({"_id": _id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — selled
# ---------------------------------------------------------------------------


@app.get("/api/selled-records")
def list_selled_records():
    db = get_db()
    rows = [enrich_selled(doc) for doc in db.selled_records.find().sort("_id", -1)]
    return rows


@app.delete("/api/selled-records/{record_id}")
def delete_selled_record(record_id: str):
    db = get_db()
    _id = oid(record_id)
    if db.ing_allocations.count_documents({"target_type": "SELLED", "target_id": _id}):
        db.ing_allocations.delete_many({"target_type": "SELLED", "target_id": _id})
    result = db.selled_records.delete_one({"_id": _id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — 分配
# ---------------------------------------------------------------------------


@app.get("/api/allocations")
def list_allocations():
    db = get_db()
    rows = [serialize(doc) for doc in db.ing_allocations.find().sort("_id", -1)]
    return rows


@app.post("/api/allocations/t-match", status_code=201)
def allocate_to_t(body: TMatchAllocation):
    db = get_db()
    ing = get_ing_or_404(body.ing_id, db.ing_records)
    t_doc = get_t_or_404(body.t_id, db.t_records)
    allocations = db.ing_allocations

    ing_remaining = round2(float(ing["count"]) - ing_allocated_count(ing["_id"], allocations))
    if body.count > ing_remaining + 1e-9:
        raise HTTPException(status_code=400, detail=f"进货剩余克数不足，仅剩 {ing_remaining} 克")

    t_remaining = round2(float(t_doc["count"]) - t_allocated_count(t_doc["_id"], allocations))
    if body.count > t_remaining + 1e-9:
        raise HTTPException(status_code=400, detail=f"倒T 剩余可配对克数不足，仅剩 {t_remaining} 克")

    amount = round2(body.count * float(ing["price"]))
    alloc = {
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
def allocate_to_selled(body: SelledAllocation):
    db = get_db()
    ing = get_ing_or_404(body.ing_id, db.ing_records)
    allocations = db.ing_allocations

    ing_remaining = round2(float(ing["count"]) - ing_allocated_count(ing["_id"], allocations))
    if body.count > ing_remaining + 1e-9:
        raise HTTPException(status_code=400, detail=f"进货剩余克数不足，仅剩 {ing_remaining} 克")

    buy_price = float(ing["price"])
    buy_amount = round2(body.count * buy_price)
    sell_amount = round2(body.count * body.sell_price)

    selled_doc = {
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
def delete_allocation(allocation_id: str):
    db = get_db()
    _id = oid(allocation_id)
    alloc = db.ing_allocations.find_one({"_id": _id})
    if not alloc:
        raise HTTPException(status_code=404, detail="分配记录不存在")

    if alloc["target_type"] == "SELLED":
        db.selled_records.delete_one({"_id": alloc["target_id"]})

    db.ing_allocations.delete_one({"_id": _id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))
