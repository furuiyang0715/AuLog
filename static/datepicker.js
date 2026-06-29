(function () {
  const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

  let popup = null;
  let activeField = null;
  let viewYear = 0;
  let viewMonth = 0;

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function toISO(year, month, day) {
    return `${year}-${pad(month)}-${pad(day)}`;
  }

  function parseToISO(value) {
    if (!value) return "";
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
    if (/^\d{4}$/.test(value)) {
      const year = new Date().getFullYear();
      return `${year}-${value.slice(0, 2)}-${value.slice(2, 4)}`;
    }
    return "";
  }

  function formatDisplay(iso) {
    if (!iso) return "选择日期";
    const [y, m, d] = iso.split("-");
    return `${y}/${m}/${d}`;
  }

  function ensurePopup() {
    if (popup) return popup;
    popup = document.createElement("div");
    popup.id = "date-picker-popup";
    popup.className = "date-picker-popup hidden";
    popup.innerHTML = `
      <div class="date-picker-panel">
        <div class="date-picker-header">
          <button type="button" class="date-picker-nav" data-dir="-1" aria-label="上个月">‹</button>
          <span class="date-picker-title"></span>
          <button type="button" class="date-picker-nav" data-dir="1" aria-label="下个月">›</button>
        </div>
        <div class="date-picker-weekdays"></div>
        <div class="date-picker-days"></div>
        <div class="date-picker-footer">
          <button type="button" class="date-picker-today">今天</button>
          <button type="button" class="date-picker-clear">清空</button>
        </div>
      </div>`;
    document.body.appendChild(popup);

    popup.querySelector(".date-picker-weekdays").innerHTML = WEEKDAYS.map(
      (d) => `<span>${d}</span>`
    ).join("");

    popup.addEventListener("click", (e) => {
      const nav = e.target.closest(".date-picker-nav");
      if (nav) {
        shiftMonth(Number(nav.dataset.dir));
        renderDays();
        return;
      }
      if (e.target.classList.contains("date-picker-day")) {
        selectDate(
          Number(e.target.dataset.year),
          Number(e.target.dataset.month),
          Number(e.target.dataset.day)
        );
        return;
      }
      if (e.target.classList.contains("date-picker-today")) {
        const now = new Date();
        selectDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
        return;
      }
      if (e.target.classList.contains("date-picker-clear")) {
        clearField(activeField);
        closePopup();
      }
    });

    document.addEventListener("click", (e) => {
      if (!popup || popup.classList.contains("hidden")) return;
      if (popup.contains(e.target) || e.target.closest(".date-picker-btn")) return;
      closePopup();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closePopup();
    });

    return popup;
  }

  function shiftMonth(delta) {
    viewMonth += delta;
    if (viewMonth > 12) {
      viewMonth = 1;
      viewYear += 1;
    } else if (viewMonth < 1) {
      viewMonth = 12;
      viewYear -= 1;
    }
  }

  function renderDays() {
    const title = popup.querySelector(".date-picker-title");
    const daysEl = popup.querySelector(".date-picker-days");
    title.textContent = `${viewYear}年 ${viewMonth}月`;

    const hidden = activeField?.querySelector('input[type="hidden"]');
    const selected = hidden?.value || "";
    const today = new Date();
    const todayISO = toISO(today.getFullYear(), today.getMonth() + 1, today.getDate());

    const first = new Date(viewYear, viewMonth - 1, 1);
    const startOffset = first.getDay();
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
    const prevMonthDays = new Date(viewYear, viewMonth - 1, 0).getDate();

    let cells = "";
    for (let i = 0; i < 42; i += 1) {
      let y = viewYear;
      let m = viewMonth;
      let d;
      let muted = false;

      if (i < startOffset) {
        d = prevMonthDays - startOffset + i + 1;
        m = viewMonth === 1 ? 12 : viewMonth - 1;
        y = viewMonth === 1 ? viewYear - 1 : viewYear;
        muted = true;
      } else if (i >= startOffset + daysInMonth) {
        d = i - startOffset - daysInMonth + 1;
        m = viewMonth === 12 ? 1 : viewMonth + 1;
        y = viewMonth === 12 ? viewYear + 1 : viewYear;
        muted = true;
      } else {
        d = i - startOffset + 1;
      }

      const iso = toISO(y, m, d);
      const classes = ["date-picker-day"];
      if (muted) classes.push("is-muted");
      if (iso === selected) classes.push("is-selected");
      if (iso === todayISO) classes.push("is-today");

      cells += `<button type="button" class="${classes.join(" ")}" data-year="${y}" data-month="${m}" data-day="${d}">${d}</button>`;
    }
    daysEl.innerHTML = cells;
  }

  function updateFieldDisplay(field, iso) {
    const hidden = field.querySelector('input[type="hidden"]');
    const text = field.querySelector(".date-picker-text");
    hidden.value = iso || "";
    text.textContent = formatDisplay(iso);
    field.classList.toggle("has-value", Boolean(iso));
  }

  function clearField(field) {
    if (!field) return;
    updateFieldDisplay(field, "");
  }

  function selectDate(year, month, day) {
    if (!activeField) return;
    updateFieldDisplay(activeField, toISO(year, month, day));
    closePopup();
  }

  function openPopup(field, anchor) {
    ensurePopup();
    activeField = field;
    const hidden = field.querySelector('input[type="hidden"]');
    const iso = hidden.value;
    if (iso) {
      const [y, m] = iso.split("-").map(Number);
      viewYear = y;
      viewMonth = m;
    } else {
      const now = new Date();
      viewYear = now.getFullYear();
      viewMonth = now.getMonth() + 1;
    }

    renderDays();

    const rect = anchor.getBoundingClientRect();
    popup.style.top = `${rect.bottom + window.scrollY + 6}px`;
    popup.style.left = `${Math.max(8, rect.left + window.scrollX)}px`;
    popup.classList.remove("hidden");
  }

  function closePopup() {
    if (!popup) return;
    popup.classList.add("hidden");
    activeField = null;
  }

  function init(root = document) {
    ensurePopup();
    root.querySelectorAll(".date-picker").forEach((field) => {
      if (field.dataset.initialized) return;
      field.dataset.initialized = "1";
      const btn = field.querySelector(".date-picker-btn");
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openPopup(field, btn);
      });
    });
  }

  function findField(target) {
    if (!target) return null;
    if (target.classList?.contains("date-picker")) return target;
    return target.querySelector?.(".date-picker") || target.closest?.(".date-picker");
  }

  function setValue(target, value) {
    const field = findField(target);
    if (!field) return;
    updateFieldDisplay(field, parseToISO(value));
  }

  function resetForm(form) {
    form.querySelectorAll(".date-picker").forEach((field) => clearField(field));
  }

  window.DatePicker = { init, setValue, clear: clearField, resetForm };
})();
