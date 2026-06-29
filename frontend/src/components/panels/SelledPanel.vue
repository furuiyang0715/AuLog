<script setup>
import { h, inject } from "vue";
import { NButton, NCard, NDataTable, useDialog, useMessage } from "naive-ui";
import { fmt, formatDateDisplay, gainType } from "../../utils/format";
import { usePagination } from "../../composables/usePagination";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();
const { pagination, watchDataLength } = usePagination(10);
watchDataLength(ledger.selledRecords);

const columns = [
  { title: "日期", key: "date", render: (r) => formatDateDisplay(r.date) },
  { title: "备注", key: "mark", render: (r) => r.mark || "—" },
  { title: "买入价", key: "buy_price", render: (r) => fmt(r.buy_price) },
  { title: "克数", key: "count", render: (r) => fmt(r.count) },
  { title: "买入额", key: "buy_amount", render: (r) => fmt(r.buy_amount) },
  { title: "卖出价", key: "sell_price", render: (r) => fmt(r.sell_price) },
  { title: "卖出额", key: "sell_amount", render: (r) => fmt(r.sell_amount) },
  {
    title: "获利",
    key: "gain",
    render: (r) => {
      const type = gainType(r.gain);
      return h(
        "span",
        { class: type === "success" ? "gain-positive" : type === "error" ? "gain-negative" : "" },
        fmt(r.gain)
      );
    },
  },
  {
    title: "操作",
    key: "actions",
    render: (r) =>
      h(
        NButton,
        { size: "small", quaternary: true, type: "error", onClick: () => onDelete(r.id) },
        { default: () => "删除" }
      ),
  },
];

function onDelete(id) {
  dialog.warning({
    title: "确认删除",
    content: "确定删除？关联分配也会撤销",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await ledger.deleteSelled(id);
        message.success("已删除");
      } catch (err) {
        message.error(err.message);
      }
    },
  });
}
</script>

<template>
  <NCard :bordered="false" class="section-card">
    <p class="hint-text">反弹卖出只能从「进货 ing」列表中操作「反弹卖出」创建，并自动关联对应进货记录。</p>
  </NCard>

  <NCard title="反弹卖出列表" :bordered="false" class="section-card">
    <NDataTable
      :columns="columns"
      :data="ledger.selledRecords.value"
      :loading="ledger.loading.value"
      :bordered="false"
      size="small"
      :scroll-x="900"
      :pagination="pagination"
    />
  </NCard>
</template>

<style scoped>
.section-card {
  margin-bottom: 1rem;
}
</style>
