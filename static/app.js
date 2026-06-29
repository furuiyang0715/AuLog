const API = "/api";
const TOKEN_KEY = "aulog_token";

let authToken = localStorage.getItem(TOKEN_KEY) || "";
let currentUser = null;
let tRecords = [];
let ingRecords = [];
let selledRecords = [];
let allocations = [];
let selectedIngId = null;
let authMode = "login";

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------

function fmt(n) {
  if (n === null || n === undefined || n === "") return "—";
  return Number(n).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDateDisplay(value) {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-");
    return `${y}/${m}/${d}`;
  }
  return String(value);
}

function resetFormWithDates(form) {
  form.reset();
  if (window.DatePicker) DatePicker.resetForm(form);
}

function validateDatePickers(form) {
  for (const picker of form.querySelectorAll(".date-picker[data-required]")) {
    const hidden = picker.querySelector('input[type="hidden"]');
    if (!hidden.value) {
      showToast("请选择日期", true);
      return false;
    }
  }
  return true;
}

function showToast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => el.classList.add("hidden"), 3000);
}

function parseErrorDetail(data) {
  if (!data || !data.detail) return "请求失败";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || String(d)).join("；");
  }
  return String(data.detail);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  const res = await fetch(`${API}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/auth/login" && path !== "/auth/register") {
    logout(false);
    throw new Error(parseErrorDetail(data) || "请重新登录");
  }
  if (!res.ok) {
    throw new Error(parseErrorDetail(data) || res.statusText || "请求失败");
  }
  return data;
}

function setAuthUI(loggedIn) {
  document.getElementById("auth-screen").classList.toggle("hidden", loggedIn);
  document.getElementById("app-shell").classList.toggle("hidden", !loggedIn);
  document.getElementById("user-bar").classList.toggle("hidden", !loggedIn);
  if (loggedIn && currentUser) {
    document.getElementById("current-username").textContent = currentUser.username;
  }
}

function saveAuth(token, username) {
  authToken = token;
  currentUser = { username };
  localStorage.setItem(TOKEN_KEY, token);
  setAuthUI(true);
}

function logout(showMsg = true) {
  authToken = "";
  currentUser = null;
  localStorage.removeItem(TOKEN_KEY);
  setAuthUI(false);
  tRecords = [];
  ingRecords = [];
  selledRecords = [];
  allocations = [];
  if (showMsg) {
    showToast("已退出登录");
  }
}

function setAuthMode(mode) {
  authMode = mode;
  document.querySelectorAll(".auth-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
  document.getElementById("auth-title").textContent = mode === "login" ? "登录" : "注册";
  document.getElementById("auth-submit").textContent = mode === "login" ? "登录" : "注册";
  document.querySelector("#form-auth input[name=password]").autocomplete =
    mode === "login" ? "current-password" : "new-password";
}

function statusBadge(status) {
  const map = {
    OPEN: ["待买回", "status-open"],
    PARTIAL: ["部分配对", "status-partial"],
    CLOSED: ["已闭环", "status-closed"],
    UNALLOCATED: ["未分配", "status-unallocated"],
    PARTIAL_ING: ["部分分配", "status-partial"],
    FULLY_ALLOCATED: ["已分完", "status-fully"],
  };
  const [label, cls] = map[status] || [status, "status-open"];
  return `<span class="status ${cls}">${label}</span>`;
}

function gainClass(v) {
  if (v === null || v === undefined) return "";
  return Number(v) >= 0 ? "gain-pos" : "gain-neg";
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

document.querySelectorAll(".auth-tab").forEach((btn) => {
  btn.addEventListener("click", () => setAuthMode(btn.dataset.mode));
});

document.getElementById("form-auth").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const path = authMode === "login" ? "/auth/login" : "/auth/register";
  try {
    const data = await api(path, {
      method: "POST",
      body: JSON.stringify({
        username: String(fd.get("username")).trim(),
        password: String(fd.get("password")),
      }),
    });
    saveAuth(data.token, data.username);
    showToast(authMode === "login" ? "登录成功" : "注册成功");
    e.target.reset();
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("btn-logout").addEventListener("click", () => logout());

async function bootstrap() {
  DatePicker.init();
  setAuthMode("login");
  if (!authToken) {
    setAuthUI(false);
    return;
  }
  try {
    const me = await api("/auth/me");
    currentUser = { username: me.username, id: me.id };
    setAuthUI(true);
    await refreshAll();
  } catch {
    logout(false);
  }
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------------------------------------------------------------------------
// Load & render
// ---------------------------------------------------------------------------

async function refreshAll() {
  [tRecords, ingRecords, selledRecords, allocations] = await Promise.all([
    api("/t-records"),
    api("/ing-records"),
    api("/selled-records"),
    api("/allocations"),
  ]);
  renderT();
  renderIng();
  renderSelled();
  renderAlloc();
}

function renderT() {
  const el = document.getElementById("list-t");
  if (!tRecords.length) {
    el.innerHTML = '<p class="empty">暂无记录，请先添加卖出记录</p>';
    return;
  }
  el.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>备注</th><th>克数</th><th>回笼</th><th>卖价</th>
          <th>买回成本</th><th>套利 gain <span class="hint-inline">部分配对=已配部分</span></th><th>已配/剩余</th><th>状态</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${tRecords
          .map(
            (r) => `
          <tr>
            <td>${esc(r.mark) || "—"}</td>
            <td>${fmt(r.count)}</td>
            <td>${fmt(r.pop_amount)}</td>
            <td>${fmt(r.price)}</td>
            <td>${fmt(r.push_amount)}</td>
            <td class="${gainClass(r.gain)}">${fmt(r.gain)}</td>
            <td>${fmt(r.allocated_count)} / ${fmt(r.remaining_count)}</td>
            <td>${statusBadge(r.status)}</td>
            <td>
              <button class="btn-sm danger" onclick="deleteT('${r.id}')">删除</button>
            </td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderIng() {
  const el = document.getElementById("list-ing");
  if (!ingRecords.length) {
    el.innerHTML = '<p class="empty">暂无进货记录</p>';
    return;
  }
  el.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>日期</th><th>备注</th><th>单价</th><th>克数</th><th>总价</th>
          <th>已配/剩余</th><th>配倒T</th><th>已消利</th><th>状态</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        ${ingRecords
          .map((r) => {
            const canAct = r.remaining_count > 0;
            return `
          <tr>
            <td>${esc(formatDateDisplay(r.date))}</td>
            <td>${esc(r.mark) || "—"}</td>
            <td>${fmt(r.price)}</td>
            <td>${fmt(r.count)}</td>
            <td>${fmt(r.amount)}</td>
            <td>${fmt(r.allocated_count)} / ${fmt(r.remaining_count)}</td>
            <td>${fmt(r.allocated_to_t)}</td>
            <td>${r.is_change ? "✓" : "—"}</td>
            <td>${statusBadge(r.allocation_status)}</td>
            <td class="actions">
              ${
                canAct
                  ? `<button class="btn-sm primary" onclick="openTMatch('${r.id}')">配对倒T</button>
                     <button class="btn-sm" onclick="openSelled('${r.id}')">反弹卖出</button>`
                  : ""
              }
              <button class="btn-sm danger" onclick="deleteIng('${r.id}')">删除</button>
            </td>
          </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;
}

function renderSelled() {
  const el = document.getElementById("list-selled");
  if (!selledRecords.length) {
    el.innerHTML = '<p class="empty">暂无反弹卖出记录</p>';
    return;
  }
  el.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>日期</th><th>备注</th><th>买入价</th><th>克数</th><th>买入额</th>
          <th>卖出价</th><th>卖出额</th><th>获利</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${selledRecords
          .map(
            (r) => `
          <tr>
            <td>${esc(formatDateDisplay(r.date))}</td>
            <td>${esc(r.mark) || "—"}</td>
            <td>${fmt(r.buy_price)}</td>
            <td>${fmt(r.count)}</td>
            <td>${fmt(r.buy_amount)}</td>
            <td>${fmt(r.sell_price)}</td>
            <td>${fmt(r.sell_amount)}</td>
            <td class="${gainClass(r.gain)}">${fmt(r.gain)}</td>
            <td><button class="btn-sm danger" onclick="deleteSelled('${r.id}')">删除</button></td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function targetMark(a) {
  if (a.target_type === "T_MATCH") {
    const t = tRecords.find((r) => r.id === a.target_id);
    return t?.mark || "—";
  }
  const s = selledRecords.find((r) => r.id === a.target_id);
  return s?.mark || "—";
}

function renderAlloc() {
  const el = document.getElementById("list-alloc");
  if (!allocations.length) {
    el.innerHTML = '<p class="empty">暂无分配记录</p>';
    return;
  }
  el.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>类型</th><th>ing</th><th>目标</th><th>克数</th><th>成本</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${allocations
          .map((a) => {
            const ing = ingRecords.find((i) => i.id === a.ing_id);
            const typeLabel = a.target_type === "T_MATCH" ? "配对倒T" : "反弹卖出";
            return `
          <tr>
            <td>${typeLabel}</td>
            <td>${esc(ing?.mark || "—")}</td>
            <td>${esc(targetMark(a))}</td>
            <td>${fmt(a.count)}</td>
            <td>${fmt(a.amount)}</td>
            <td><button class="btn-sm danger" onclick="deleteAlloc('${a.id}')">撤销</button></td>
          </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;
}

function esc(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Forms
// ---------------------------------------------------------------------------

document.getElementById("form-t").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/t-records", {
      method: "POST",
      body: JSON.stringify({
        mark: fd.get("mark"),
        count: Number(fd.get("count")),
        pop_amount: Number(fd.get("pop_amount")),
        sold_at: fd.get("sold_at") || null,
      }),
    });
    resetFormWithDates(e.target);
    showToast("倒 T 记录已添加");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("form-ing").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!validateDatePickers(e.target)) return;
  const fd = new FormData(e.target);
  const amountRaw = fd.get("amount");
  try {
    await api("/ing-records", {
      method: "POST",
      body: JSON.stringify({
        date: fd.get("date"),
        mark: fd.get("mark"),
        price: Number(fd.get("price")),
        count: Number(fd.get("count")),
        amount: amountRaw ? Number(amountRaw) : null,
      }),
    });
    resetFormWithDates(e.target);
    showToast("进货记录已添加");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ---------------------------------------------------------------------------
// Allocation dialogs
// ---------------------------------------------------------------------------

function openTMatch(ingId) {
  selectedIngId = ingId;
  const ing = ingRecords.find((i) => i.id === ingId);
  if (!ing) return;

  document.getElementById("t-match-ing-info").textContent =
    `${ing.mark || "无备注"} · 单价 ${fmt(ing.price)} · 剩余 ${fmt(ing.remaining_count)} 克`;

  const select = document.querySelector("#form-t-match select[name=t_id]");
  const openT = tRecords.filter((t) => t.remaining_count > 0);
  if (!openT.length) {
    showToast("没有可配对的倒 T 记录（需有剩余克数）", true);
    return;
  }
  select.innerHTML = openT
    .map(
      (t) =>
        `<option value="${t.id}">${esc(t.mark) || "无备注"} · 剩余 ${fmt(t.remaining_count)} 克 · 卖价 ${fmt(t.price)}</option>`
    )
    .join("");

  document.querySelector("#form-t-match input[name=count]").value = Math.min(
    ing.remaining_count,
    openT[0].remaining_count
  );

  document.getElementById("dialog-t-match").showModal();
}

function openSelled(ingId) {
  selectedIngId = ingId;
  const ing = ingRecords.find((i) => i.id === ingId);
  if (!ing) return;

  document.getElementById("selled-ing-info").textContent =
    `${ing.mark || "无备注"} · 买入价 ${fmt(ing.price)} · 剩余 ${fmt(ing.remaining_count)} 克`;

  const form = document.getElementById("form-selled-alloc");
  DatePicker.setValue(form.querySelector(".date-picker"), ing.date);
  form.mark.value = ing.mark || "";
  form.count.value = ing.remaining_count;
  form.sell_price.value = "";

  document.getElementById("dialog-selled").showModal();
}

document.getElementById("cancel-t-match").addEventListener("click", () => {
  document.getElementById("dialog-t-match").close();
});

document.getElementById("cancel-selled").addEventListener("click", () => {
  document.getElementById("dialog-selled").close();
});

document.getElementById("form-t-match").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/allocations/t-match", {
      method: "POST",
      body: JSON.stringify({
        ing_id: selectedIngId,
        t_id: fd.get("t_id"),
        count: Number(fd.get("count")),
      }),
    });
    document.getElementById("dialog-t-match").close();
    showToast("配对成功");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("form-selled-alloc").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!validateDatePickers(e.target)) return;
  const fd = new FormData(e.target);
  try {
    await api("/allocations/selled", {
      method: "POST",
      body: JSON.stringify({
        ing_id: selectedIngId,
        date: fd.get("date"),
        mark: fd.get("mark"),
        count: Number(fd.get("count")),
        sell_price: Number(fd.get("sell_price")),
      }),
    });
    document.getElementById("dialog-selled").close();
    showToast("反弹卖出已记录");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
});

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------

async function deleteT(id) {
  if (!confirm("确定删除这条倒 T 记录？")) return;
  try {
    await api(`/t-records/${id}`, { method: "DELETE" });
    showToast("已删除");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteIng(id) {
  if (!confirm("确定删除这条进货记录？")) return;
  try {
    await api(`/ing-records/${id}`, { method: "DELETE" });
    showToast("已删除");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteSelled(id) {
  if (!confirm("确定删除？关联分配也会撤销")) return;
  try {
    await api(`/selled-records/${id}`, { method: "DELETE" });
    showToast("已删除");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function deleteAlloc(id) {
  if (!confirm("确定撤销这条分配？反弹卖出会一并删除")) return;
  try {
    await api(`/allocations/${id}`, { method: "DELETE" });
    showToast("已撤销");
    await refreshAll();
  } catch (err) {
    showToast(err.message, true);
  }
}

window.deleteT = deleteT;
window.deleteIng = deleteIng;
window.deleteSelled = deleteSelled;
window.deleteAlloc = deleteAlloc;
window.openTMatch = openTMatch;
window.openSelled = openSelled;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

bootstrap().catch((err) => showToast(err.message, true));
