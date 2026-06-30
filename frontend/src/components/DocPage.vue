<script setup>
import { NAnchor, NAnchorLink, NCard, NDivider, NTable, NTag } from "naive-ui";
import AuthScreen from "./AuthScreen.vue";

defineProps({
  loading: { type: Boolean, default: false },
});

defineEmits(["success"]);

const sheetRows = [
  { sheet: "倒 T", role: "先卖出实物金，等待低价买回完成闭环", status: "待买回 / 部分配对 / 已闭环" },
  { sheet: "进货 ing", role: "低价买入的货源池，用于配对倒 T 或反弹卖出", status: "未分配 / 部分分配 / 已分完" },
  { sheet: "反弹 selled", role: "从 ing 发起的反弹卖出，记录实际成交", status: "—" },
  { sheet: "分配记录", role: "ing 克数 → 倒 T 或 selled 的关联明细", status: "—" },
];

const exampleT = [
  { step: "1", action: "倒 T 卖出", detail: "10 克，回笼 8,800 元 → 卖价 880 元/克" },
  { step: "2", action: "ing 进货", detail: "10 克，单价 860 元 → 成本 8,600 元" },
  { step: "3", action: "配对倒 T", detail: "从 ing 分配 10 克给该倒 T" },
  { step: "4", action: "闭环结果", detail: "gain = 8,800 − 8,600 = 200 元" },
];

const exampleSelled = [
  { step: "1", action: "ing 进货", detail: "5 克，单价 850 元" },
  { step: "2", action: "反弹卖出", detail: "5 克 × 870 元/克 = 4,350 元" },
  { step: "3", action: "获利", detail: "gain = 4,350 − 4,250 = 100 元" },
];
</script>

<template>
  <div class="doc-page">
    <div class="doc-layout">
      <aside class="doc-nav">
        <NAnchor :bound="80" ignore-gap class="doc-anchor">
          <NAnchorLink title="概述" href="#overview" />
          <NAnchorLink title="设计思路" href="#design" />
          <NAnchorLink title="账本结构" href="#sheets" />
          <NAnchorLink title="获利计算" href="#gain" />
          <NAnchorLink title="使用样例" href="#examples" />
          <NAnchorLink title="统计页" href="#stats" />
          <NAnchorLink title="登录使用" href="#auth" />
        </NAnchor>
      </aside>

      <main class="doc-main">
        <section id="overview" class="doc-section">
          <h2>概述</h2>
          <p>
            <strong>AuLog</strong> 是为<strong>实物金「倒 T」</strong>设计的个人账本：先在高价卖出，再在低价买回完成套利；
            同时管理<strong>进货货源</strong>与<strong>反弹卖出</strong>，并用分配记录把每一笔克数关联起来。
          </p>
          <p class="hint-text">
            适用场景：京东/银行积存金等可反复买卖、需要清楚记录「卖了哪笔、用哪批货买回」的投资者。
          </p>
        </section>

        <section id="design" class="doc-section">
          <h2>设计思路</h2>

          <h3>1. 倒 T 与进货分离</h3>
          <p>
            <strong>倒 T</strong>只记录「卖出腿」：克数、回笼金额、卖出日期。买回不直接填在倒 T 里，而是通过
            <strong>进货 ing</strong> 录入实际买入，再用「配对」把 ing 克数挂到倒 T 上。这样一笔卖出可以分多次、用多批进货买回。
          </p>

          <h3>2. 分配是关联纽带</h3>
          <p>
            每次从 ing 划克数给倒 T（或发起反弹卖出），系统生成一条<strong>分配记录</strong>。倒 T 列表点备注可查看配对了哪些进货；
            分配页可审计、撤销（撤销反弹会一并删除 selled）。
          </p>

          <h3>3. 不接受亏损配对</h3>
          <p>
            配对时要求 <strong>倒 T 卖价 ≥ ing 买入价</strong>。避免「高买低卖式闭环」把亏损伪装成已平仓。未达条件的配对会被拒绝。
          </p>

          <h3>4. 两种获利路径</h3>
          <ul>
            <li><strong>倒 T 闭环</strong>：卖价 − 买回成本，状态变为「已闭环」后计入已实现 gain。</li>
            <li><strong>反弹卖出</strong>：从 ing 直接按更高价卖出，不经过倒 T 抵消，单独记 selled gain。</li>
          </ul>

          <h3>5. 统计页：已实现 + 现价预估</h3>
          <p>
            已实现获利只看落袋部分；「现价预估」用当前浙商金价估算未闭合倒 T、未分配 ing 若现在操作会怎样——作方向参考，不是精确结算。
          </p>
        </section>

        <section id="sheets" class="doc-section">
          <h2>账本结构</h2>
          <NTable :bordered="false" size="small" :single-line="false">
            <thead>
              <tr>
                <th>模块</th>
                <th>作用</th>
                <th>典型状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sheetRows" :key="row.sheet">
                <td><strong>{{ row.sheet }}</strong></td>
                <td>{{ row.role }}</td>
                <td>{{ row.status }}</td>
              </tr>
            </tbody>
          </NTable>
        </section>

        <section id="gain" class="doc-section">
          <h2>获利计算</h2>

          <NCard size="small" :bordered="false" class="doc-card">
            <div class="formula-title">倒 T（部分配对）</div>
            <code>gain = 已配克数 × 卖价 − 已配买回成本</code>
          </NCard>

          <NCard size="small" :bordered="false" class="doc-card">
            <div class="formula-title">倒 T（已闭环）</div>
            <code>gain = 回笼金额 pop_amount − 买回成本 push_amount</code>
          </NCard>

          <NCard size="small" :bordered="false" class="doc-card">
            <div class="formula-title">反弹 selled</div>
            <code>gain = 卖出额 − 买入额</code>
          </NCard>

          <p class="hint-text">
            卖价 = pop_amount ÷ 克数；买回成本来自分配时 ing 单价 × 配对克数之和。
          </p>
        </section>

        <section id="examples" class="doc-section">
          <h2>使用样例</h2>

          <h3>样例 A：完整倒 T 闭环</h3>
          <p>金价在高位先卖 10 克，回落后用一批 ing 全部买回。</p>
          <NTable :bordered="false" size="small" :single-line="false">
            <thead>
              <tr>
                <th>步骤</th>
                <th>操作</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in exampleT" :key="row.step">
                <td>{{ row.step }}</td>
                <td>{{ row.action }}</td>
                <td>{{ row.detail }}</td>
              </tr>
            </tbody>
          </NTable>

          <h3>样例 B：反弹卖出（不经过倒 T）</h3>
          <p>低位 ing 尚未配对倒 T，金价反弹后直接卖出。</p>
          <NTable :bordered="false" size="small" :single-line="false">
            <thead>
              <tr>
                <th>步骤</th>
                <th>操作</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in exampleSelled" :key="row.step">
                <td>{{ row.step }}</td>
                <td>{{ row.action }}</td>
                <td>{{ row.detail }}</td>
              </tr>
            </tbody>
          </NTable>

          <h3>样例 C：部分配对</h3>
          <p>
            倒 T 卖出 20 克，先配 8 克 ing → 状态「部分配对」，gain 只算已配 8 克；
            剩余 12 克待更低 ing 或价格合适时再配。全部配满后变为「已闭环」。
          </p>

          <h3>推荐操作顺序</h3>
          <ol class="doc-steps">
            <li>在<strong>倒 T</strong>录入卖出记录</li>
            <li>在<strong>进货 ing</strong>录入买回（或囤货）记录</li>
            <li>在 ing 行点击<strong>配对倒T</strong>，选择卖价 ≥ 进货价的倒 T</li>
            <li>若 ing 想直接卖反弹，用<strong>反弹卖出</strong>（与倒 T 配对是两条独立路径，注意克数不要重复分配）</li>
            <li>在<strong>统计</strong>查看已实现获利与现价预估</li>
          </ol>
        </section>

        <section id="stats" class="doc-section">
          <h2>统计页说明</h2>
          <ul>
            <li>
              <strong>倒 T 获利（已闭环）</strong>：仅 CLOSED 记录的 gain 之和
            </li>
            <li>
              <strong>反弹卖出获利</strong>：全部 selled 的 gain 之和
            </li>
            <li>
              <strong>预计买回收益</strong>：Σ (T 卖价 − 现价) × 未闭合剩余克数
              <NTag size="small" :bordered="false" type="info">买回参考</NTag>
            </li>
            <li>
              <strong>预计卖出收益</strong>：Σ (现价 − ing 价) × 未分配克数
              <NTag size="small" :bordered="false" type="warning">卖出参考</NTag>
            </li>
            <li>
              <strong>预估净差</strong>：上述两项相加，表示若按当前金价同时「买回未闭合 + 卖掉未分配」的浮动合计
            </li>
          </ul>
        </section>

        <NDivider />

        <section id="auth" class="doc-section auth-section">
          <h2>登录使用</h2>
          <p class="hint-text">每位用户数据独立隔离，登录后即可录入自己的账本。</p>
          <AuthScreen :loading="loading" @success="$emit('success', $event)" />
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.doc-page {
  padding: 1.5rem 1.5rem 3rem;
}

