<script setup>
import { computed, h, inject, ref } from "vue";
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
  NSelect,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import { fmt, formatDateDisplay, gainType, parseLegacyDate, statusMap, toDateString } from "../../utils/format";
import { usePagination } from "../../composables/usePagination";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();
const { pagination, watchDataLength } = usePagination(10);
watchDataLength(ledger.ingRecords);

const ingUnclosedTotal = computed(() =>
  ledger.ingRecords.value.reduce((sum, r) => sum + (Number(r.remaining_count) || 0), 0)
);

const form = ref({
  date: null,
  mark: "",
  price: null,
  count: null,
  amount: null,
});

const showMatch = ref(false);
const matchForm = ref({ t_id: null, count: null });
const selectedIng = ref(null);

const tOptionsForIng = (ing) => {
  if (!ing) return [];
  const buyPrice = Number(ing.price);
  return ledger.tRecords.value
    .filter((t) => t.remaining_count > 0 && Number(t.price) + 1e-9 >= buyPrice)
    .map((t) => ({
      label: `${t.mark || "无备注"} · 剩余 ${fmt(t.remaining_count)} 克 · 卖价 ${fmt(t.price)}`,
      value: t.id,
    }));
};

function hStatus(status) {
  const meta = statusMap[status] || { label: status, type: "default" };
  return h(NTag, { size: "small", type: meta.type, bordered: false }, { default: () => meta.label });
}

const columns = [
  { title: "日期", key: "date", render: (r) => formatDateDisplay(r.date) },
  { title: "备注", key: "mark", render: (r) => r.mark || "—" },
  { title: "单价", key: "price", render: (r) => fmt(r.price) },
  { title: "克数", key: "count", render: (r) => fmt(r.count) },
  { title: "总价", key: "amount", render: (r) => fmt(r.amount) },
  {
    title: "已配/剩余",
    key: "allocated",
    render: (r) => `${fmt(r.allocated_count)} / ${fmt(r.remaining_count)}`,
  },
  { title: "配倒T", key: "allocated_to_t", render: (r) => fmt(r.allocated_to_t) },
  { title: "已消利", key: "is_change", render: (r) => (r.is_change ? "✓" : "—") },
  { title: "状态", key: "allocation_status", render: (r) => hStatus(r.allocation_status) },
  {
    title: "操作",
    key: "actions",
    width: 260,
    render: (r) =>
      h("div", { class: "actions" }, [
        h(
          NButton,
          { size: "small", quaternary: true, type: "primary", onClick: () => openEdit(r) },
          { default: () => "编辑" }
        ),
        r.remaining_count > 0
          ? h(
              NButton,
              { size: "small", type: "primary", ghost: true, onClick: () => openMatch(r) },
              { default: () => "配对倒T" }
            )
          : null,
        r.remaining_count > 0
          ? h(
              NButton,
              { size: "small", quaternary: true, onClick: () => openSelled(r) },
              { default: () => "反弹卖出" }
            )
          : null,
        h(
          NButton,
          { size: "small", quaternary: true, type: "error", onClick: () => onDelete(r.id) },
          { default: () => "删除" }
        ),
      ]),
  },
];

const showSelled = ref(false);
const selledForm = ref({ date: null, mark: "", count: null, sell_price: null });

const showEdit = ref(false);
const editingId = ref(null);
const editForm = ref({
  date: null,
  mark: "",
  price: null,
  count: null,
  amount: null,
  allocated_count: 0,
});

async function submit() {
  if (!form.value.date || !form.value.price || !form.value.count) {
    message.warning("请填写日期、单价和克数");
    return;
  }
  try {
    await ledger.createIng({
      date: toDateString(form.value.date),
      mark: form.value.mark,
      price: form.value.price,
      count: form.value.count,
      amount: form.value.amount,
    });
    form.value = { date: null, mark: "", price: null, count: null, amount: null };
    message.success("进货记录已添加");
  } catch (err) {
    message.error(err.message);
  }
}

