<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import {
  NButton,
  NDatePicker,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  useMessage,
} from "naive-ui";
import * as echarts from "echarts";
import { api } from "../api/client";
import { fmt, toDateString } from "../utils/format";

const props = defineProps({
  show: { type: Boolean, default: false },
});

const emit = defineEmits(["update:show"]);

const MAX_RANGE_DAYS = 7;

const message = useMessage();
const chartRef = ref(null);
const loading = ref(false);
const history = ref(null);
const selectedRange = ref(todayRange());
const lastValidRange = ref(todayRange());
const selectedLabel = ref("浙商黄金");

const labelOptions = [
  { label: "浙商黄金", value: "浙商黄金" },
  { label: "伦敦金", value: "伦敦金" },
];

const rangeShortcuts = {
  今天: () => todayRange(),
  近3天: () => recentRange(3),
  近7天: () => recentRange(7),
};

let chartInstance = null;
let resizeObserver = null;

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function todayRange() {
  const today = startOfToday();
  return [today, today];
}

function recentRange(days) {
  const end = startOfToday();
  const start = end - (days - 1) * 24 * 60 * 60 * 1000;
  return [start, end];
}

function rangeDayCount(startTs, endTs) {
  if (!startTs || !endTs) return 0;
  return Math.floor((endTs - startTs) / (24 * 60 * 60 * 1000)) + 1;
}

function formatRangeLabel(startTs, endTs) {
  const start = toDateString(startTs);
  const end = toDateString(endTs);
  if (!start || !end) return "";
  return start === end ? start : `${start} ~ ${end}`;
}

function formatAxisLabel(timeStr, isSingleDay) {
  if (!timeStr) return "";
  if (isSingleDay) return timeStr.slice(11, 16);
  return `${timeStr.slice(5, 10)} ${timeStr.slice(11, 16)}`;
}

function closeModal() {
  emit("update:show", false);
}

function disposeChart() {
  resizeObserver?.disconnect();
  resizeObserver = null;
  chartInstance?.dispose();
  chartInstance = null;
}

function renderChart() {
  if (!chartRef.value) {
    disposeChart();
    return;
  }

  const points = history.value?.points || [];
  if (!points.length) {
    disposeChart();
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, undefined, { renderer: "canvas" });
    resizeObserver = new ResizeObserver(() => chartInstance?.resize());
    resizeObserver.observe(chartRef.value);
  }

  const startDate = history.value?.start_date;
  const endDate = history.value?.end_date;
  const isSingleDay = startDate && endDate && startDate === endDate;
  const times = points.map((p) => formatAxisLabel(p.time, isSingleDay));
  const prices = points.map((p) => p.price);
  const unit = history.value?.unit || "元/克";
  const summary = history.value?.summary;
  const useDataZoom = points.length > 48;

  chartInstance.setOption(
    {
      animation: false,
      grid: {
        left: 56,
        right: 20,
        top: 24,
        bottom: useDataZoom ? 72 : 48,
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(26, 29, 35, 0.95)",
        borderColor: "#2e3340",
        textStyle: { color: "#e8eaed", fontSize: 12 },
        formatter(params) {
          const item = params[0];
          const point = points[item.dataIndex];
          return `${point.time}<br/>${fmt(item.data)} ${unit}`;
        },
      },
      dataZoom: useDataZoom
        ? [
            {
              type: "inside",
              start: 0,
              end: 100,
            },
            {
              type: "slider",
              start: 0,
              end: 100,
              height: 18,
              bottom: 8,
              borderColor: "#2e3340",
              fillerColor: "rgba(212, 168, 83, 0.15)",
              handleStyle: { color: "#d4a853" },
              textStyle: { color: "#8b929e", fontSize: 10 },
            },
          ]
        : undefined,
      xAxis: {
        type: "category",
        data: times,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#2e3340" } },
        axisLabel: {
          color: "#8b929e",
          fontSize: 11,
          hideOverlap: true,
        },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLine: { show: false },
        axisLabel: {
          color: "#8b929e",
          fontSize: 11,
          formatter: (value) => Number(value).toFixed(2),
        },
        splitLine: { lineStyle: { color: "#2e3340", type: "dashed" } },
      },
      series: [
        {
          type: "line",
          data: prices,
          smooth: 0.25,
          showSymbol: false,
          lineStyle: { color: "#d4a853", width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(212, 168, 83, 0.28)" },
              { offset: 1, color: "rgba(212, 168, 83, 0.02)" },
            ]),
          },
          markLine: summary
            ? {
                symbol: "none",
                silent: true,
                lineStyle: { type: "dashed", color: "#5c6370", width: 1 },
                label: { color: "#8b929e", fontSize: 10 },
                data: [
                  { yAxis: summary.high, name: "高" },
                  { yAxis: summary.low, name: "低" },
                ],
              }
            : undefined,
        },
      ],
    },
    true
  );
}

