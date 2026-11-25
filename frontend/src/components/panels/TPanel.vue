<script setup>
import { computed, h, inject, onMounted, ref } from "vue";
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
  NSwitch,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import { fmt, fmtQty, formatDateDisplay, gainType, parseLegacyDate, statusMap, toDateTimeString, compareLegacyDate } from "../../utils/format";

const COUNT_EPS = 1e-6;
import {
  firstValidationError,
  syncTradeAmounts,
  validatePriceCountAmount,
} from "../../utils/tradeAmount";
import { usePagination } from "../../composables/usePagination";
import { useGoldPrice } from "../../composables/useGoldPrice";
import { rowTintClassName, tRecordRowTint } from "../../utils/recordRowTint";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();
const { pagination, resetPage, watchDataLength } = usePagination(10);
const { goldLoading, currentGold, loadGoldPrice } = useGoldPrice();

const onlyUnclosed = ref(false);
const onlySettleable = ref(false);

const tableRecords = computed(() => {
  let rows = ledger.tRecords.value;
  if (onlyUnclosed.value) {
    rows = rows.filter((r) => r.status !== "CLOSED");
  }
  if (onlySettleable.value) {
    const gold = currentGold.value;
    if (gold == null) return [];
    rows = rows.filter(
      (r) => Number(r.remaining_count) > 0 && Number(r.price) + 1e-9 >= gold
    );
  }
  return rows;
});

async function toggleSettleable() {
  if (onlySettleable.value) {
    onlySettleable.value = false;
    resetPage();
    return;
  }
  try {
    const gold = await loadGoldPrice(true);
    if (gold == null) {
      message.warning("暂无金价，无法筛选可结算项目");
      return;
    }
    onlySettleable.value = true;
    resetPage();
  } catch (err) {
    message.error(err.message || "获取金价失败");
  }
}

watchDataLength(tableRecords);

const tRealizedGainTotal = computed(() =>
  ledger.tRecords.value.reduce((sum, r) => sum + (Number(r.gain) || 0), 0)
);

const buybackRemainingTotal = computed(() =>
  ledger.tRecords.value
    .filter((r) => r.status !== "CLOSED")
    .reduce((sum, r) => sum + (Number(r.remaining_count) || 0), 0)
);

const form = ref({
  mark: "",
  price: null,
  count: null,
  pop_amount: null,
  sold_at: Date.now(),
});

const showEdit = ref(false);
const editingId = ref(null);
const showLinkedIng = ref(false);
const selectedT = ref(null);
const editForm = ref({
  mark: "",
  price: null,
  count: null,
  pop_amount: null,
  sold_at: null,
  allocated_count: 0,
});

function tMatchAllocations(tId) {
  return ledger.allocations.value.filter(
    (a) => a.target_type === "T_MATCH" && a.target_id === tId
  );
}

function buildLinkedRows(t) {
  const sellPrice = Number(t.price) || 0;
  return tMatchAllocations(t.id).map((alloc) => {
    const ing = ledger.ingRecords.value.find((i) => i.id === alloc.ing_id);
    const buyPrice = ing != null ? Number(ing.price) : null;
    return {
      ingDate: ing?.date,
      ingMark: ing?.mark || "—",
      buyPrice,
      matchCount: alloc.count,
      matchAmount: alloc.amount,
      priceDiff: buyPrice != null ? sellPrice - buyPrice : null,
    };
  });
}

const linkedRows = computed(() => (selectedT.value ? buildLinkedRows(selectedT.value) : []));

const linkedSummary = computed(() => {
  const rows = linkedRows.value;
  const totalCount = rows.reduce((sum, row) => sum + (Number(row.matchCount) || 0), 0);
  const totalAmount = rows.reduce((sum, row) => sum + (Number(row.matchAmount) || 0), 0);
  const sellPrice = Number(selectedT.value?.price) || 0;
  return {
    totalCount,
    totalAmount,
    gain: totalCount * sellPrice - totalAmount,
  };
});

const linkedModalTitle = computed(() => {
  if (!selectedT.value) return "配对进货";
  const name =
    selectedT.value.mark ||
    formatDateDisplay(selectedT.value.sold_at) ||
    `${fmt(selectedT.value.count)} 克`;
  return `配对进货 · ${name}`;
});

