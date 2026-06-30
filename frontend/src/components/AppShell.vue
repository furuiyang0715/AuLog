<script setup>
import { ref, onMounted, provide } from "vue";
import {
  NButton,
  NLayout,
  NLayoutHeader,
  NLayoutContent,
  NSpin,
  NTabs,
  NTabPane,
  useMessage,
} from "naive-ui";
import { setUnauthorizedHandler } from "../api/client";
import { useAuth } from "../composables/useAuth";
import { useLedger } from "../composables/useLedger";
import DocPage from "./DocPage.vue";
import TPanel from "./panels/TPanel.vue";
import IngPanel from "./panels/IngPanel.vue";
import SelledPanel from "./panels/SelledPanel.vue";
import AllocPanel from "./panels/AllocPanel.vue";
import StatsPanel from "./panels/StatsPanel.vue";

const auth = useAuth();
const ledger = useLedger();
provide("ledger", ledger);

const message = useMessage();
const authLoading = ref(false);
const activeTab = ref("t");

onMounted(async () => {
  setUnauthorizedHandler(() => {
    auth.logout();
    message.warning("登录已失效，请重新登录");
  });
  await auth.bootstrap();
  if (auth.user.value) {
    await ledger.refreshAll();
  }
});

async function handleAuth(payload) {
  authLoading.value = true;
  try {
    if (payload.mode === "login") {
      await auth.login(payload.username, payload.password);
      message.success("登录成功");
    } else {
      await auth.register(payload.username, payload.password);
      message.success("注册成功");
    }
    await ledger.refreshAll();
  } catch (err) {
    message.error(err.message || "操作失败");
  } finally {
    authLoading.value = false;
  }
}

function scrollToAuth() {
  document.getElementById("auth")?.scrollIntoView({ behavior: "smooth" });
}

function logout() {
  auth.logout();
  ledger.tRecords.value = [];
  ledger.ingRecords.value = [];
  ledger.selledRecords.value = [];
  ledger.allocations.value = [];
  message.success("已退出登录");
}
</script>

<template>
  <NLayout class="app-layout">
    <NLayoutHeader bordered class="app-header">
      <div class="header-inner">
        <div>
          <h1>AuLog</h1>
          <p class="subtitle">实物金倒 T 账本</p>
        </div>
        <div v-if="auth.user.value" class="user-bar">
          <span>{{ auth.user.value.username }}</span>
          <NButton size="small" quaternary @click="logout">退出</NButton>
        </div>
        <div v-else-if="!auth.loading.value" class="user-bar">
          <NButton size="small" type="primary" @click="scrollToAuth">登录 / 注册</NButton>
        </div>
      </div>
    </NLayoutHeader>

    <NLayoutContent>
      <NSpin :show="auth.loading.value">
        <DocPage
          v-if="!auth.user.value && !auth.loading.value"
          :loading="authLoading"
          @success="handleAuth"
        />

        <template v-else-if="auth.user.value">
          <div class="content-shell">
            <NTabs v-model:value="activeTab" type="line" animated class="main-tabs">
              <NTabPane name="t" tab="倒 T">
                <div class="page-container"><TPanel /></div>
              </NTabPane>
              <NTabPane name="ing" tab="进货 ing">
                <div class="page-container"><IngPanel /></div>
              </NTabPane>
              <NTabPane name="selled" tab="反弹 selled">
                <div class="page-container"><SelledPanel /></div>
              </NTabPane>
              <NTabPane name="alloc" tab="分配记录">
                <div class="page-container"><AllocPanel /></div>
              </NTabPane>
              <NTabPane name="stats" tab="统计">
                <div class="page-container"><StatsPanel /></div>
              </NTabPane>
            </NTabs>
          </div>
        </template>
      </NSpin>
    </NLayoutContent>
  </NLayout>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: #0f1114;
}

.app-header {
  background: linear-gradient(135deg, #1a1d23 0%, #2a2418 100%);
  padding: 1.25rem 1.5rem;
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  max-width: 1100px;
  margin: 0 auto;
}

.header-inner h1 {
  margin: 0;
  font-size: 1.5rem;
  color: #d4a853;
  letter-spacing: 0.04em;
}

.subtitle {
  margin: 0.25rem 0 0;
  color: #8b929e;
  font-size: 0.875rem;
}

.user-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #8b929e;
  font-size: 0.875rem;
}

.content-shell {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 1.5rem;
  box-sizing: border-box;
}

.main-tabs {
  width: 100%;
}

.main-tabs :deep(.n-tabs-nav) {
  padding: 0;
  background: transparent;
}

.main-tabs :deep(.n-tabs-pane-wrapper) {
  width: 100%;
  overflow: visible;
}

.main-tabs :deep(.n-tab-pane) {
  width: 100%;
}

.main-tabs :deep(.n-data-table-wrapper) {
  overflow-x: visible;
}

.main-tabs :deep(.n-data-table-base-table) {
  width: 100%;
  table-layout: auto;
}

.main-tabs :deep(.n-data-table-th),
.main-tabs :deep(.n-data-table-td) {
  white-space: normal;
}
</style>
