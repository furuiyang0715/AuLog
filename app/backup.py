from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException
from pymongo.database import Database

BACKUP_VERSION = 1
BACKUP_APP = "AuLog"

COLLECTIONS = (
    "t_records",
    "ing_records",
    "selled_records",
    "ing_allocations",
)

ALLOWED_FIELDS: dict[str, tuple[str, ...]] = {
    "t_records": ("mark", "count", "pop_amount", "sold_at", "created_at", "updated_at"),
    "ing_records": ("date", "mark", "price", "count", "amount", "created_at", "updated_at"),
    "selled_records": (
        "date",
        "mark",
        "buy_price",
        "count",
        "buy_amount",
        "sell_price",
        "sell_amount",
        "created_at",
    ),
    "ing_allocations": (
        "ing_id",
        "target_type",
        "target_id",
        "count",
        "amount",
        "created_at",
    ),
}


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def export_doc(doc: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            out["id"] = str(value)
        elif key == "user_id":
            continue
        else:
            out[key] = _serialize_value(value)
    return out


def export_user_data(db: Database, uid: ObjectId, username: str) -> dict[str, Any]:
    data = {
        name: [export_doc(doc) for doc in db[name].find({"user_id": uid})]
        for name in COLLECTIONS
    }
    return {
        "version": BACKUP_VERSION,
        "app": BACKUP_APP,
        "exported_at": datetime.utcnow().isoformat(),
        "username": username,
        "data": data,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效的日期时间: {value}") from exc
    raise HTTPException(status_code=400, detail=f"无效的日期时间类型: {type(value).__name__}")


def _require_record_id(record: Any, collection: str, index: int) -> str:
    if not isinstance(record, dict):
        raise HTTPException(status_code=400, detail=f"{collection}[{index}] 必须是对象")
    record_id = record.get("id")
    if not record_id or not isinstance(record_id, str) or not ObjectId.is_valid(record_id):
        raise HTTPException(status_code=400, detail=f"{collection}[{index}] 缺少有效 id")
    return record_id


def _build_record(
    record: dict[str, Any],
    collection: str,
    uid: ObjectId,
    id_maps: dict[str, dict[str, ObjectId]],
) -> dict[str, Any]:
    allowed = ALLOWED_FIELDS[collection]
    doc: dict[str, Any] = {"user_id": uid}
    old_id = record["id"]

    for key in allowed:
        if key not in record:
            continue
        value = record[key]
        if key in ("ing_id", "target_id"):
            if not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"{collection} 引用 id 无效")
            ref_collection = "ing_records" if key == "ing_id" else _target_collection(record)
            mapped = id_maps[ref_collection].get(value)
            if mapped is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"{collection} 引用了不存在的 {key}: {value}",
                )
            doc[key] = mapped
        elif key in ("created_at", "updated_at"):
            parsed = _parse_datetime(value)
            if parsed is not None:
                doc[key] = parsed
        elif key == "target_type":
            if value not in ("T_MATCH", "SELLED"):
                raise HTTPException(status_code=400, detail="target_type 必须是 T_MATCH 或 SELLED")
            doc[key] = value
        elif key in ("count", "pop_amount", "price", "amount", "buy_price", "buy_amount", "sell_price", "sell_amount"):
            doc[key] = round(float(value), 2)
        elif key in ("mark", "date", "sold_at"):
            doc[key] = str(value).strip() if value is not None else ""
        else:
            doc[key] = value

    new_id = ObjectId()
    id_maps[collection][old_id] = new_id
    doc["_id"] = new_id
    return doc


def _target_collection(record: dict[str, Any]) -> str:
    target_type = record.get("target_type")
    if target_type == "T_MATCH":
        return "t_records"
    if target_type == "SELLED":
        return "selled_records"
    raise HTTPException(status_code=400, detail="分配记录缺少有效 target_type")


def _validate_backup_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="备份文件必须是 JSON 对象")

    version = payload.get("version")
    if version != BACKUP_VERSION:
        raise HTTPException(status_code=400, detail=f"不支持的备份版本: {version}")

    if payload.get("app") != BACKUP_APP:
        raise HTTPException(status_code=400, detail="不是 AuLog 备份文件")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="备份缺少 data 字段")

    for name in COLLECTIONS:
        rows = data.get(name)
        if rows is None:
            raise HTTPException(status_code=400, detail=f"备份缺少 data.{name}")
        if not isinstance(rows, list):
            raise HTTPException(status_code=400, detail=f"data.{name} 必须是数组")

    return payload


def import_user_data(db: Database, uid: ObjectId, payload: dict[str, Any]) -> dict[str, int]:
    payload = _validate_backup_payload(payload)
    data = payload["data"]

    seen_ids: dict[str, set[str]] = {name: set() for name in COLLECTIONS}
    for collection in COLLECTIONS:
        for index, record in enumerate(data[collection]):
            record_id = _require_record_id(record, collection, index)
            if record_id in seen_ids[collection]:
                raise HTTPException(status_code=400, detail=f"{collection} 存在重复 id: {record_id}")
            seen_ids[collection].add(record_id)

    for index, record in enumerate(data["ing_allocations"]):
        ing_id = record.get("ing_id")
        target_id = record.get("target_id")
        target_type = record.get("target_type")
        if not isinstance(ing_id, str) or ing_id not in seen_ids["ing_records"]:
            raise HTTPException(status_code=400, detail=f"ing_allocations[{index}] ing_id 无效")
        if target_type == "T_MATCH":
            if not isinstance(target_id, str) or target_id not in seen_ids["t_records"]:
                raise HTTPException(status_code=400, detail=f"ing_allocations[{index}] target_id 无效")
        elif target_type == "SELLED":
            if not isinstance(target_id, str) or target_id not in seen_ids["selled_records"]:
                raise HTTPException(status_code=400, detail=f"ing_allocations[{index}] target_id 无效")
        else:
            raise HTTPException(status_code=400, detail=f"ing_allocations[{index}] target_type 无效")

    id_maps: dict[str, dict[str, ObjectId]] = {name: {} for name in COLLECTIONS}

    for name in COLLECTIONS:
        db[name].delete_many({"user_id": uid})

    counts: dict[str, int] = {}
    insert_order = ("t_records", "ing_records", "selled_records", "ing_allocations")
    for collection in insert_order:
        docs = [
            _build_record(record, collection, uid, id_maps)
            for record in data[collection]
        ]
        if docs:
            db[collection].insert_many(docs)
        counts[collection] = len(docs)

    return counts


def parse_backup_json(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="备份文件必须是 UTF-8 编码") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {exc.msg}") from exc

    return payload