.doc-layout {
  display: flex;
  gap: 2rem;
  max-width: 1100px;
  margin: 0 auto;
  align-items: flex-start;
}

.doc-nav {
  position: sticky;
  top: 5rem;
  flex: 0 0 140px;
  display: none;
}

@media (min-width: 900px) {
  .doc-nav {
    display: block;
  }
}

.doc-main {
  flex: 1;
  min-width: 0;
  color: #c4c8cf;
  line-height: 1.65;
}

.doc-section {
  margin-bottom: 2.5rem;
  scroll-margin-top: 5rem;
}

.doc-section h2 {
  margin: 0 0 1rem;
  font-size: 1.35rem;
  color: #d4a853;
  font-weight: 600;
}

.doc-section h3 {
  margin: 1.25rem 0 0.5rem;
  font-size: 1.05rem;
  color: #e8eaed;
}

.doc-section p {
  margin: 0 0 0.75rem;
}

.doc-section ul,
.doc-section ol {
  margin: 0.5rem 0 0.75rem;
  padding-left: 1.25rem;
}

.doc-section li {
  margin-bottom: 0.35rem;
}

.doc-section li strong {
  color: #e8eaed;
}

.doc-card {
  margin-bottom: 0.75rem;
  background: rgba(212, 168, 83, 0.06);
}

.formula-title {
  font-size: 0.85rem;
  color: #8b929e;
  margin-bottom: 0.35rem;
}

.doc-card code {
  display: block;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 0.9rem;
  color: #e8eaed;
  word-break: break-all;
}

.doc-steps li {
  margin-bottom: 0.5rem;
}

.auth-section :deep(.auth-screen) {
  padding: 0;
  justify-content: flex-start;
}

.auth-section :deep(.auth-card) {
  max-width: 420px;
}
</style>
