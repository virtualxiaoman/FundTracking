<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getPortfolio } from '@/api'
import FundChartDialog from '@/components/FundChartDialog.vue'

// ============================================================
// 持仓卡片
// ============================================================
const cards = ref([])
const loading = ref(false)
const refreshing = ref(false)

const loadCards = async (force = false) => {
  loading.value = true
  try {
    const data = await getPortfolio(force)
    cards.value = data.cards || []
  } catch (e) {
    ElMessage.error('加载持仓失败：' + e.message)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const refresh = async () => {
  refreshing.value = true
  await loadCards(true)
}

// 涨跌用色：沿用涨红跌绿（国内习惯）。估值使用 status-critical(红) / status-good(绿)，
// 语义固定为“涨/跌”，与 dataviz 规范中 status 需配文字说明的要求一致。
const upColor = '#d03b3b'
const downColor = '#0ca30c'

// 估值涨跌幅（小数如 0.0125）-> 展示 +1.25%
const fmtRate = (v) => {
  if (v === null || v === undefined || isNaN(v)) return '--'
  const pct = v * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

const fmtAmount = (v) => {
  if (v === null || v === undefined) return '--'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const rateColor = (v) => {
  if (v === null || v === undefined || isNaN(v)) return ''
  if (v > 0) return upColor
  if (v < 0) return downColor
  return ''
}

const todayPct = (card) => card.estimation?.change_rate ?? null

// 今日净值展示：优先官方净值，其次实时估值
const todayDisplayNav = (card) => {
  if (card.today_nav !== null && card.today_nav !== undefined) return card.today_nav
  if (card.estimation?.estimate_nav) return card.estimation.estimate_nav
  return null
}

// 带符号金额：+1,234.56 / -56.00
const fmtSignedAmount = (v) => {
  if (v === null || v === undefined || isNaN(v)) return '--'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + fmtAmount(n)
}

// 今日估算收益 = 当前金额 × 估算涨跌幅（无金额或无估值时为 null）
const estProfitOf = (card) => {
  const pct = todayPct(card)
  const amount = card.current_amount || 0
  if (pct === null || pct === undefined || isNaN(pct) || !(amount > 0)) return null
  return amount * pct
}

// 真实收益率 = 收益金额 / 当前金额（无金额时为 null）
const realRateOf = (card) => {
  const amount = card.current_amount || 0
  if (!(amount > 0)) return null
  return (card.profit_amount || 0) / amount
}

// 估值更新时间（仅取 HH:MM，用户显然知道日期）
const estTime = (card) => {
  const t = card.estimation?.query_time
  if (!t) return null
  const m = String(t).match(/T(\d{2}:\d{2})/)
  return m ? m[1] : null
}

// ============================================================
// 历史净值曲线弹窗（复用 FundChartDialog 组件）
// ============================================================
const showChart = ref(false)
const currentCard = ref(null)

const openChart = (card) => {
  currentCard.value = card
  showChart.value = true
}

onMounted(loadCards)

const totalAmount = computed(() =>
  cards.value.reduce((s, c) => s + (c.current_amount || 0), 0)
)
const totalProfit = computed(() =>
  cards.value.reduce((s, c) => s + (c.profit_amount || 0), 0)
)

// 汇总：今日估算涨跌幅 / 估算收益（全持仓按当前金额加权，纯估算，不并入真实收益）
const estTotalRate = computed(() => {
  const weights = cards.value
    .map((c) => ({ amount: c.current_amount || 0, pct: todayPct(c) }))
    .filter((w) => w.amount > 0 && w.pct !== null && !isNaN(w.pct))
  const totalW = weights.reduce((s, w) => s + w.amount, 0)
  if (!totalW) return null
  return weights.reduce((s, w) => s + w.amount * w.pct, 0) / totalW
})
const estTotalProfit = computed(() =>
  cards.value.reduce((s, c) => s + (estProfitOf(c) ?? 0), 0)
)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="title">当前持仓</h2>
        <p class="subtitle">
          共 {{ cards.length }} 只基金 · 持仓金额 {{ fmtAmount(totalAmount) }} 元 ·
          收益 {{ fmtSignedAmount(totalProfit) }} 元
          <template v-if="estTotalRate !== null">
            · 今日估算
            <span
              class="est-inline"
              :style="{ color: rateColor(estTotalRate) }"
            >
              {{ fmtRate(estTotalRate) }}
            </span>
            / {{ fmtSignedAmount(estTotalProfit) }} 元
          </template>
        </p>
      </div>
      <el-button
        :loading="refreshing"
        :icon="Refresh"
        type="primary"
        plain
        @click="refresh"
      >
        刷新估值
      </el-button>
    </div>

    <el-skeleton :loading="loading" animated :rows="6" class="skeleton">
      <template #default>
        <div v-if="cards.length === 0" class="empty">
          <el-empty description="还没有持仓，去「持仓」页添加基金吧" />
        </div>
        <div v-else class="card-grid">
          <div
            v-for="card in cards"
            :key="card.fund_code"
            class="fund-card"
            @click="openChart(card)"
          >
            <div class="card-head">
              <span class="code">{{ card.fund_code }}</span>
              <div class="est-group">
                <span class="est-item">
                  <span class="num" :style="{ color: rateColor(todayPct(card)) }">
                    {{ fmtSignedAmount(estProfitOf(card)) }} 元
                  </span>
                </span>
                <span
                  class="est-item chip"
                  :style="{
                    color: rateColor(todayPct(card)),
                    background: rateColor(todayPct(card)) + '1a',
                  }"
                >
                  {{ fmtRate(todayPct(card)) }}
                </span>
              </div>
            </div>
            <div class="name" :title="card.fund_name">{{ card.fund_name }}</div>

            <div class="navs">
              <div class="nav-col">
                <span class="nav-label">昨日净值</span>
                <span class="nav-value">{{ card.yesterday_nav ?? '--' }}</span>
              </div>
              <div class="nav-col">
                <span class="nav-label">今日估值</span>
                <span
                  class="nav-value"
                  :style="{ color: rateColor(todayPct(card)) }"
                >
                  {{ card.estimation?.estimate_nav ?? '--' }}
                </span>
              </div>
              <div class="nav-col">
                <span class="nav-label">今日净值</span>
                <span class="nav-value">{{ todayDisplayNav(card) ?? '--' }}</span>
              </div>
            </div>

            <div class="card-foot">
              <div class="foot-row">
                <span class="hold-title">持仓</span>
                <span class="num">{{ fmtAmount(card.current_amount) }} 元</span>
                <span
                  class="num"
                  :style="{ color: (card.profit_amount || 0) >= 0 ? upColor : downColor }"
                >
                  {{ fmtSignedAmount(card.profit_amount) }} 元
                </span>
                <span class="num" :style="{ color: rateColor(realRateOf(card)) }">
                  {{ realRateOf(card) !== null ? fmtRate(realRateOf(card)) : '--' }}
                </span>
              </div>
            </div>

            <div class="update-time">估值更新 {{ estTime(card) ?? '--' }}</div>
          </div>
        </div>
      </template>
    </el-skeleton>

    <!-- 历史净值曲线弹窗（复用组件） -->
    <FundChartDialog v-model="showChart" :fund="currentCard" />
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #0b0b0b;
}
.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #52514e;
}
.est-inline {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.fund-card {
  background: #fcfcfb;
  border: 1px solid rgba(11, 11, 11, 0.10);
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.18s, transform 0.18s;
}
.fund-card:hover {
  box-shadow: 0 6px 18px rgba(11, 11, 11, 0.10);
  transform: translateY(-2px);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.code {
  font-weight: 600;
  color: #0b0b0b;
  font-size: 15px;
  letter-spacing: 0.3px;
}
.est-group {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.est-item {
  font-variant-numeric: tabular-nums;
}
.chip {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.name {
  margin-top: 6px;
  font-size: 14px;
  color: #52514e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.navs {
  display: flex;
  gap: 12px;
  margin-top: 14px;
}
.nav-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-label {
  font-size: 12px;
  color: #898781;
}
.nav-value {
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #0b0b0b;
}
.card-foot {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid #e1e0d9;
  font-size: 13px;
  color: #52514e;
}
.foot-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.hold-title {
  color: #0b0b0b;
  font-weight: 600;
}
.num {
  font-variant-numeric: tabular-nums;
}
.update-time {
  margin-top: 8px;
  font-size: 11px;
  color: #898781;
  text-align: right;
}
.skeleton {
  margin-top: 8px;
}
.empty {
  background: #fcfcfb;
  border: 1px dashed #c3c2b7;
  border-radius: 10px;
}
</style>