function validateRange(range) {
  if (!Array.isArray(range) || range.length !== 2 || !range[0] || !range[1]) {
    return false;
  }
  if (range[0] > range[1]) {
    message.warning("开始日期不能晚于结束日期");
    return false;
  }
  if (rangeDayCount(range[0], range[1]) > MAX_RANGE_DAYS) {
    message.warning(`查询范围不能超过 ${MAX_RANGE_DAYS} 天`);
    return false;
  }
  return true;
}

async function loadHistory() {
  const [startTs, endTs] = selectedRange.value || [];
  const startDate = toDateString(startTs);
  const endDate = toDateString(endTs);
  if (!startDate || !endDate) return;
  if (!validateRange(selectedRange.value)) return;

  loading.value = true;
  try {
    const query = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      label: selectedLabel.value,
    });
    history.value = await api(`/stats/gold-price/history?${query.toString()}`);
    await nextTick();
    renderChart();
  } catch (err) {
    history.value = null;
    disposeChart();
    message.error(err.message || "加载行情失败");
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      const range = todayRange();
      selectedRange.value = range;
      lastValidRange.value = [...range];
      selectedLabel.value = "浙商黄金";
      return;
    }
    disposeChart();
    history.value = null;
  }
);

watch([selectedRange, selectedLabel], () => {
  if (!props.show) return;
  if (!validateRange(selectedRange.value)) {
    selectedRange.value = [...lastValidRange.value];
    return;
  }
  lastValidRange.value = [...selectedRange.value];
  loadHistory();
});

onBeforeUnmount(disposeChart);
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="金价趋势"
    style="max-width: 760px"
    @update:show="emit('update:show', $event)"
  >
    <NSpace vertical :size="16">
      <div class="toolbar">
        <NDatePicker
          v-model:value="selectedRange"
          type="daterange"
          :shortcuts="rangeShortcuts"
          :input-readonly="true"
          style="width: 280px"
        />
        <NSelect
          v-model:value="selectedLabel"
          :options="labelOptions"
          style="width: 140px"
        />
        <NButton quaternary :loading="loading" @click="loadHistory">刷新</NButton>
      </div>

      <NSpin :show="loading">
        <div v-if="history?.summary" class="summary-row">
          <span class="range-label">
            {{
              formatRangeLabel(
                selectedRange?.[0],
                selectedRange?.[1]
              )
            }}
          </span>
          <span>采样 {{ history.summary.count }} 次</span>
          <span>开 {{ fmt(history.summary.open) }}</span>
          <span>收 {{ fmt(history.summary.close) }}</span>
          <span>高 {{ fmt(history.summary.high) }}</span>
          <span>低 {{ fmt(history.summary.low) }}</span>
          <span class="unit">{{ history.unit }}</span>
        </div>

        <div v-if="history?.points?.length" ref="chartRef" class="chart-box" />

        <p v-else-if="!loading" class="empty-text">
          {{ formatRangeLabel(selectedRange?.[0], selectedRange?.[1]) }}
          暂无 {{ selectedLabel }} 采样记录
        </p>
      </NSpin>
    </NSpace>

    <template #footer>
      <NButton @click="closeModal">关闭</NButton>
    </template>
  </NModal>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
  color: #c4c8cf;
}

.range-label {
  color: #d4a853;
  font-weight: 600;
}

.unit {
  color: #8b929e;
}

.chart-box {
  width: 100%;
  height: 320px;
}

.empty-text {
  margin: 2rem 0;
  text-align: center;
  color: #8b929e;
  font-size: 0.9rem;
}
</style>
