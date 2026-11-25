export function round4(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return NaN;
  return Math.round(n * 10000) / 10000;
}

export function roundMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return NaN;
  return Math.round(n * 100) / 100;
}

/** 总价 = round(单价×克数, 2)；单价、克数各四位 */
export function amountFromPriceCount(price, count) {
  const p = round4(price);
  const c = round4(count);
  if (c <= 0) return null;
  return roundMoney(p * c);
}

export function priceFromAmountCount(amount, count) {
  const c = round4(count);
  const a = roundMoney(amount);
  if (c <= 0 || a <= 0) return null;
  return round4(a / c);
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
  if (Math.abs(roundMoney(a) - expected) > 0.009) {
    errors.push(`总价须等于单价×克数（应为 ${expected.toFixed(2)}）`);
  }
  return { ok: errors.length === 0, errors, expectedAmount: expected };
}

export function firstValidationError(result) {
  return result.errors[0] || "数据校验未通过";
}