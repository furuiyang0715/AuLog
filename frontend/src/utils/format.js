export function fmt(n) {
  if (n === null || n === undefined || n === "") return "—";
  return Number(n).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;
const DATE_TIME = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/;
const LEGACY_MMDD = /^\d{4}$/;

function pad(n) {
  return String(n).padStart(2, "0");
}

export function formatDateDisplay(value) {
  if (!value) return "—";
  const dt = DATE_TIME.exec(value);
  if (dt) {
    return `${dt[1]}/${dt[2]}/${dt[3]} ${dt[4]}:${dt[5]}:${dt[6]}`;
  }
  const day = DATE_ONLY.exec(value);
  if (day) {
    return `${day[1]}/${day[2]}/${day[3]}`;
  }
  return String(value);
}

export function parseLegacyDate(value) {
  if (!value) return null;
  const dt = DATE_TIME.exec(value);
  if (dt) {
    return new Date(+dt[1], +dt[2] - 1, +dt[3], +dt[4], +dt[5], +dt[6]).getTime();
  }
  const day = DATE_ONLY.exec(value);
  if (day) {
    return new Date(+day[1], +day[2] - 1, +day[3]).getTime();
  }
  if (LEGACY_MMDD.test(value)) {
    const year = new Date().getFullYear();
    return new Date(year, +value.slice(0, 2) - 1, +value.slice(2, 4)).getTime();
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
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function toDateTimeString(timestamp) {
  if (!timestamp) return null;
  const d = new Date(timestamp);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
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
