export function round2(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return NaN;
  return Math.round(n * 100) / 100;
}

/** 与后端 amount_from_price_count 一致：先保留两位单价/克数，再用整数运算求总价 */
export function amountFromPriceCount(price, count) {
  const priceCents = Math.round(round2(price) * 100);
  const countHundredths = Math.round(round2(count) * 100);
  if (countHundredths <= 0) return null;
  const amountCents = Math.round((priceCents * countHundredths) / 100);
  return amountCents / 100;
}

/** 由总价、克数反算单价（保留两位） */
export function priceFromAmountCount(amount, count) {
  const c = round2(count);
  const a = round2(amount);
  if (c <= 0 || a <= 0) return null;
  const countHundredths = Math.round(c * 100);
  const amountCents = Math.round(a * 100);
  if (countHundredths <= 0) return null;
  return Math.round((amountCents / countHundredths) * 100) / 100;
}

/**
 * @param {Record<string, unknown>} state 含 price、count 与 amountKey
 * @param {'price' | 'amount' | 'count'} changed 用户刚改动的字段
 * @param {string} amountKey 总价字段名，默认 amount
 */
export function syncTradeAmounts(state, changed, amountKey = "amount") {
  const count = Number(state.count);
  if (!Number.isFinite(count) || count <= 0) return;

  const price = Number(state.price);
  const total = Number(state[amountKey]);
  const hasPrice = Number.isFinite(price) && price > 0;
  const hasTotal = Number.isFinite(total) && total > 0;

  if (changed === "price" && hasPrice) {
    state[amountKey] = amountFromPriceCount(price, count);
    return;
  }
  if (changed === "amount" && hasTotal) {
    state.price = priceFromAmountCount(total, count);
    return;
  }
  if (changed === "count") {
    if (hasPrice) {
      state[amountKey] = amountFromPriceCount(price, count);
    } else if (hasTotal) {
      state.price = priceFromAmountCount(total, count);
    }
  }
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
