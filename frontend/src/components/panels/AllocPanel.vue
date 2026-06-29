<script setup>
import { h, inject } from "vue";
import { NButton, NCard, NDataTable, useDialog, useMessage } from "naive-ui";
import { fmt } from "../../utils/format";
import { usePagination } from "../../composables/usePagination";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();
const { pagination, watchDataLength } = usePagination(10);
watchDataLength(ledger.allocations);

const columns = [
  {
    title: "类型",
    key: "target_type",
    render: (r) => (r.target_type === "T_MATCH" ? "配对倒T" : "反弹卖出"),
  },
  {
    title: "ing",
    key: "ing_id",
    render: (r) => ledger.ingRecords.value.find((i) => i.id === r.ing_id)?.mark || "—",
  },
  {
    title: "目标",
    key: "target_id",
    render: (r) => ledger.targetMark(r),
  },
  { title: "克数", key: "count", render: (r) => fmt(r.count) },
  { title: "成本", key: "amount", render: (r) => fmt(r.amount) },
  {
    title: "操作",
    key: "actions",
    render: (r) =>
      h(
        NButton,
        { size: "small", quaternary: true, type: "error", onClick: () => onDelete(r.id) },
        { default: () => "撤销" }
      ),
  },
];

function onDelete(id) {
  dialog.warning({
    title: "确认撤销",
    content: "确定撤销这条分配？反弹卖出会一并删除",
    positiveText: "撤销",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await ledger.deleteAlloc(id);
        message.success("已撤销");
      } catch (err) {
        message.error(err.message);
      }
    },
  });
}
</script>

<template>
  <NCard title="分配记录" :bordered="false" class="section-card">
    <p class="hint-text">ing 克数分配到倒 T 配对，或反弹卖出。</p>
    <NDataTable
      :columns="columns"
      :data="ledger.allocations.value"
      :loading="ledger.loading.value"
      :bordered="false"
      size="small"
      :scroll-x="760"
      :pagination="pagination"
    />
  </NCard>
</template>

<style scoped>
.section-card {
  margin-bottom: 1rem;
}
</style>