function openLinkedIng(record) {
  selectedT.value = record;
  showLinkedIng.value = true;
}

function renderMark(r) {
  const matchCount = tMatchAllocations(r.id).length;
  const label = r.mark || "—";
  return h(
    "button",
    {
      type: "button",
      class: ["mark-link", matchCount > 0 ? "mark-link-active" : "mark-link-muted"],
      onClick: () => openLinkedIng(r),
    },
    [
      label,
      matchCount > 0 ? h("span", { class: "mark-badge" }, ` (${matchCount})`) : null,
    ]
  );
}

function renderPriceDiff(row) {
  if (row.priceDiff == null) return "—";
  const type = gainType(row.priceDiff);
  return h(
    "span",
    { class: type === "success" ? "gain-positive" : type === "error" ? "gain-negative" : "" },
    fmt(row.priceDiff)
  );
}

const linkedColumns = [
  { title: "进货日期", key: "ingDate", minWidth: 168, render: (r) => formatDateDisplay(r.ingDate) },
  { title: "备注", key: "ingMark" },
  { title: "买入价", key: "buyPrice", render: (r) => fmt(r.buyPrice) },
  { title: "配对克数", key: "matchCount", render: (r) => fmt(r.matchCount) },
  { title: "买回成本", key: "matchAmount", render: (r) => fmt(r.matchAmount) },
  { title: "价差/克", key: "priceDiff", render: renderPriceDiff },
];

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
  { title: "备注", key: "mark", render: renderMark },
  {
    title: "卖出日期",
    key: "sold_at",
    minWidth: 168,
    sorter: (a, b) => compareLegacyDate(a.sold_at, b.sold_at),
    defaultSortOrder: "descend",
    render: (r) => formatDateDisplay(r.sold_at),
  },
  { title: "克数", key: "count", render: (r) => fmtQty(r.count) },
  { title: "回笼", key: "pop_amount", render: (r) => fmt(r.pop_amount) },
  {
    title: "卖价",
    key: "price",
    sorter: (a, b) => Number(a.price) - Number(b.price),
    render: (r) => fmtQty(r.price),
  },
  { title: "买回成本", key: "push_amount", render: (r) => fmt(r.push_amount) },
  { title: "套利 gain", key: "gain", render: renderGain },
  {
    title: "已配/剩余",
    key: "allocated",
    render: (r) => `${fmtQty(r.allocated_count)} / ${fmtQty(r.remaining_count)}`,
  },
  { title: "状态", key: "status", render: (r) => hStatus(r.status) },
  { title: "操作", key: "actions", width: 120, render: actionButtons },
];

function hasPositive(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0;
}

function onFormPriceChange() {
  syncTradeAmounts(form.value, "price", "pop_amount");
}

function onFormCountChange() {
  syncTradeAmounts(form.value, "count", "pop_amount");
}

function onFormPopChange() {
  syncTradeAmounts(form.value, "amount", "pop_amount");
}

function onEditPriceChange() {
  syncTradeAmounts(editForm.value, "price", "pop_amount");
}

function onEditCountChange() {
  syncTradeAmounts(editForm.value, "count", "pop_amount");
}

function onEditPopChange() {
  syncTradeAmounts(editForm.value, "amount", "pop_amount");
}

function ensureTTradeFields(state) {
  if (!hasPositive(state.count)) {
    message.warning("请填写克数");
    return false;
  }
  if (!hasPositive(state.price) && !hasPositive(state.pop_amount)) {
    message.warning("请填写单价或回笼金额");
    return false;
  }
  if (hasPositive(state.price)) {
    syncTradeAmounts(state, "price", "pop_amount");
  } else {
    syncTradeAmounts(state, "amount", "pop_amount");
  }
  return true;
}

