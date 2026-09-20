<script setup>
import { computed, onMounted, ref, watch } from "vue";
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInputNumber,
  NSpin,
  useMessage,
} from "naive-ui";
import { api } from "../../api/client";
import { fmt } from "../../utils/format";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

const message = useMessage();
const month = ref(currentMonth());
const summary = ref(null);
const salaryInput = ref(null);
const loading = ref(false);
const savingSalary = ref(false);
const toggling = ref(false);

function pad(n) {
  return String(n).padStart(2, "0");
}

function currentMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
}

function todayString() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatMonthLabel(value) {
  if (!value) return "";
  const [year, monthN] = value.split("-");
  return `${year}年${Number(monthN)}月`;
}

function shiftMonth(delta) {
  const [year, monthN] = month.value.split("-").map(Number);
  const next = new Date(year, monthN - 1 + delta, 1);
  month.value = `${next.getFullYear()}-${pad(next.getMonth() + 1)}`;
}

const workSet = computed(() => new Set(summary.value?.work_dates || []));

const calendarCells = computed(() => {
  const days = summary.value?.days_in_month;
  if (!days) return [];
  const [year, monthN] = month.value.split("-").map(Number);
  const lead = (new Date(year, monthN - 1, 1).getDay() + 6) % 7;
  const today = todayString();
  const cells = Array.from({ length: lead }, () => null);
  for (let day = 1; day <= days; day += 1) {
    const date = `${month.value}-${pad(day)}`;
    cells.push({
      date,
      day,
      working: workSet.value.has(date),
      today: date === today,
    });
  }
  return cells;
});

const rateHint = computed(() => {
  const data = summary.value;
  if (!data) return "";
  if (data.rate_basis === "attendance") {
    return `按时薪估算：上月出勤 ${data.prev_work_count} 天 × ${data.hours_per_day} 小时。`;
  }
  return `上月还没有出勤记录，暂按上月 ${data.days_in_prev_month} 个自然日 × ${data.hours_per_day} 小时估算。`;
});

async function loadMonth() {
  loading.value = true;
  try {
    const data = await api(`/work/month?month=${month.value}`);
    summary.value = data;
    salaryInput.value = data.prev_salary;
  } catch (err) {
    message.error(err.message || "加载工时日志失败");
  } finally {
    loading.value = false;
  }
}

async function saveSalary() {
  if (!summary.value) return;
  if (salaryInput.value == null || Number(salaryInput.value) <= 0) {
    message.warning("请填写上月月薪");
    return;
  }
  savingSalary.value = true;
  try {
    await api("/work/salary", {
      method: "PUT",
      body: JSON.stringify({
        month: summary.value.prev_month,
        amount: salaryInput.value,
      }),
    });
    await loadMonth();
    message.success("上月月薪已保存");
  } catch (err) {
    message.error(err.message);
  } finally {
    savingSalary.value = false;
  }
}

async function toggleDay(cell) {
  if (!cell || toggling.value) return;
  toggling.value = true;
  try {
    const data = await api(`/work/days/${cell.date}`, {
      method: "PUT",
      body: JSON.stringify({ working: !cell.working }),
    });
    summary.value = data;
    salaryInput.value = data.prev_salary;
  } catch (err) {
    message.error(err.message);
  } finally {
    toggling.value = false;
  }
}

watch(month, loadMonth);
onMounted(loadMonth);
</script>

