<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as echarts from "echarts";
import { fmt } from "../utils/format";

const props = defineProps({
  slices: { type: Array, default: () => [] },
  unit: { type: String, default: "元" },
});

const COLORS = [
  "#d4a853",
  "#5b9bd5",
  "#70ad47",
  "#ed7d31",
  "#9b7ebd",
  "#4ecdc4",
  "#c9a227",
  "#e06c75",
  "#61afef",
  "#98c379",
];

const chartRef = ref(null);
let chartInstance = null;
let resizeObserver = null;

function disposeChart() {
  resizeObserver?.disconnect();
  resizeObserver = null;
  chartInstance?.dispose();
  chartInstance = null;
}

function renderChart() {
  if (!chartRef.value || !props.slices.length) {
    disposeChart();
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, undefined, { renderer: "canvas" });
    resizeObserver = new ResizeObserver(() => chartInstance?.resize());
    resizeObserver.observe(chartRef.value);
  }

  const data = props.slices.map((slice, index) => ({
    name: slice.name,
    value: slice.value,
    amount: slice.amount,
    itemStyle: { color: COLORS[index % COLORS.length] },
  }));

  chartInstance.setOption(
    {
      animation: false,
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(26, 29, 35, 0.95)",
        borderColor: "#2e3340",
        textStyle: { color: "#e8eaed", fontSize: 12 },
        formatter(params) {
          const amount = params.data?.amount ?? params.value;
          return `${params.name}<br/>${fmt(amount)} ${props.unit}（${params.percent}%）`;
        },
      },
      legend: {
        type: "scroll",
        bottom: 0,
        textStyle: { color: "#8b929e", fontSize: 12 },
        pageIconColor: "#d4a853",
        pageTextStyle: { color: "#8b929e" },
      },
      series: [
        {
          type: "pie",
          radius: ["38%", "64%"],
          center: ["50%", "46%"],
          avoidLabelOverlap: true,
          data,
          label: {
            color: "#c4c8cf",
            fontSize: 11,
            formatter: (params) => `${params.name}\n${fmt(params.data.amount)}`,
          },
          labelLine: {
            lineStyle: { color: "#5c6370" },
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 12,
              shadowColor: "rgba(0, 0, 0, 0.35)",
            },
          },
        },
      ],
    },
    true
  );
}

watch(
  () => props.slices,
  async () => {
    await nextTick();
    renderChart();
  },
  { deep: true, immediate: true }
);

onBeforeUnmount(disposeChart);
</script>

<template>
  <div v-if="slices.length" ref="chartRef" class="book-pie" />
  <p v-else class="hint-text">当天没有非零项目</p>
</template>

<style scoped>
.book-pie {
  width: 100%;
  height: 320px;
}

.hint-text {
  margin: 0;
  color: #8b929e;
  font-size: 0.875rem;
}
</style>
