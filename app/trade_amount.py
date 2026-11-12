from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

_TWOPLACES = Decimal("0.01")


def round2(value: float) -> float:
    return float(Decimal(str(value)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP))


def amount_from_price_count(price: float, count: float) -> float:
    """总价 = round(单价×克数, 2)，四舍五入，避免 float 与银行家舍入差异。"""
    p = Decimal(str(round2(price)))
    c = Decimal(str(round2(count)))
    return float((p * c).quantize(_TWOPLACES, rounding=ROUND_HALF_UP))


def resolve_ing_amount(price: float, count: float, amount: float | None) -> float:
    price_r = round2(price)
    count_r = round2(count)
    if price_r <= 0 or count_r <= 0:
        raise HTTPException(status_code=400, detail="单价与克数须大于 0")
    expected = amount_from_price_count(price_r, count_r)
    if amount is None:
        return expected
    amount_r = round2(amount)
    if amount_r <= 0:
        raise HTTPException(status_code=400, detail="总价须大于 0")
    if abs(amount_r - expected) > 0.009:
        raise HTTPException(
            status_code=400,
            detail=f"总价须等于单价×克数（应为 {expected}）",
        )
    return amount_r


def validate_t_pop_amount(count: float, pop_amount: float) -> None:
    count_r = round2(count)
    pop_r = round2(pop_amount)
    if count_r <= 0 or pop_r <= 0:
        raise HTTPException(status_code=400, detail="克数与回笼金额须大于 0")
    unit = round2(float(Decimal(str(pop_r)) / Decimal(str(count_r))))
    expected_pop = amount_from_price_count(unit, count_r)
    if abs(expected_pop - pop_r) > 0.009:
        raise HTTPException(
            status_code=400,
            detail=(
                f"回笼金额须与克数×单价一致（单价 {unit} 元/克，"
                f"总价应为 {expected_pop}）"
            ),
        )