<template>
  <NCard title="工时日志" :bordered="false" class="section-card">
    <p class="hint-text">
      填写上月月薪，再点选出勤日。每个出勤日按 {{ summary?.hours_per_day || 15 }} 小时估算当日收入。可翻到上一月补点上月出勤，时薪会更准。
    </p>

    <div class="month-nav">
      <NButton size="small" @click="shiftMonth(-1)">上一月</NButton>
      <strong class="month-label">{{ formatMonthLabel(month) }}</strong>
      <NButton size="small" @click="shiftMonth(1)">下一月</NButton>
      <NButton size="small" quaternary @click="month = currentMonth()">本月</NButton>
    </div>

    <NSpin :show="loading">
      <NForm class="salary-row" @submit.prevent="saveSalary">
        <NFormItem :label="`上月月薪（${formatMonthLabel(summary?.prev_month)}）`">
          <div class="salary-fields">
            <NInputNumber
              v-model:value="salaryInput"
              :min="0.01"
              :precision="2"
              class="salary-input"
              placeholder="元"
            />
            <NButton type="primary" attr-type="submit" :loading="savingSalary">保存月薪</NButton>
          </div>
        </NFormItem>
      </NForm>

      <div class="summary-grid">
        <div class="summary-item">
          <div class="summary-k">时薪</div>
          <div class="summary-v">{{ fmt(summary?.hourly_rate) }} 元</div>
        </div>
        <div class="summary-item">
          <div class="summary-k">当日预估</div>
          <div class="summary-v">{{ fmt(summary?.daily_estimate) }} 元</div>
        </div>
        <div class="summary-item">
          <div class="summary-k">本月出勤</div>
          <div class="summary-v">{{ summary?.work_dates?.length || 0 }} 天</div>
        </div>
        <div class="summary-item">
          <div class="summary-k">本月预估合计</div>
          <div class="summary-v">{{ fmt(summary?.month_total) }} 元</div>
        </div>
      </div>
      <p class="hint-text">{{ rateHint }}</p>

      <div class="calendar">
        <div v-for="label in WEEKDAYS" :key="label" class="weekday">{{ label }}</div>
        <button
          v-for="(cell, index) in calendarCells"
          :key="cell?.date || `empty-${index}`"
          type="button"
          class="day-cell"
          :class="{
            empty: !cell,
            working: cell?.working,
            today: cell?.today,
          }"
          :disabled="!cell || toggling"
          @click="toggleDay(cell)"
        >
          <template v-if="cell">
            <span class="day-num">{{ cell.day }}</span>
            <span v-if="cell.working" class="day-pay">{{ fmt(summary?.daily_estimate) }}</span>
            <span v-else class="day-pay muted">点选出勤</span>
          </template>
        </button>
      </div>
    </NSpin>
  </NCard>
</template>

<style scoped>
.section-card {
  margin-bottom: 1rem;
}

.hint-text {
  margin: 0 0 0.75rem;
  color: #8b929e;
  font-size: 0.875rem;
}

.month-nav {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.month-label {
  min-width: 7.5rem;
  text-align: center;
  color: #d4a853;
  font-size: 1.05rem;
}

.salary-row {
  max-width: 520px;
}

.salary-fields {
  display: flex;
  gap: 0.5rem;
  width: 100%;
}

.salary-input {
  flex: 1;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.summary-item {
  padding: 0.75rem 1rem;
  border: 1px solid #2e3340;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(212, 168, 83, 0.1) 0%, rgba(26, 29, 35, 0.8) 100%);
}

.summary-k {
  color: #8b929e;
  font-size: 0.8rem;
}

.summary-v {
  margin-top: 0.25rem;
  color: #d4a853;
  font-size: 1.15rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.calendar {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0.5rem;
}

.weekday {
  text-align: center;
  color: #8b929e;
  font-size: 0.8rem;
  padding: 0.25rem 0;
}

.day-cell {
  appearance: none;
  min-height: 76px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.35rem;
  padding: 0.55rem 0.6rem;
  border: 1px solid #2e3340;
  border-radius: 10px;
  background: #16181d;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.day-cell.empty {
  visibility: hidden;
  cursor: default;
}

.day-cell:not(.empty):hover,
.day-cell:not(.empty):focus-visible {
  border-color: #d4a853;
  outline: none;
}

.day-cell.today {
  box-shadow: inset 0 0 0 1px rgba(212, 168, 83, 0.45);
}

.day-cell.working {
  background: linear-gradient(135deg, rgba(212, 168, 83, 0.2) 0%, rgba(26, 29, 35, 0.92) 100%);
  border-color: #d4a853;
}

.day-num {
  font-weight: 600;
  color: #e8eaed;
}

.day-pay {
  font-size: 0.75rem;
  color: #d4a853;
  font-variant-numeric: tabular-nums;
}

.day-pay.muted {
  color: #5c6370;
}
</style>
