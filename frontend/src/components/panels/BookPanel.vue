<script setup>
import { computed, h, inject, onMounted, ref, watch } from "vue";
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
  NSpace,
  useDialog,
  useMessage,
} from "naive-ui";
import BookLineChart from "../BookLineChart.vue";
import BookPieChart from "../BookPieChart.vue";
import { fmt, formatDateDisplay, toDateString } from "../../utils/format";
import { usePagination } from "../../composables/usePagination";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();
const { pagination, resetPage, watchDataLength } = usePagination(10);

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

const newProjectName = ref("");
const detailName = ref("");
const formDate = ref(startOfToday());
const formAmounts = ref({});
const savingDay = ref(false);
const renaming = ref(false);
const showDetail = ref(false);
const selectedProject = ref(null);
const showBreakdown = ref(false);
const selectedSnapshot = ref(null);

const projects = computed(() =>
  [...ledger.bookProjects.value].sort((a, b) =>
    (a.name || "").localeCompare(b.name || "", "zh")
  )
);
const snapshots = computed(() => ledger.bookSnapshots.value);
const usedProjectIds = computed(() => {
  const ids = new Set();
  for (const snap of snapshots.value) {
    for (const pid of Object.keys(snap.amounts || {})) {
      ids.add(pid);
    }
  }
  return ids;
});

watchDataLength(snapshots);

function snapshotForDay(day) {
  return snapshots.value.find((row) => row.date === day) || null;
}

function selectedDay() {
  return toDateString(formDate.value);
}

function hydrateFromSnapshot() {
  const snap = snapshotForDay(selectedDay());
  const next = {};
  for (const project of projects.value) {
    const raw = snap?.amounts?.[project.id];
    next[project.id] = raw == null || raw === "" ? 0 : Number(raw);
  }
  formAmounts.value = next;
}

function ensureProjectAmountKeys() {
  const snap = snapshotForDay(selectedDay());
  const next = { ...formAmounts.value };
  const ids = new Set(projects.value.map((p) => p.id));
  for (const project of projects.value) {
    if (next[project.id] === undefined) {
      const raw = snap?.amounts?.[project.id];
      next[project.id] = raw == null || raw === "" ? 0 : Number(raw);
    }
  }
  for (const key of Object.keys(next)) {
    if (!ids.has(key)) delete next[key];
  }
  formAmounts.value = next;
}

watch(
  projects,
  (list) => {
    ensureProjectAmountKeys();
    if (!selectedProject.value) return;
    const updated = list.find((p) => p.id === selectedProject.value.id);
    if (updated) {
      selectedProject.value = updated;
      if (!renaming.value) detailName.value = updated.name;
    } else {
      showDetail.value = false;
      selectedProject.value = null;
    }
  },
  { immediate: true }
);

watch(formDate, hydrateFromSnapshot);

const selectedInUse = computed(
  () => selectedProject.value != null && usedProjectIds.value.has(selectedProject.value.id)
);

const dayTotal = computed(() =>
  projects.value.reduce((sum, project) => {
    const value = formAmounts.value[project.id];
    return sum + (Number(value) || 0);
  }, 0)
);

const sortedSnapshots = computed(() =>
  [...snapshots.value].sort((a, b) => a.date.localeCompare(b.date))
);

const totalPoints = computed(() =>
  sortedSnapshots.value.map((row) => ({ date: row.date, value: row.total }))
);

const projectPoints = computed(() => {
  if (!selectedProject.value) return [];
  const pid = selectedProject.value.id;
  return sortedSnapshots.value.map((row) => ({
    date: row.date,
    value: Number(row.amounts?.[pid] ?? 0),
  }));
});

const projectHistoryRows = computed(() => [...projectPoints.value].reverse());

const breakdownSlices = computed(() => {
  const snap = selectedSnapshot.value;
  if (!snap) return [];
  const amounts = snap.amounts || {};
  const nameById = Object.fromEntries(projects.value.map((p) => [p.id, p.name]));
  const slices = [];
  for (const [pid, raw] of Object.entries(amounts)) {
    const amount = Number(raw);
    if (!Number.isFinite(amount) || Math.abs(amount) < 1e-9) continue;
    slices.push({
      name: nameById[pid] || "未知项目",
      amount,
      value: Math.abs(amount),
    });
  }
  slices.sort((a, b) => b.value - a.value);
  return slices;
});

async function addProject() {
  const name = newProjectName.value.trim();
  if (!name) {
    message.warning("请填写项目名称");
    return;
  }
  try {
    await ledger.createBookProject(name);
    newProjectName.value = "";
    message.success("项目已添加");
  } catch (err) {
    message.error(err.message);
  }
}

