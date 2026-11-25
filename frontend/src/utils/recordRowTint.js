const COUNT_EPS = 1e-6;

/** @typedef {'closed' | 'profit' | 'loss' | 'neutral'} RowTint */

/**
 * 倒 T：已闭环 → closed；否则按剩余克数 (卖价−现价)×R，≥0 为盈利（含持平）
 * @returns {RowTint}
 */
export function tRecordRowTint(record, currentGold) {
  if (record?.status === "CLOSED") return "closed";

  const remaining = Number(record?.remaining_count) || 0;
  if (remaining <= COUNT_EPS) return "closed";

  const gold = currentGold;
  if (gold == null || !Number.isFinite(gold)) return "neutral";

  const sellPrice = Number(record?.price) || 0;
  const floatPnl = (sellPrice - gold) * remaining;
  if (floatPnl >= -1e-6) return "profit";
  return "loss";
}

/**
 * 进货：已分完 → closed；否则 (现价−买入价)×R
 * @returns {RowTint}
 */
export function ingRecordRowTint(record, currentGold) {
  if (record?.allocation_status === "FULLY_ALLOCATED") return "closed";

  const remaining = Number(record?.remaining_count) || 0;
  if (remaining <= COUNT_EPS) return "closed";

  const gold = currentGold;
  if (gold == null || !Number.isFinite(gold)) return "neutral";

  const buyPrice = Number(record?.price) || 0;
  const floatPnl = (gold - buyPrice) * remaining;
  if (floatPnl >= -1e-6) return "profit";
  return "loss";
}

/** @param {RowTint} tint */
export function rowTintClassName(tint) {
  if (tint === "closed") return "row-tint-closed";
  if (tint === "profit") return "row-tint-profit";
  if (tint === "loss") return "row-tint-loss";
  return "";
}