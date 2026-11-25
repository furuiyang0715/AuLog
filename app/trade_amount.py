from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

_FOURPLACES = Decimal("0.0001")
_TWOPLACES = Decimal("0.01")

COUNT_EPS = 1e-6
MONEY_EPS = 0.009


def round4(value: float) -> float:
    return float(Decimal(str(value)).quantize(_FOURPLACES, rounding=ROUND_HALF_UP))


def round_money(value: float) -> float:
    """金额（元）保留两位小数。"""
    return float(Decimal(str(value)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP))


def amount_from_price_count(price: float, count: float) -> float:
    """总价 = round(单价×克数, 2)；单价、克数各保留四位。"""
    p = Decimal(str(round4(price)))
    c = Decimal(str(round4(count)))
    return float((p * c).quantize(_TWOPLACES, rounding=ROUND_HALF_UP))


def unit_price_from_amount_count(amount: float, count: float) -> float:
    count_r = round4(count)
    amount_r = round_money(amount)
    if count_r <= 0 or amount_r <= 0:
        raise ValueError("invalid amount/count")
    return round4(float(Decimal(str(amount_r)) / Decimal(str(count_r))))


def resolve_ing_amount(price: float, count: float, amount: float | None) -> float:
    price_r = round4(price)
    count_r = round4(count)
    if price_r <= 0 or count_r <= 0:
        raise HTTPException(status_code=400, detail="单价与克数须大于 0")
    expected = amount_from_price_count(price_r, count_r)
    if amount is None:
        return expected
    amount_r = round_money(amount)
    if amount_r <= 0:
        raise HTTPException(status_code=400, detail="总价须大于 0")
    if abs(amount_r - expected) > MONEY_EPS:
        raise HTTPException(
            status_code=400,
            detail=f"总价须等于单价×克数（应为 {expected}）",
        )
    return amount_r


def validate_t_pop_amount(count: float, pop_amount: float) -> None:
    count_r = round4(count)
    pop_r = round_money(pop_amount)
    if count_r <= 0 or pop_r <= 0:
        raise HTTPException(status_code=400, detail="克数与回笼金额须大于 0")
    unit = unit_price_from_amount_count(pop_r, count_r)
    expected_pop = amount_from_price_count(unit, count_r)
    if abs(expected_pop - pop_r) > MONEY_EPS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"回笼金额须与克数×单价一致（单价 {unit} 元/克，"
                f"总价应为 {expected_pop}）"
            ),
        )