async function renameSelected() {
  const project = selectedProject.value;
  if (!project) return;
  const name = detailName.value.trim();
  if (!name) {
    message.warning("项目名称不能为空");
    detailName.value = project.name;
    return;
  }
  if (name === project.name) return;
  renaming.value = true;
  try {
    await ledger.renameBookProject(project.id, name);
    message.success("已改名");
  } catch (err) {
    detailName.value = project.name;
    message.error(err.message);
  } finally {
    renaming.value = false;
  }
}

function onDeleteSelected() {
  const project = selectedProject.value;
  if (!project) return;
  if (usedProjectIds.value.has(project.id)) {
    message.warning("该项目已有金额记录，无法删除");
    return;
  }
  dialog.warning({
    title: "确认删除",
    content: `确定删除项目「${project.name}」？`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await ledger.deleteBookProject(project.id);
        showDetail.value = false;
        selectedProject.value = null;
        message.success("已删除");
      } catch (err) {
        message.error(err.message);
      }
    },
  });
}

function openDetail(project) {
  selectedProject.value = project;
  detailName.value = project.name;
  showDetail.value = true;
}

function openBreakdown(row) {
  selectedSnapshot.value = row;
  showBreakdown.value = true;
}

async function saveDay() {
  const day = selectedDay();
  if (!day) {
    message.warning("请选择日期");
    return;
  }
  if (!projects.value.length) {
    message.warning("请先新增项目");
    return;
  }
  savingDay.value = true;
  try {
    const amounts = {};
    for (const project of projects.value) {
      amounts[project.id] = Number(formAmounts.value[project.id]) || 0;
    }
    await ledger.saveBookSnapshot(day, amounts);
    resetPage();
    message.success(`${formatDateDisplay(day)} 已保存`);
  } catch (err) {
    message.error(err.message);
  } finally {
    savingDay.value = false;
  }
}

function loadDay(row) {
  const ts = Date.parse(`${row.date}T00:00:00`);
  formDate.value = Number.isNaN(ts) ? startOfToday() : ts;
}

const snapshotColumns = [
  {
    title: "日期",
    key: "date",
    render: (r) => formatDateDisplay(r.date),
  },
  {
    title: "总资产",
    key: "total",
    render: (r) =>
      h(
        "button",
        {
          type: "button",
          class: "total-link",
          onClick: () => openBreakdown(r),
        },
        fmt(r.total)
      ),
  },
  {
    title: "操作",
    key: "actions",
    width: 120,
    render: (r) =>
      h(
        NButton,
        { size: "small", quaternary: true, type: "primary", onClick: () => loadDay(r) },
        { default: () => "载入" }
      ),
  },
];

const historyColumns = [
  { title: "日期", key: "date", render: (r) => formatDateDisplay(r.date) },
  { title: "金额", key: "value", render: (r) => fmt(r.value) },
];

onMounted(async () => {
  try {
    await ledger.refreshBook();
    hydrateFromSnapshot();
  } catch (err) {
    message.error(err.message || "加载资产账本失败");
  }
});
</script>

