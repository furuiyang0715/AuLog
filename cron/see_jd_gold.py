#!/usr/bin/env python3
"""京东黄金价格定时监控：API 采集 → MongoDB 采样 → PushPlus 预警/推送。"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from app.db import get_db
from app.gold_price import fetch_stats_gold_prices
from cron.gold_history import ensure_indexes, get_today_stats, save_price_record

# ==================== PushPlus 推送配置 ====================
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
PUSHPLUS_TOPIC = os.environ.get("PUSHPLUS_TOPIC", "")

# 只监控以下品种（留空则监控 API 返回的全部）
MONITOR_LABELS = ["伦敦金", "浙商黄金"]

PUSH_TITLE_LABEL_ABBR: dict[str, str] = {
    "伦敦金": "伦",
    "浙商黄金": "浙",
    "民生黄金": "民",
    "黄金TD": "T",
    "汇率": "汇",
    "伦敦金换算价格（￥）": "换",
    "溢价": "溢",
}

TITLE_DISPLAY_ORDER = ["浙商黄金", "伦敦金"]

ALERT_CONFIG = {
    "price_change_percent": 10.0,
    "water_level_high": 99.9999,
    "water_level_low": 0.001,
    "min_records": 3,
    "alert_labels": [],
}


def fetch_monitored_prices() -> dict[str, dict[str, Any]]:
    """通过 AuLog 现有 API 获取监控品种当前价。"""
    bundle = fetch_stats_gold_prices(force=True)
    items: dict[str, dict[str, Any]] = {
        bundle["label"]: {
            "price": float(bundle["price"]),
            "unit": bundle.get("unit") or "元/克",
        }
    }
    london = bundle.get("london")
    if london and london.get("price") is not None:
        items[london["label"]] = {
            "price": float(london["price"]),
            "unit": london.get("unit") or "美元/盎司",
        }
    return items


def calculate_water_level(current_price: float, high: float, low: float) -> float:
    if high == low:
        return 50.0
    level = (current_price - low) / (high - low) * 100
    return max(0, min(100, level))


def format_recent_prices(records: list[dict[str, Any]], count: int = 5) -> str | None:
    if not records:
        return None
    recent = records[-count:]
    return " → ".join(f"{r['price']:.2f}" for r in recent)


def get_water_level_bar(level: float, width: int = 20) -> str:
    filled = int(level / 100 * width)
    empty = width - filled
    if level >= 80:
        indicator = "🔴"
    elif level >= 60:
        indicator = "🟠"
    elif level >= 40:
        indicator = "🟡"
    elif level >= 20:
        indicator = "🟢"
    else:
        indicator = "🔵"
    bar = "█" * filled + "░" * empty
    return f"{indicator} [{bar}] {level:.1f}%"


def build_push_html(all_data: list[dict[str, Any]]) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 10px;">
        <div style="background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); color: white; padding: 15px 20px; border-radius: 10px 10px 0 0;">
            <h2 style="margin: 0; font-size: 18px;">🥇 京东黄金价格监控</h2>
            <p style="margin: 5px 0 0 0; font-size: 12px; opacity: 0.9;">{now}</p>
        </div>
        <div style="background: #f8f9fa; border-radius: 0 0 10px 10px; padding: 5px;">
    """

    for item in all_data:
        change_val = item.get("price_change_val", 0.0)
        if change_val > 0:
            change_color = "#e74c3c"
            arrow = "▲"
        elif change_val < 0:
            change_color = "#27ae60"
            arrow = "▼"
        else:
            change_color = "#7f8c8d"
            arrow = "→"

        level = item.get("water_level", 50.0)
        if level >= 80:
            level_color = "#e74c3c"
        elif level >= 60:
            level_color = "#e67e22"
        elif level >= 40:
            level_color = "#f39c12"
        elif level >= 20:
            level_color = "#27ae60"
        else:
            level_color = "#3498db"

        level_width = int(level)
        unit = item.get("unit") or "元/克"

        html += f"""
        <div style="background: white; margin: 8px; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 600; font-size: 15px; color: #2c3e50;">{item['label']}</span>
                <span style="color: {change_color}; font-size: 12px;">{arrow} {item['price_change']} ({item['price_change_percent']})</span>
            </div>
            <div style="font-size: 24px; font-weight: 700; color: #2c3e50; margin-bottom: 4px;">
                {item['price']:.2f} <span style="font-size: 12px; color: #95a5a6;">{unit}</span>
            </div>
            <div style="font-size: 12px; color: #95a5a6; margin-bottom: 8px;">
                当日记录高 {item['stat_high']:.2f} / 低 {item['stat_low']:.2f}
            </div>
        """

        if item.get("has_stats"):
            html += f"""
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #ecf0f1;">
                <div style="font-size: 12px; color: #7f8c8d; margin-bottom: 4px;">今日水位 (记录 {item['record_count']} 次)</div>
                <div style="background: #ecf0f1; border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: {level_color}; height: 100%; width: {level_width}%; border-radius: 10px;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: #95a5a6; margin-top: 2px;">
                    <span>低 {item['stat_low']:.2f}</span>
                    <span style="color: {level_color}; font-weight: 600;">{level:.1f}%</span>
                    <span>高 {item['stat_high']:.2f}</span>
                </div>
            </div>
            """

        html += "</div>"

    html += """
        </div>
    </div>
    """
    return html


