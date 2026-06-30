<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { NButton, NCard, NSpin, useMessage } from "naive-ui";
import { api } from "../../api/client";
import { fmt, gainType } from "../../utils/format";

const ledger = inject("ledger");
const message = useMessage();

const goldLoading = ref(false);
const goldPrice = ref(null);

const tGainClosed = computed(() =>
  ledger.tRecords.value
    .filter((r) => r.status === "CLOSED")
    .reduce((sum, r) => sum + (Number(r.gain) || 0), 0)
);

const selledGain = computed(() =>
  ledger.selledRecords.value.reduce((sum, r) => sum + (Number(r.gain) || 0), 0)
);

const totalGain = computed(() => tGainClosed.value + selledGain.value);

const currentGold = computed(() => {
  const price = goldPrice.value?.price;
  if (price == null || price === "") return null;
  return Number(price);
});

const expectedBuybackGain = computed(() => {
  const gold = currentGold.value;
  if (gold == null) return null;
  return round2(
    ledger.tRecords.value
      .filter((r) => r.status !== "CLOSED" && Number(r.remaining_count) > 0)
      .reduce((sum, r) => {
        const sellPrice = Number(r.price) || 0;
        const remaining = Number(r.remaining_count) || 0;
        return sum + (sellPrice - gold) * remaining;
      }, 0)
  );
});

const expectedSellGain = computed(() => {
  const gold = currentGold.value;
  if (gold == null) return null;
  return round2(
    ledger.ingRecords.value
      .filter((r) => Number(r.remaining_count) > 0)
      .reduce((sum, r) => {
        const buyPrice = Number(r.price) || 0;
        const remaining = Number(r.remaining_count) || 0;
        return sum + (gold - buyPrice) * remaining;
      }, 0)
  );
});

const expectedNetDiff = computed(() => {
  if (expectedBuybackGain.value == null || expectedSellGain.value == null) return null;
  return round2(expectedBuybackGain.value + expectedSellGain.value);
});

function round2(value) {
  return Math.round(value * 100) / 100;
}

function fmtEstimate(value) {
  if (value == null) return "—";
  return fmt(value);
}

function gainClass(value) {
  const type = gainType(value);
  if (type === "success") return "gain-positive";
  if (type === "error") return "gain-negative";
  return "";
}

async function loadGoldPrice(force = false) {
  goldLoading.value = true;
  try {
    const query = force ? "?refresh=1" : "";
    goldPrice.value = await api(`/stats/gold-price${query}`);
  } catch (err) {
    message.error(err.message || "获取金价失败");
  } finally {
    goldLoading.value = false;
  }
}

onMounted(() => {
  loadGoldPrice();
});
</script>

<template>
  <NCard title="获利统计" :bordered="false" class="section-card">
    <div class="stats-grid">
      <div class="stat-item summary-card">
        <div class="summary-label">倒 T 获利（已闭环）</div>
        <div class="hint-text">与倒 T 页「已闭环套利合计」一致</div>
        <div class="summary-value" :class="gainClass(tGainClosed)">{{ fmt(tGainClosed) }}</div>
      </div>
      <div class="stat-item summary-card">
        <div class="summary-label">反弹卖出获利</div>
        <div class="hint-text">与反弹 selled 页「反弹获利合计」一致</div>
        <div class="summary-value" :class="gainClass(selledGain)">{{ fmt(selledGain) }}</div>
      </div>
      <div class="stat-item summary-card stat-item-total">
        <div class="summary-label">获利总和</div>
        <div class="hint-text">倒 T 已闭环 + 反弹卖出</div>
        <div class="summary-value" :class="gainClass(totalGain)">{{ fmt(totalGain) }}</div>
      </div>
    </div>
  </NCard>

  <NCard title="当前金价" :bordered="false" class="section-card">
    <template #header-extra>
      <NButton size="small" quaternary :loading="goldLoading" @click="loadGoldPrice(true)">
        刷新
      </NButton>
    </template>

    <NSpin :show="goldLoading && !goldPrice">
      <div v-if="goldPrice" class="gold-panel summary-card">
        <div>
          <div class="summary-label">{{ goldPrice.label }}</div>
          <div class="hint-text">京东金融浙商积存金 · 元/克</div>
        </div>
        <div class="gold-price">{{ fmt(goldPrice.price) }}</div>
      </div>
      <div v-if="goldPrice?.change_amount != null" class="gold-meta">
        <span>较昨收</span>
        <span :class="gainClass(goldPrice.change_amount)">
          {{ goldPrice.change_amount >= 0 ? "+" : "" }}{{ fmt(goldPrice.change_amount) }}
        </span>
        <span v-if="goldPrice.change_rate" :class="gainClass(goldPrice.change_amount)">
          ({{ goldPrice.change_rate }})
        </span>
      </div>
      <p v-if="goldPrice?.updated_at" class="hint-text updated-at">
        更新于 {{ new Date(goldPrice.updated_at).toLocaleString("zh-CN") }}
      </p>
      <p v-else-if="!goldLoading" class="hint-text">暂无金价数据</p>
    </NSpin>
  </NCard>

  <NCard title="现价预估" :bordered="false" class="section-card">
    <p class="hint-text estimate-intro">
      按上方当前金价估算：若未闭合倒 T 现在买回、未分配进货现在卖出，各自的浮动盈亏（可为负，作操作参考）。
    </p>
    <div class="stats-grid">
      <div class="stat-item summary-card">
        <div class="summary-label">预计买回收益（倒 T 未闭合）</div>
        <div class="hint-text">Σ (T 卖出价 − 现价) × 剩余克数</div>
        <div class="summary-value" :class="gainClass(expectedBuybackGain)">
          {{ fmtEstimate(expectedBuybackGain) }}
        </div>
      </div>
      <div class="stat-item summary-card">
        <div class="summary-label">预计卖出收益（进货未分配）</div>
        <div class="hint-text">Σ (现价 − 进货价) × 剩余克数</div>
        <div class="summary-value" :class="gainClass(expectedSellGain)">
          {{ fmtEstimate(expectedSellGain) }}
        </div>
      </div>
      <div class="stat-item summary-card stat-item-total">
        <div class="summary-label">预估净差</div>
        <div class="hint-text">上述两项相加 · 两边均按现价操作的浮动盈亏</div>
        <div class="summary-value" :class="gainClass(expectedNetDiff)">
          {{ fmtEstimate(expectedNetDiff) }}
        </div>
      </div>
    </div>
  </NCard>
</template>

<style scoped>
.section-card {
  margin-bottom: 1rem;
}

.summary-card {
  background: linear-gradient(135deg, rgba(212, 168, 83, 0.08) 0%, rgba(26, 29, 35, 0.6) 100%);
  border-radius: 8px;
  padding: 1rem 1.25rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.stat-item-total {
  border: 1px solid rgba(212, 168, 83, 0.25);
}

.summary-label {
  font-size: 0.95rem;
  color: #d4a853;
  font-weight: 600;
}

.summary-value {
  margin-top: 0.25rem;
  font-size: 1.5rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.gold-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.gold-price {
  font-size: 2rem;
  font-weight: 700;
  color: #d4a853;
  font-variant-numeric: tabular-nums;
}

.gold-meta {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #8b929e;
}

.updated-at {
  margin-top: 0.5rem;
}

.estimate-intro {
  margin: 0 0 1rem;
}
</style>