function openMatch(ing) {
  const options = tOptionsForIng(ing);
  if (!options.length) {
    message.warning("没有卖价不低于进货价的可配对倒 T");
    return;
  }
  selectedIng.value = ing;
  matchForm.value = {
    t_id: options[0].value,
    count: Math.min(
      ing.remaining_count,
      ledger.tRecords.value.find((t) => t.id === options[0].value)?.remaining_count ||
        ing.remaining_count
    ),
  };
  showMatch.value = true;
}

function openSelled(ing) {
  selectedIng.value = ing;
  selledForm.value = {
    date: parseLegacyDate(ing.date),
    mark: ing.mark || "",
    count: ing.remaining_count,
    sell_price: null,
  };
  showSelled.value = true;
}

function openEdit(record) {
  editingId.value = record.id;
  editForm.value = {
    date: parseLegacyDate(record.date),
    mark: record.mark || "",
    price: record.price,
    count: record.count,
    amount: record.amount,
    allocated_count: record.allocated_count || 0,
  };
  showEdit.value = true;
}

async function submitEdit() {
  if (!editForm.value.date || !editForm.value.price || !editForm.value.count) {
    message.warning("请填写日期、单价和克数");
    return;
  }
  if (editForm.value.count + 1e-9 < editForm.value.allocated_count) {
    message.warning(`克数不能小于已分配克数 ${fmt(editForm.value.allocated_count)} 克`);
    return;
  }
  try {
    await ledger.updateIng(editingId.value, {
      date: toDateString(editForm.value.date),
      mark: editForm.value.mark,
      price: editForm.value.price,
      count: editForm.value.count,
      amount: editForm.value.amount,
    });
    showEdit.value = false;
    message.success("已保存");
  } catch (err) {
    message.error(err.message);
  }
}

async function submitMatch() {
  try {
    await ledger.matchT({
      ing_id: selectedIng.value.id,
      t_id: matchForm.value.t_id,
      count: matchForm.value.count,
    });
    showMatch.value = false;
    message.success("配对成功");
  } catch (err) {
    message.error(err.message);
  }
}

async function submitSelled() {
  if (!selledForm.value.date || !selledForm.value.count || !selledForm.value.sell_price) {
    message.warning("请完整填写卖出信息");
    return;
  }
  try {
    await ledger.sellFromIng({
      ing_id: selectedIng.value.id,
      date: toDateString(selledForm.value.date),
      mark: selledForm.value.mark,
      count: selledForm.value.count,
      sell_price: selledForm.value.sell_price,
    });
    showSelled.value = false;
    message.success("反弹卖出已记录");
  } catch (err) {
    message.error(err.message);
  }
}

function onDelete(id) {
  dialog.warning({
    title: "确认删除",
    content: "确定删除这条进货记录？",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await ledger.deleteIng(id);
        message.success("已删除");
      } catch (err) {
        message.error(err.message);
      }
    },
  });
}
</script>

