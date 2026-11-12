export function round2(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return NaN;
  return Math.round(n * 100) / 100;
}

/** 与后端 amount_from_price_count 一致：先保留两位单价/克数，再用整数运算求总价 */
export function amountFromPriceCount(price, count) {
  const priceCents = Math.round(round2(price) * 100);
  const countHundredths = Math.round(round2(count) * 100);
  const amountCents = Math.round((priceCents * countHundredths) / 100);
  return amountCents / 100;
}

/**
 * @returns {{ ok: boolean, errors: string[], expectedAmount: number | null }}
 */
export function validatePriceCountAmount({ price, count, amount, requireTotal = true }) {
  const errors = [];
  const c = Number(count);
  const p = Number(price);

  if (!Number.isFinite(c) || c <= 0) errors.push("克数须大于 0");
  if (!Number.isFinite(p) || p <= 0) errors.push("单价须大于 0");
  if (errors.length) return { ok: false, errors, expectedAmount: null };

  const expected = amountFromPriceCount(p, c);
  const amountMissing = amount == null || amount === "";
  if (amountMissing) {
    if (requireTotal) {
      errors.push("请填写总价");
      return { ok: false, errors, expectedAmount: expected };
    }
    return { ok: true, errors: [], expectedAmount: expected };
  }

  const a = Number(amount);
  if (!Number.isFinite(a) || a <= 0) {
    errors.push("总价须大于 0");
    return { ok: false, errors, expectedAmount: expected };
  }
  if (Math.abs(round2(a) - expected) > 0.009) {
    errors.push(`总价须等于单价×克数（应为 ${expected.toFixed(2)}）`);
  }
  return { ok: errors.length === 0, errors, expectedAmount: expected };
}

export function firstValidationError(result) {
  return result.errors[0] || "数据校验未通过";
}