def _ordered_for_title(all_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not TITLE_DISPLAY_ORDER:
        return list(all_data)
    rank = {name: i for i, name in enumerate(TITLE_DISPLAY_ORDER)}
    return sorted(
        all_data,
        key=lambda it: (rank.get(it.get("label") or "", 10_000), it.get("label") or ""),
    )


def _water_level_title_segments(all_data: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in _ordered_for_title(all_data):
        label = item.get("label") or ""
        abbr = PUSH_TITLE_LABEL_ABBR.get(label, label[:1] or "?")
        level = float(item.get("water_level", 50.0))
        has_stats = bool(item.get("has_stats"))
        if has_stats and level < 50.0:
            sign = "-"
            color = "#27ae60"
        else:
            sign = "+"
            color = "#e74c3c"
        price_str = f"{float(item.get('price', 0.0)):.2f}"
        out.append({"abbr": abbr, "sign": sign, "price_str": price_str, "color": color})
    return out


def format_water_level_pushplus_title(all_data: list[dict[str, Any]]) -> str:
    if not all_data:
        return "金价"
    segs = _water_level_title_segments(all_data)
    return "/".join(f"{s['abbr']}{s['sign']}({s['price_str']})" for s in segs)


def build_pushplus_title_color_banner_html(all_data: list[dict[str, Any]]) -> str:
    if not all_data:
        return ""
    segs = _water_level_title_segments(all_data)
    parts = [
        f"<span style=\"color:{s['color']};font-weight:700;\">"
        f"{s['abbr']}{s['sign']}({s['price_str']})</span>"
        for s in segs
    ]
    inner = '<span style="color:#bdc3c7;"> / </span>'.join(parts)
    return (
        '<div style="padding:14px 12px;margin:0 8px 12px 8px;background:#f8f9fa;'
        'border-radius:8px;text-align:center;border:1px solid #ecf0f1;font-size:15px;">'
        f"{inner}</div>"
    )


def send_pushplus(title: str, content: str, template: str = "html") -> bool:
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未配置 PUSHPLUS_TOKEN，跳过 PushPlus 推送")
        return False

    url = "http://www.pushplus.plus/send"
    data: dict[str, Any] = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": template,
    }
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC

    try:
        resp = requests.post(url, json=data, timeout=10)
        result = resp.json()
        if result.get("code") == 200:
            print(f"✅ PushPlus 推送成功: {title}")
            return True
        print(f"❌ PushPlus 推送失败: {result.get('msg', '未知错误')}")
        return False
    except Exception as exc:
        print(f"❌ PushPlus 推送异常: {exc}")
        return False


def check_and_alert(all_data: list[dict[str, Any]]) -> bool:
    alerts: list[str] = []
    alert_labels = ALERT_CONFIG.get("alert_labels") or []

    for item in all_data:
        label = item["label"]
        if alert_labels and label not in alert_labels:
            continue

        try:
            pct_val = float(
                str(item.get("price_change_percent", "0")).replace("%", "").replace("+", "")
            )
            if abs(pct_val) >= ALERT_CONFIG["price_change_percent"]:
                direction = "暴涨" if pct_val > 0 else "暴跌"
                alerts.append(f"📢 {label} {direction} {pct_val:+.2f}%")
        except (ValueError, TypeError):
            pass

        if item.get("has_stats") and item.get("record_count", 0) >= ALERT_CONFIG["min_records"]:
            level = item.get("water_level", 50.0)
            if level >= ALERT_CONFIG["water_level_high"]:
                alerts.append(f"🔴 {label} 水位 {level:.1f}%，接近当日最高")
            elif level <= ALERT_CONFIG["water_level_low"]:
                alerts.append(f"🔵 {label} 水位 {level:.1f}%，接近当日最低")

    if not alerts:
        return False

    title = format_water_level_pushplus_title(all_data)
    html_content = build_pushplus_title_color_banner_html(all_data) + build_push_html(all_data)
    alert_summary = "<br>".join(alerts)
    alert_html = f"""
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 15px; margin: 10px; border-radius: 4px; font-size: 13px;">
            <strong>⚠️ 预警触发:</strong><br>{alert_summary}
        </div>
    """
    send_pushplus(title, alert_html + html_content)
    return True


def collect_gold_prices(db) -> list[dict[str, Any]]:
    """采集当前价、写入 MongoDB，并返回用于推送的结构化数据。"""
    try:
        price_map = fetch_monitored_prices()
    except Exception as exc:
        print(f"❌ 获取金价失败: {exc}")
        return []

    if not price_map:
        print("❌ 未获取到京东黄金价格数据")
        return []

    monitor_labels = MONITOR_LABELS or list(price_map.keys())
    all_data: list[dict[str, Any]] = []

    print("=" * 60)
    print(f"  🥇 京东黄金价格 | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for label, meta in price_map.items():
        if label not in monitor_labels:
            continue

        price = float(meta["price"])
        unit = meta.get("unit") or "元/克"
        stats = get_today_stats(db, label)
        save_price_record(db, label, price)

        has_stats = bool(stats and stats["count"] > 0)
        level = 50.0
        stat_high = price
        stat_low = price
        price_change = "0.00"
        price_change_percent = "0.00%"
        price_change_val = 0.0

        if has_stats:
            stat_high = max(float(stats["high"]), price)
            stat_low = min(float(stats["low"]), price)
            level = calculate_water_level(price, stat_high, stat_low)
            first_price = float(stats["first"])
            if first_price:
                diff = price - first_price
                price_change_val = diff
                price_change = f"{diff:+.2f}"
                price_change_percent = f"{diff / first_price * 100:+.2f}%"

        recent = format_recent_prices(stats["records"]) if stats else None

        print(f"\n名称: {label}")
        print(f"当前价: {price:.2f} {unit}")
        if recent:
            print(f"最近5次: {recent}")
        if has_stats:
            print(f"当日最高: {stat_high:.2f}")
            print(f"当日最低: {stat_low:.2f}")
            print(f"相对首次: {price_change} ({price_change_percent})")
            print(f"今日水位: {get_water_level_bar(level)}")
        else:
            print("暂无历史记录，等待更多数据累积...")

        all_data.append(
            {
                "label": label,
                "price": price,
                "unit": unit,
                "price_change": price_change,
                "price_change_percent": price_change_percent,
                "price_change_val": price_change_val,
                "has_stats": has_stats,
                "water_level": level,
                "record_count": stats["count"] if has_stats else 1,
                "stat_high": stat_high,
                "stat_low": stat_low,
            }
        )

    print()
    print("=" * 60)
    return all_data


def main(push_report: bool = False) -> None:
    db = get_db()
    ensure_indexes(db)

    all_data = collect_gold_prices(db)
    if not all_data or not PUSHPLUS_TOKEN:
        return

    alerted = check_and_alert(all_data)

    if push_report and not alerted:
        title = format_water_level_pushplus_title(all_data)
        html = build_pushplus_title_color_banner_html(all_data) + build_push_html(all_data)
        send_pushplus(title, html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="京东黄金价格监控（AuLog cron）")
    parser.add_argument(
        "--push",
        action="store_true",
        help="强制推送报告（未触发预警时也推送）",
    )
    parser.add_argument("--token", type=str, default=None, help="PushPlus Token")
    parser.add_argument(
        "--pushplus-topic",
        type=str,
        default=None,
        help="PushPlus 群组编码 topicCode",
    )
    args = parser.parse_args()

    if args.token:
        globals()["PUSHPLUS_TOKEN"] = args.token
    if args.pushplus_topic is not None:
        globals()["PUSHPLUS_TOPIC"] = args.pushplus_topic

    main(push_report=args.push)