<template>
  <NCard title="新建进货记录" :bordered="false" class="section-card">
    <NForm @submit.prevent="submit">
      <NGrid :cols="24" :x-gap="12" :y-gap="8" item-responsive responsive="screen">
        <NGridItem span="24 m:8">
          <NFormItem label="日期 date">
            <NDatePicker v-model:value="form.date" type="date" class="full-width" :input-readonly="true" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="备注 mark">
            <NInput v-model:value="form.mark" placeholder="买了什么" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="单价 price">
            <NInputNumber v-model:value="form.price" :min="0.01" :precision="2" class="full-width" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="克数 count">
            <NInputNumber v-model:value="form.count" :min="0.01" :precision="2" class="full-width" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="总价 amount">
            <NInputNumber v-model:value="form.amount" :min="0" :precision="2" class="full-width" placeholder="留空自动计算" />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24">
          <NButton type="primary" attr-type="submit">添加</NButton>
        </NGridItem>
      </NGrid>
    </NForm>
  </NCard>

  <NCard :bordered="false" class="section-card summary-card">
    <div class="summary-row">
      <div>
        <div class="summary-label">当前需闭合总克数</div>
        <div class="hint-text">进货未分完的剩余克数之和（未分配 + 部分分配）</div>
      </div>
      <div class="summary-value summary-count">{{ fmt(ingUnclosedTotal) }}</div>
    </div>
  </NCard>

  <NCard title="进货列表" :bordered="false" class="section-card">
    <NDataTable
      :columns="columns"
      :data="ledger.ingRecords.value"
      :loading="ledger.loading.value"
      :bordered="false"
      size="small"
      :pagination="pagination"
    />
  </NCard>

  <NModal v-model:show="showEdit" preset="card" title="编辑进货记录" style="max-width: 520px">
    <p v-if="editForm.allocated_count > 0" class="hint-text">
      已分配 {{ fmt(editForm.allocated_count) }} 克，克数不能小于该值；修改单价会同步更新倒 T 配对的买回成本
    </p>
    <NForm @submit.prevent="submitEdit">
      <NFormItem label="日期 date">
        <NDatePicker v-model:value="editForm.date" type="date" class="full-width" :input-readonly="true" />
      </NFormItem>
      <NFormItem label="备注 mark">
        <NInput v-model:value="editForm.mark" />
      </NFormItem>
      <NFormItem label="单价 price">
        <NInputNumber v-model:value="editForm.price" :min="0.01" :precision="2" class="full-width" />
      </NFormItem>
      <NFormItem label="克数 count">
        <NInputNumber
          v-model:value="editForm.count"
          :min="editForm.allocated_count || 0.01"
          :precision="2"
          class="full-width"
        />
      </NFormItem>
      <NFormItem label="总价 amount">
        <NInputNumber v-model:value="editForm.amount" :min="0" :precision="2" class="full-width" placeholder="留空按单价×克数" />
      </NFormItem>
      <div class="modal-actions">
        <NButton @click="showEdit = false">取消</NButton>
        <NButton type="primary" attr-type="submit">保存</NButton>
      </div>
    </NForm>
  </NModal>

  <NModal v-model:show="showMatch" preset="card" title="配对倒 T" style="max-width: 460px">
    <p v-if="selectedIng" class="hint-text">
      {{ selectedIng.mark || "无备注" }} · 单价 {{ fmt(selectedIng.price) }} · 剩余 {{ fmt(selectedIng.remaining_count) }} 克
    </p>
    <NForm @submit.prevent="submitMatch">
      <NFormItem label="选择倒 T 记录">
        <NSelect v-model:value="matchForm.t_id" :options="tOptionsForIng(selectedIng)" />
      </NFormItem>
      <NFormItem label="配对克数">
        <NInputNumber v-model:value="matchForm.count" :min="0.01" :precision="2" class="full-width" />
      </NFormItem>
      <div class="modal-actions">
        <NButton @click="showMatch = false">取消</NButton>
        <NButton type="primary" attr-type="submit">确认配对</NButton>
      </div>
    </NForm>
  </NModal>

  <NModal v-model:show="showSelled" preset="card" title="反弹卖出" style="max-width: 460px">
    <p v-if="selectedIng" class="hint-text">
      {{ selectedIng.mark || "无备注" }} · 买入价 {{ fmt(selectedIng.price) }} · 剩余 {{ fmt(selectedIng.remaining_count) }} 克
    </p>
    <NForm @submit.prevent="submitSelled">
      <NFormItem label="日期">
        <NDatePicker v-model:value="selledForm.date" type="date" class="full-width" :input-readonly="true" />
      </NFormItem>
      <NFormItem label="备注 mark">
        <NInput v-model:value="selledForm.mark" />
      </NFormItem>
      <NFormItem label="卖出克数">
        <NInputNumber v-model:value="selledForm.count" :min="0.01" :precision="2" class="full-width" />
      </NFormItem>
      <NFormItem label="卖出单价">
        <NInputNumber v-model:value="selledForm.sell_price" :min="0.01" :precision="2" class="full-width" />
      </NFormItem>
      <div class="modal-actions">
        <NButton @click="showSelled = false">取消</NButton>
        <NButton type="primary" attr-type="submit">确认卖出</NButton>
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

.summary-card {
  background: linear-gradient(135deg, rgba(212, 168, 83, 0.08) 0%, rgba(26, 29, 35, 0.6) 100%);
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.summary-label {
  font-size: 0.95rem;
  color: #d4a853;
  font-weight: 600;
}

.summary-value {
  font-size: 1.5rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.summary-count {
  color: #d4a853;
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
