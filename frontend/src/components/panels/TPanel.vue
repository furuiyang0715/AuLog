<script setup>
import { h, inject, ref } from "vue";
import {
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import { fmt, gainType, statusMap, toDateString } from "../../utils/format";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();

const form = ref({
  mark: "",
  count: null,
  pop_amount: null,
  sold_at: null,
});

function hStatus(status) {
  const meta = statusMap[status] || { label: status, type: "default" };
  return h(NTag, { size: "small", type: meta.type, bordered: false }, { default: () => meta.label });
}

function renderGain(r) {
  const type = gainType(r.gain);
  return h(
    "span",
    { class: type === "success" ? "gain-positive" : type === "error" ? "gain-negative" : "" },
    fmt(r.gain)
  );
}

const columns = [
  { title: "备注", key: "mark", render: (r) => r.mark || "—" },
  { title: "克数", key: "count", render: (r) => fmt(r.count) },
  { title: "回笼", key: "pop_amount", render: (r) => fmt(r.pop_amount) },
  { title: "卖价", key: "price", render: (r) => fmt(r.price) },
  { title: "买回成本", key: "push_amount", render: (r) => fmt(r.push_amount) },
  { title: "套利 gain", key: "gain", render: renderGain },
  {
    title: "已配/剩余",
    key: "allocated",
    render: (r) => `${fmt(r.allocated_count)} / ${fmt(r.remaining_count)}`,
  },
  { title: "状态", key: "status", render: (r) => hStatus(r.status) },
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

async function submit() {
  if (!form.value.count || !form.value.pop_amount) {
    message.warning("请填写克数和回笼金额");
    return;
  }
  try {
    await ledger.createT({
      mark: form.value.mark,
      count: form.value.count,
      pop_amount: form.value.pop_amount,
      sold_at: form.value.sold_at ? toDateString(form.value.sold_at) : null,
    });
    form.value = { mark: "", count: null, pop_amount: null, sold_at: null };
    message.success("倒 T 记录已添加");
  } catch (err) {
    message.error(err.message);
  }
}

function onDelete(id) {
  dialog.warning({
    title: "确认删除",
    content: "确定删除这条倒 T 记录？",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await ledger.deleteT(id);
        message.success("已删除");
      } catch (err) {
        message.error(err.message);
      }
    },
  });
}
</script>

<template>
  <NCard title="新建卖出记录" :bordered="false" class="section-card">
    <NForm @submit.prevent="submit">
      <NGrid :cols="24" :x-gap="12" :y-gap="8" item-responsive responsive="screen">
        <NGridItem span="24 m:8">
          <NFormItem label="备注 mark">
            <NInput v-model:value="form.mark" placeholder="卖了什么" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="克数 count">
            <NInputNumber v-model:value="form.count" :min="0.01" :precision="2" class="full-width" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="回笼金额 pop_amount">
            <NInputNumber v-model:value="form.pop_amount" :min="0.01" :precision="2" class="full-width" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="卖出日期">
            <NDatePicker
              v-model:value="form.sold_at"
              type="date"
              clearable
              class="full-width"
              :input-readonly="true"
            />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24">
          <NButton type="primary" attr-type="submit">添加</NButton>
        </NGridItem>
      </NGrid>
    </NForm>
  </NCard>

  <NCard title="倒 T 列表" :bordered="false" class="section-card">
    <NDataTable
      :columns="columns"
      :data="ledger.tRecords.value"
      :loading="ledger.loading.value"
      :bordered="false"
      size="small"
      :scroll-x="960"
    />
  </NCard>
</template>

<style scoped>
.section-card {
  margin-bottom: 1rem;
}

.full-width {
  width: 100%;
}
</style>
