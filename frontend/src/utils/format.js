export function fmt(n) {
  if (n === null || n === undefined || n === "") return "—";
  return Number(n).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatDateDisplay(value) {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-");
    return `${y}/${m}/${d}`;
  }
  return String(value);
}

export function parseLegacyDate(value) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T00:00:00`).getTime();
  }
  if (/^\d{4}$/.test(value)) {
    const year = new Date().getFullYear();
    return new Date(`${year}-${value.slice(0, 2)}-${value.slice(2, 4)}T00:00:00`).getTime();
  }
  return null;
}

export function compareLegacyDate(a, b) {
  const ta = parseLegacyDate(a) ?? Number.MAX_SAFE_INTEGER;
  const tb = parseLegacyDate(b) ?? Number.MAX_SAFE_INTEGER;
  return ta - tb;
}

export function toDateString(timestamp) {
  if (!timestamp) return null;
  const d = new Date(timestamp);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export const statusMap = {
  OPEN: { label: "待买回", type: "warning" },
  PARTIAL: { label: "部分配对", type: "info" },
  CLOSED: { label: "已闭环", type: "success" },
  UNALLOCATED: { label: "未分配", type: "default" },
  FULLY_ALLOCATED: { label: "已分完", type: "success" },
};

export function gainType(value) {
  if (value === null || value === undefined || value === "") return "default";
  return Number(value) >= 0 ? "success" : "error";
}
