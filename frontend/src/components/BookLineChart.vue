<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as echarts from "echarts";
import { fmt, formatDateDisplay } from "../utils/format";

const props = defineProps({
  points: { type: Array, default: () => [] },
  unit: { type: String, default: "元" },
});

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
  if (!chartRef.value || !props.points.length) {
    disposeChart();
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, undefined, { renderer: "canvas" });
    resizeObserver = new ResizeObserver(() => chartInstance?.resize());
    resizeObserver.observe(chartRef.value);
  }

  const labels = props.points.map((p) => formatDateDisplay(p.date));
  const values = props.points.map((p) => Number(p.value) || 0);
  const showSymbol = props.points.length <= 16;

  chartInstance.setOption(
    {
      animation: false,
      grid: { left: 64, right: 20, top: 24, bottom: 40 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(26, 29, 35, 0.95)",
        borderColor: "#2e3340",
        textStyle: { color: "#e8eaed", fontSize: 12 },
        formatter(params) {
          const item = params[0];
          const point = props.points[item.dataIndex];
          return `${formatDateDisplay(point.date)}<br/>${fmt(item.data)} ${props.unit}`;
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#2e3340" } },
        axisLabel: { color: "#8b929e", fontSize: 11, hideOverlap: true },
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
          data: values,
          smooth: 0.2,
          showSymbol,
          symbolSize: 8,
          lineStyle: { color: "#d4a853", width: 2 },
          itemStyle: { color: "#d4a853" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(212, 168, 83, 0.28)" },
              { offset: 1, color: "rgba(212, 168, 83, 0.02)" },
            ]),
          },
        },
      ],
    },
    true
  );
}

watch(
  () => props.points,
  async () => {
    await nextTick();
    renderChart();
  },
  { deep: true, immediate: true }
);

onBeforeUnmount(disposeChart);
</script>

<template>
  <div v-if="points.length" ref="chartRef" class="book-chart" />
  <p v-else class="hint-text">暂无记录</p>
</template>

<style scoped>
.book-chart {
  width: 100%;
  height: 240px;
}

.hint-text {
  margin: 0;
  color: #8b929e;
  font-size: 0.875rem;
}
</style>