<template>
  <NCard title="项目管理" :bordered="false" class="section-card">
    <p class="hint-text">点击方块查看曲线、改名或删除。有过日期记录的项目不能删除。</p>
    <NSpace :wrap="true" class="add-row">
      <NInput
        v-model:value="newProjectName"
        placeholder="项目名称"
        maxlength="32"
        class="name-input"
        @keyup.enter="addProject"
      />
      <NButton type="primary" @click="addProject">新增项目</NButton>
    </NSpace>
    <div v-if="projects.length" class="project-grid">
      <button
        v-for="project in projects"
        :key="project.id"
        type="button"
        class="project-tile"
        :title="project.name"
        @click="openDetail(project)"
      >
        <span class="project-tile-name">{{ project.name }}</span>
      </button>
    </div>
    <p v-else class="hint-text empty-projects">还没有项目，先在上方添加一个。</p>
  </NCard>

  <NCard title="记录某日资产" :bordered="false" class="section-card">
    <NForm @submit.prevent="saveDay">
      <NGrid :cols="24" :x-gap="12" :y-gap="8" item-responsive responsive="screen">
        <NGridItem span="24 m:8">
          <NFormItem label="日期">
            <NDatePicker
              v-model:value="formDate"
              type="date"
              class="full-width"
              :input-readonly="true"
            />
          </NFormItem>
        </NGridItem>
        <NGridItem v-for="project in projects" :key="project.id" span="24 m:8">
          <NFormItem :label="project.name">
            <NInputNumber
              v-model:value="formAmounts[project.id]"
              :precision="2"
              class="full-width"
              placeholder="0.00"
            />
          </NFormItem>
        </NGridItem>
        <NGridItem span="24">
          <div class="day-footer">
            <div>
              <div class="summary-label">当日总资产</div>
              <div class="hint-text">未填按 0 计，可为负数（欠款）</div>
            </div>
            <div class="day-total">{{ fmt(dayTotal) }} 元</div>
          </div>
          <NButton type="primary" attr-type="submit" :loading="savingDay" :disabled="!projects.length">
            保存当日记录
          </NButton>
        </NGridItem>
      </NGrid>
    </NForm>
    <p v-if="!projects.length" class="hint-text">请先新增至少一个项目。</p>
  </NCard>

  <NCard title="总资产随日期" :bordered="false" class="section-card">
    <BookLineChart :points="totalPoints" />
  </NCard>

  <NCard title="历史记录" :bordered="false" class="section-card">
    <NDataTable
      :columns="snapshotColumns"
      :data="snapshots"
      :loading="ledger.bookLoading.value"
      :bordered="false"
      size="small"
      :pagination="pagination"
    />
  </NCard>

  <NModal
    v-model:show="showDetail"
    preset="card"
    :title="selectedProject ? `项目详情 · ${selectedProject.name}` : '项目详情'"
    style="max-width: 720px"
  >
    <NForm class="rename-row" @submit.prevent="renameSelected">
      <NInput
        v-model:value="detailName"
        maxlength="32"
        placeholder="项目名称"
        class="rename-input"
      />
      <NButton type="primary" attr-type="submit" :loading="renaming">保存名称</NButton>
    </NForm>
    <p class="hint-text">该项目在各记录日的金额；未出现的日期按 0 计。</p>
    <h4 class="chart-title">{{ selectedProject?.name }} 金额曲线</h4>
    <BookLineChart v-if="showDetail" :points="projectPoints" />
    <h4 class="chart-title">总资产随日期</h4>
    <BookLineChart v-if="showDetail" :points="totalPoints" />
    <NDataTable
      :columns="historyColumns"
      :data="projectHistoryRows"
      :bordered="false"
      size="small"
      :pagination="false"
      class="history-table"
    />
    <div class="modal-actions">
      <NButton type="error" ghost :disabled="selectedInUse" @click="onDeleteSelected">
        删除项目
      </NButton>
      <NButton @click="showDetail = false">关闭</NButton>
    </div>
  </NModal>

  <NModal
    v-model:show="showBreakdown"
    preset="card"
    :title="
      selectedSnapshot
        ? `资产构成 · ${formatDateDisplay(selectedSnapshot.date)}`
        : '资产构成'
    "
    style="max-width: 640px"
  >
    <p class="hint-text">
      总资产 {{ fmt(selectedSnapshot?.total) }} 元，仅展示金额不为 0 的项目。
    </p>
    <BookPieChart v-if="showBreakdown" :slices="breakdownSlices" />
    <div class="modal-actions">
      <NButton @click="showBreakdown = false">关闭</NButton>
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

.hint-text {
  margin: 0 0 0.75rem;
  color: #8b929e;
  font-size: 0.875rem;
}

.add-row {
  margin-bottom: 0.75rem;
}

.name-input {
  width: min(280px, 100%);
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: 0.75rem;
}

.project-tile {
  appearance: none;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem;
  border: 1px solid #2e3340;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(212, 168, 83, 0.14) 0%, rgba(26, 29, 35, 0.9) 100%);
  color: #e8eaed;
  font: inherit;
  cursor: pointer;
  text-align: center;
}

.project-tile:hover,
.project-tile:focus-visible {
  border-color: #d4a853;
  color: #d4a853;
  outline: none;
}

.project-tile-name {
  display: -webkit-box;
  overflow: hidden;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.35;
  word-break: break-all;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.empty-projects {
  margin-top: 0.25rem;
}

.rename-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.rename-input {
  flex: 1;
}

.day-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.summary-label {
  font-size: 0.95rem;
  color: #d4a853;
  font-weight: 600;
}

.day-total {
  font-size: 1.5rem;
  font-weight: 700;
  color: #d4a853;
  font-variant-numeric: tabular-nums;
}

.chart-title {
  margin: 1rem 0 0.5rem;
  font-size: 0.95rem;
  color: #c4c8cf;
  font-weight: 600;
}

.history-table {
  margin-top: 1rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}

:deep(.total-link) {
  appearance: none;
  padding: 0;
  border: none;
  background: none;
  color: #d4a853;
  font: inherit;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

:deep(.total-link:hover),
:deep(.total-link:focus-visible) {
  color: #e8c068;
  outline: none;
}
</style>
