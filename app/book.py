from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database

from app.auth import user_id
from app.db import get_db

router = APIRouter(prefix="/api/book", tags=["book"])

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BookProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class BookSnapshotBody(BaseModel):
    amounts: dict[str, Optional[float]] = Field(default_factory=dict)


def round2(value: float) -> float:
    return round(float(value), 2)


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
        elif isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def require_calendar_day(value: str) -> str:
    if not value or not _DAY_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="日期必须是有效的 YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效日期") from exc
    return value


def normalize_project_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    if len(text) > 32:
        raise HTTPException(status_code=400, detail="项目名称不能超过 32 个字")
    return text


def list_projects(db: Database, uid: ObjectId) -> list[dict[str, Any]]:
    return list(db.book_projects.find({"user_id": uid}).sort("name", 1))


def get_project_or_404(db: Database, uid: ObjectId, project_id: str) -> dict[str, Any]:
    doc = db.book_projects.find_one({"_id": oid(project_id), "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="项目不存在")
    return doc


def project_in_use(db: Database, uid: ObjectId, project_id: ObjectId) -> bool:
    return (
        db.book_snapshots.count_documents(
            {"user_id": uid, f"amounts.{str(project_id)}": {"$exists": True}}
        )
        > 0
    )


def name_taken(
    db: Database, uid: ObjectId, name: str, exclude_id: ObjectId | None = None
) -> bool:
    query: dict[str, Any] = {"user_id": uid, "name": name}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    return db.book_projects.find_one(query) is not None


def parse_amount(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return round2(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="金额必须是数字") from exc


def enrich_snapshot(doc: dict[str, Any]) -> dict[str, Any]:
    item = serialize(doc) or {}
    amounts = item.get("amounts") or {}
    normalized: dict[str, float] = {}
    for key, value in amounts.items():
        normalized[str(key)] = parse_amount(value)
    item["amounts"] = normalized
    item["total"] = round2(sum(normalized.values()))
    return item


def build_day_amounts(
    projects: list[dict[str, Any]], raw: dict[str, Optional[float]]
) -> dict[str, float]:
    amounts: dict[str, float] = {}
    for project in projects:
        pid = str(project["_id"])
        amounts[pid] = parse_amount(raw.get(pid))
    return amounts


@router.get("/projects")
def list_book_projects(uid: ObjectId = Depends(user_id)):
    db = get_db()
    return [serialize(doc) for doc in list_projects(db, uid)]


@router.post("/projects", status_code=201)
def create_book_project(body: BookProjectBody, uid: ObjectId = Depends(user_id)):
    db = get_db()
    name = normalize_project_name(body.name)
    if name_taken(db, uid, name):
        raise HTTPException(status_code=400, detail="已有同名项目")
    doc = {
        "user_id": uid,
        "name": name,
        "created_at": datetime.utcnow(),
    }
    result = db.book_projects.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.patch("/projects/{project_id}")
def rename_book_project(
    project_id: str, body: BookProjectBody, uid: ObjectId = Depends(user_id)
):
    db = get_db()
    doc = get_project_or_404(db, uid, project_id)
    name = normalize_project_name(body.name)
    if name_taken(db, uid, name, exclude_id=doc["_id"]):
        raise HTTPException(status_code=400, detail="已有同名项目")
    update = {"name": name, "updated_at": datetime.utcnow()}
    db.book_projects.update_one({"_id": doc["_id"], "user_id": uid}, {"$set": update})
    doc.update(update)
    return serialize(doc)


@router.delete("/projects/{project_id}")
def delete_book_project(project_id: str, uid: ObjectId = Depends(user_id)):
    db = get_db()
    doc = get_project_or_404(db, uid, project_id)
    if project_in_use(db, uid, doc["_id"]):
        raise HTTPException(status_code=400, detail="该项目已有金额记录，无法删除")
    db.book_projects.delete_one({"_id": doc["_id"], "user_id": uid})
    return {"ok": True}


@router.get("/snapshots")
def list_book_snapshots(uid: ObjectId = Depends(user_id)):
    db = get_db()
    rows = [
        enrich_snapshot(doc)
        for doc in db.book_snapshots.find({"user_id": uid}).sort("date", -1)
    ]
    return rows


@router.put("/snapshots/{day}")
def upsert_book_snapshot(
    day: str, body: BookSnapshotBody, uid: ObjectId = Depends(user_id)
):
    day = require_calendar_day(day)
    db = get_db()
    projects = list_projects(db, uid)
    if not projects:
        raise HTTPException(status_code=400, detail="请先新增项目")

    amounts = build_day_amounts(projects, body.amounts or {})
    now = datetime.utcnow()
    existing = db.book_snapshots.find_one({"user_id": uid, "date": day})
    if existing:
        update = {"amounts": amounts, "updated_at": now}
        db.book_snapshots.update_one(
            {"_id": existing["_id"], "user_id": uid}, {"$set": update}
        )
        existing.update(update)
        return enrich_snapshot(existing)

    doc = {
        "user_id": uid,
        "date": day,
        "amounts": amounts,
        "created_at": now,
    }
    result = db.book_snapshots.insert_one(doc)
    doc["_id"] = result.inserted_id
    return enrich_snapshot(doc)
