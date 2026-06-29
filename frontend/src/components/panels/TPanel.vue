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
  NModal,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import { fmt, gainType, parseLegacyDate, statusMap, toDateString } from "../../utils/format";
import { usePagination } from "../../composables/usePagination";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();
const { pagination, watchDataLength } = usePagination(10);
watchDataLength(ledger.tRecords);

const form = ref({
  mark: "",
  count: null,
  pop_amount: null,
  sold_at: null,
});

const showEdit = ref(false);
const editingId = ref(null);
const editForm = ref({
  mark: "",
  count: null,
  pop_amount: null,
  sold_at: null,
  allocated_count: 0,
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

function actionButtons(r) {
  return h("div", { class: "actions" }, [
    h(
      NButton,
      { size: "small", quaternary: true, type: "primary", onClick: () => openEdit(r) },
      { default: () => "编辑" }
    ),
    h(
      NButton,
      { size: "small", quaternary: true, type: "error", onClick: () => onDelete(r.id) },
      { default: () => "删除" }
    ),
  ]);
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
  { title: "操作", key: "actions", width: 120, render: actionButtons },
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

function openEdit(record) {
  editingId.value = record.id;
  editForm.value = {
    mark: record.mark || "",
    count: record.count,
    pop_amount: record.pop_amount,
    sold_at: parseLegacyDate(record.sold_at),
    allocated_count: record.allocated_count || 0,
  };
  showEdit.value = true;
}

async function submitEdit() {
  if (!editForm.value.count || !editForm.value.pop_amount) {
    message.warning("请填写克数和回笼金额");
    return;
  }
  if (editForm.value.count + 1e-9 < editForm.value.allocated_count) {
    message.warning(`克数不能小于已配对克数 ${fmt(editForm.value.allocated_count)} 克`);
    return;
  }
  try {
    await ledger.updateT(editingId.value, {
      mark: editForm.value.mark,
      count: editForm.value.count,
      pop_amount: editForm.value.pop_amount,
      sold_at: editForm.value.sold_at ? toDateString(editForm.value.sold_at) : null,
    });
    showEdit.value = false;
    message.success("已保存");
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
      :scroll-x="1020"
      :pagination="pagination"
    />
  </NCard>

  <NModal v-model:show="showEdit" preset="card" title="编辑倒 T 记录" style="max-width: 520px">
    <p v-if="editForm.allocated_count > 0" class="hint-text">
      已配对 {{ fmt(editForm.allocated_count) }} 克，克数不能小于该值
    </p>
    <NForm @submit.prevent="submitEdit">
      <NFormItem label="备注 mark">
        <NInput v-model:value="editForm.mark" />
      </NFormItem>
      <NFormItem label="克数 count">
        <NInputNumber
          v-model:value="editForm.count"
          :min="editForm.allocated_count || 0.01"
          :precision="2"
          class="full-width"
        />
      </NFormItem>
      <NFormItem label="回笼金额 pop_amount">
        <NInputNumber v-model:value="editForm.pop_amount" :min="0.01" :precision="2" class="full-width" />
      </NFormItem>
      <NFormItem label="卖出日期">
        <NDatePicker
          v-model:value="editForm.sold_at"
          type="date"
          clearable
          class="full-width"
          :input-readonly="true"
        />
      </NFormItem>
      <div class="modal-actions">
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" attr-type="submit">保存</NButton>
      </div>
    </NForm>
  </NModal>
</template>

<style scoped>
.section-card {
  margin-bottom: 1rem;
}

.full-width {
  width: 100%;
}

.actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
</style>