async function submit() {
  if (!ensureTTradeFields(form.value)) return;
  const check = validatePriceCountAmount({
    price: form.value.price,
    count: form.value.count,
    amount: form.value.pop_amount,
    requireTotal: false,
  });
  if (!check.ok) {
    message.warning(firstValidationError(check));
    return;
  }
  try {
    await ledger.createT({
      mark: form.value.mark,
      count: form.value.count,
      pop_amount: check.expectedAmount,
      sold_at: form.value.sold_at ? toDateTimeString(form.value.sold_at) : null,
    });
    form.value = { mark: "", price: null, count: null, pop_amount: null, sold_at: Date.now() };
    message.success("倒 T 记录已添加");
  } catch (err) {
    message.error(err.message);
  }
}

function openEdit(record) {
  editingId.value = record.id;
  editForm.value = {
    mark: record.mark || "",
    price: record.price,
    count: record.count,
    pop_amount: record.pop_amount,
    sold_at: parseLegacyDate(record.sold_at),
    allocated_count: record.allocated_count || 0,
  };
  showEdit.value = true;
}

async function submitEdit() {
  if (!ensureTTradeFields(editForm.value)) return;
  const check = validatePriceCountAmount({
    price: editForm.value.price,
    count: editForm.value.count,
    amount: editForm.value.pop_amount,
    requireTotal: false,
  });
  if (!check.ok) {
    message.warning(firstValidationError(check));
    return;
  }
  if (editForm.value.count + COUNT_EPS < editForm.value.allocated_count) {
    message.warning(`克数不能小于已配对克数 ${fmt(editForm.value.allocated_count)} 克`);
    return;
  }
  try {
    await ledger.updateT(editingId.value, {
      mark: editForm.value.mark,
      count: editForm.value.count,
      pop_amount: check.expectedAmount,
      sold_at: editForm.value.sold_at ? toDateTimeString(editForm.value.sold_at) : null,
    });
    showEdit.value = false;
    message.success("已保存");
  } catch (err) {
    message.error(err.message);
  }
}

function tRowClassName(row) {
  return rowTintClassName(tRecordRowTint(row, currentGold.value));
}

