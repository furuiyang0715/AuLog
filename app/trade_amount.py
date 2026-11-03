from __future__ import annotations

from fastapi import HTTPException


def round2(value: float) -> float:
    return round(float(value), 2)


def resolve_ing_amount(price: float, count: float, amount: float | None) -> float:
    price_r = round2(price)
    count_r = round2(count)
    if price_r <= 0 or count_r <= 0:
        raise HTTPException(status_code=400, detail="单价与克数须大于 0")
    expected = round2(price_r * count_r)
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
    unit = round2(pop_r / count_r)
    expected_pop = round2(count_r * unit)
    if abs(expected_pop - pop_r) > 0.009:
        raise HTTPException(
            status_code=400,
            detail=(
                f"回笼金额须与克数×单价一致（单价 {unit} 元/克，"
                f"总价应为 {expected_pop}）"
            ),
        )
