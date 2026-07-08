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

const message = useMessage();
const chartRef = ref(null);
const loading = ref(false);
const history = ref(null);
const selectedDate = ref(startOfToday());
const selectedLabel = ref("浙商黄金");

const labelOptions = [
  { label: "浙商黄金", value: "浙商黄金" },
  { label: "伦敦金", value: "伦敦金" },
];

let chartInstance = null;
let resizeObserver = null;

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
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

  const times = points.map((p) => p.time.slice(11, 16));
  const prices = points.map((p) => p.price);
  const unit = history.value?.unit || "元/克";
  const summary = history.value?.summary;

  chartInstance.setOption(
    {
      animation: false,
      grid: { left: 56, right: 20, top: 24, bottom: 48 },
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
      xAxis: {
        type: "category",
        data: times,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#2e3340" } },
        axisLabel: { color: "#8b929e", fontSize: 11 },
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

async function loadHistory() {
  const dateStr = toDateString(selectedDate.value);
  if (!dateStr) return;

  loading.value = true;
  try {
    const query = new URLSearchParams({
      date: dateStr,
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
      selectedDate.value = startOfToday();
      selectedLabel.value = "浙商黄金";
      loadHistory();
      return;
    }
    disposeChart();
    history.value = null;
  }
);

watch([selectedDate, selectedLabel], () => {
  if (props.show) {
    loadHistory();
  }
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
          v-model:value="selectedDate"
          type="date"
          :input-readonly="true"
          style="width: 180px"
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
          <span>采样 {{ history.summary.count }} 次</span>
          <span>开 {{ fmt(history.summary.open) }}</span>
          <span>收 {{ fmt(history.summary.close) }}</span>
          <span>高 {{ fmt(history.summary.high) }}</span>
          <span>低 {{ fmt(history.summary.low) }}</span>
          <span class="unit">{{ history.unit }}</span>
        </div>

        <div v-if="history?.points?.length" ref="chartRef" class="chart-box" />

        <p v-else-if="!loading" class="empty-text">
          {{ history?.date || toDateString(selectedDate) }} 暂无 {{ selectedLabel }} 采样记录
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