onMounted(() => {
  if (currentGold.value == null) loadGoldPrice();
});

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
          <NFormItem label="单价（元/克）">
            <NInputNumber
              v-model:value="form.price"
              :min="0.0001"
              :precision="4"
              class="full-width"
              @update:value="onFormPriceChange"
            />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="克数 count" required>
            <NInputNumber
              v-model:value="form.count"
              :min="0.0001"
              :precision="4"
              class="full-width"
              @update:value="onFormCountChange"
            />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="回笼金额 pop_amount">
            <NInputNumber
              v-model:value="form.pop_amount"
              :min="0.01"
              :precision="2"
              class="full-width"
              placeholder="与单价二选一填写，自动互算"
              @update:value="onFormPopChange"
            />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24 m:8">
          <NFormItem label="卖出日期">
            <NDatePicker
              v-model:value="form.sold_at"
              type="datetime"
              format="yyyy-MM-dd HH:mm:ss"
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

  <NCard :bordered="false" class="section-card summary-card">
    <div class="summary-row">
      <div>
        <div class="summary-label">倒 T 已实现获利</div>
        <div class="hint-text">含部分配对与已闭环的 gain 之和</div>
      </div>
      <div class="summary-value" :class="gainType(tRealizedGainTotal) === 'success' ? 'gain-positive' : gainType(tRealizedGainTotal) === 'error' ? 'gain-negative' : ''">
        {{ fmt(tRealizedGainTotal) }}
      </div>
    </div>
  </NCard>

  <NCard :bordered="false" class="section-card summary-card">
    <div class="summary-row">
      <div>
        <div class="summary-label">当前可买入总克数</div>
        <div class="hint-text">所有未闭环倒 T 的剩余克数之和（待买回）</div>
      </div>
      <div class="summary-value summary-count">{{ fmtQty(buybackRemainingTotal) }}</div>
    </div>
  </NCard>

  <NCard title="倒 T 列表" :bordered="false" class="section-card">
    <template #header-extra>
      <div class="list-filters">
        <label class="list-filter">
          <NSwitch v-model:value="onlyUnclosed" size="small" @update:value="resetPage" />
          <span>仅看未闭环</span>
        </label>
        <NButton
          size="small"
          :type="onlySettleable ? 'primary' : 'default'"
          :loading="goldLoading"
          @click="toggleSettleable"
        >
          当前可结算
        </NButton>
        <span v-if="onlySettleable && currentGold != null" class="filter-price">
          现价 {{ fmt(currentGold) }}
        </span>
      </div>
    </template>
    <p class="hint-text row-tint-legend">
      <span class="legend-swatch row-tint-closed-sample" />已闭合
      <span class="legend-swatch row-tint-profit-sample" />现价浮盈（含持平）
      <span class="legend-swatch row-tint-loss-sample" />现价浮亏
      <template v-if="currentGold != null"> · 现价 {{ fmt(currentGold) }} 元/克</template>
    </p>
    <NDataTable
      :columns="columns"
      :data="tableRecords"
      :loading="ledger.loading.value"
      :bordered="false"
      size="small"
      :pagination="pagination"
      :row-class-name="tRowClassName"
      @update:sorter="resetPage"
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
      <NFormItem label="单价（元/克）">
        <NInputNumber
          v-model:value="editForm.price"
          :min="0.0001"
          :precision="4"
          class="full-width"
          @update:value="onEditPriceChange"
        />
      </NFormItem>
      <NFormItem label="克数 count" required>
        <NInputNumber
          v-model:value="editForm.count"
          :min="editForm.allocated_count || 0.0001"
          :precision="4"
          class="full-width"
          @update:value="onEditCountChange"
        />
      </NFormItem>
      <NFormItem label="回笼金额 pop_amount">
        <NInputNumber
          v-model:value="editForm.pop_amount"
          :min="0.01"
          :precision="2"
          class="full-width"
          placeholder="与单价二选一填写，自动互算"
          @update:value="onEditPopChange"
        />
      </NFormItem>
      <NFormItem label="卖出日期">
        <NDatePicker
          v-model:value="editForm.sold_at"
          type="datetime"
          format="yyyy-MM-dd HH:mm:ss"
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

  <NModal
    v-model:show="showLinkedIng"
    preset="card"
    :title="linkedModalTitle"
    style="max-width: 640px"
  >
    <p v-if="selectedT" class="hint-text linked-subtitle">
      已配 {{ fmt(selectedT.allocated_count) }} 克 / 共 {{ fmt(selectedT.count) }} 克 · 卖价
      {{ fmt(selectedT.price) }}
    </p>

    <template v-if="linkedRows.length">
      <NDataTable
        :columns="linkedColumns"
        :data="linkedRows"
        :bordered="false"
        size="small"
        :pagination="false"
      />
      <p class="hint-text linked-total">
        合计：配对 {{ fmt(linkedSummary.totalCount) }} 克 · 买回成本
        {{ fmt(linkedSummary.totalAmount) }} · 套利
        <span :class="gainType(linkedSummary.gain) === 'success' ? 'gain-positive' : gainType(linkedSummary.gain) === 'error' ? 'gain-negative' : ''">{{ fmt(linkedSummary.gain) }}</span>
        元
      </p>
    </template>
    <template v-else>
      <p class="linked-empty">尚未配对进货</p>
      <p class="hint-text">可在「进货 ing」中对低价货源操作「配对倒T」。</p>
    </template>

    <div class="modal-actions">
      <NButton @click="showLinkedIng = false">关闭</NButton>
    </div>
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

.mark-link {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.mark-link-active {
  color: #d4a853;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.mark-link-active:hover {
  color: #e8c068;
}

.mark-link-muted {
  color: #8b929e;
  text-decoration: underline;
  text-decoration-style: dashed;
  text-underline-offset: 2px;
}

.mark-link-muted:hover {
  color: #a8aeb8;
}

.mark-badge {
  font-size: 0.85em;
  opacity: 0.85;
}

.linked-subtitle {
  margin: 0 0 1rem;
}

.linked-total {
  margin: 0.75rem 0 0;
}

.linked-empty {
  margin: 0 0 0.35rem;
  color: #c9cdd4;
}

.list-filters {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.list-filter {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: #8b929e;
  cursor: pointer;
  user-select: none;
}

.filter-price {
  font-size: 0.8125rem;
  color: #d4a853;
  font-variant-numeric: tabular-nums;
}

</style>
