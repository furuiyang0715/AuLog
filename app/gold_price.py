from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime
from typing import Any

import requests

ZS_GOLD_URL = (
    "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816"
)
ZS_PRODUCT_SKU = "1961543816"
ZS_LABEL = "浙商黄金"

LONDON_QUOTE_URL = (
    "https://api.jdjygold.com/gw2/generic/jdtwt/h5/m/getSimpleQuoteUseUniqueCodes"
)
LONDON_UNIQUE_CODE = "WG-XAUUSD"
LONDON_LABEL = "伦敦金"

CACHE_TTL_SECONDS = 60

_cache: dict[str, Any] = {"bundle": None, "fetched_at": 0.0}


def fetch_zheshang_gold_price(*, force: bool = False) -> dict[str, Any]:
    """获取京东金融浙商积存金当前价（与 see_jd_gold 监控品种一致）。"""
    return fetch_stats_gold_prices(force=force)


def fetch_stats_gold_prices(*, force: bool = False) -> dict[str, Any]:
    """浙商积存金（用于计算）+ 伦敦金（仅展示）。"""
    now = time.time()
    if (
        not force
        and _cache["bundle"] is not None
        and now - float(_cache["fetched_at"]) < CACHE_TTL_SECONDS
    ):
        return dict(_cache["bundle"])

    zheshang = _fetch_zheshang()
    london = _fetch_london()
    bundle = {**zheshang, "london": london}
    _cache["bundle"] = bundle
    _cache["fetched_at"] = now
    return bundle


def _fetch_zheshang() -> dict[str, Any]:
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
        raise ValueError("浙商金价接口未返回 price 字段")

    price = round(float(price_raw), 2)
    return {
        "label": ZS_LABEL,
        "price": price,
        "unit": "元/克",
        "change_amount": _optional_float(datas.get("upAndDownAmt")),
        "change_rate": datas.get("upAndDownRate"),
        "yesterday_price": _optional_float(datas.get("yesterdayPrice")),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def _fetch_london() -> dict[str, Any] | None:
    try:
        req_data = json.dumps(
            {"ticket": "gold-price-h5", "uniqueCodes": [LONDON_UNIQUE_CODE]},
            separators=(",", ":"),
        )
        url = f"{LONDON_QUOTE_URL}?reqData={urllib.parse.quote(req_data)}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("resultData", {}).get("data") or []
        item = next(
            (row for row in rows if row.get("uniqueCode") == LONDON_UNIQUE_CODE),
            rows[0] if rows else None,
        )
        if not item or item.get("lastPrice") is None:
            return None

        raise_percent = item.get("raisePercent")
        change_rate = None
        if raise_percent is not None:
            change_rate = f"{float(raise_percent) * 100:+.2f}%"

        return {
            "label": LONDON_LABEL,
            "price": round(float(item["lastPrice"]), 2),
            "unit": "美元/盎司",
            "change_amount": _optional_float(item.get("raise")),
            "change_rate": change_rate,
        }
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None
