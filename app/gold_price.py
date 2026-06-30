from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import requests

ZS_GOLD_URL = (
    "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
)
ZS_PRODUCT_SKU = "1961543816"
ZS_LABEL = "浙商黄金"
CACHE_TTL_SECONDS = 60

_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def fetch_zheshang_gold_price(*, force: bool = False) -> dict[str, Any]:
    """获取京东金融浙商积存金当前价（与 see_jd_gold 监控品种一致）。"""
    now = time.time()
    if (
        not force
        and _cache["data"] is not None
        and now - float(_cache["fetched_at"]) < CACHE_TTL_SECONDS
    ):
        return dict(_cache["data"])

    response = requests.post(
        ZS_GOLD_URL,
        json={"reqData": {"productSku": ZS_PRODUCT_SKU}},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    datas = payload.get("resultData", {}).get("datas") or {}
    price_raw = datas.get("price")
    if price_raw is None:
        raise ValueError("金价接口未返回 price 字段")

    price = round(float(price_raw), 2)
    result = {
        "label": ZS_LABEL,
        "price": price,
        "change_amount": _optional_float(datas.get("upAndDownAmt")),
        "change_rate": datas.get("upAndDownRate"),
        "yesterday_price": _optional_float(datas.get("yesterdayPrice")),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    _cache["data"] = result
    _cache["fetched_at"] = now
    return result


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None
