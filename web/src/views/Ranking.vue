<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getRanking } from '@/api'
import FundChartDialog from '@/components/FundChartDialog.vue'

// 涨跌用色：涨红跌绿（国内习惯）
const upColor = '#d03b3b'
const downColor = '#0ca30c'

// 时间范围
const ranges = [
  { value: '1D', label: '今日' },
  { value: '1W', label: '近1周' },
  { value: '1M', label: '近1月' },
  { value: '3M', label: '近3月' },
  { value: '1Y', label: '近1年' },
  { value: '3Y', label: '近3年' },
  { value: '5Y', label: '近5年' },
  { value: 'ALL', label: '全部' },
]
const currentRange = ref('1W')

// 排序方式：desc=涨幅从高到低(默认), asc=跌幅从高到低
const sortMode = ref('desc')
const sortDesc = () => sortMode.value === 'desc'

const rows = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = 50

const loadRanking = async () => {
  loading.value = true
  try {
    const data = await getRanking(currentRange.value, sortMode.value, currentPage.value, pageSize)
    rows.value = data.results || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error('加载排名失败：' + e.message)
  } finally {
    loading.value = false
  }
}

const onRangeChange = async (r) => {
  currentRange.value = r
  currentPage.value = 1
  await loadRanking()
}

const onSortChange = async (d) => {
  sortMode.value = d ? 'desc' : 'asc'
  currentPage.value = 1
  await loadRanking()
}

const onPageChange = async (p) => {
  currentPage.value = p
  await loadRanking()
}

// 涨跌幅（小数）-> 展示 +1.25%
const fmtRate = (v) => {
  if (v === null || v === undefined || isNaN(v)) return '--'
  const pct = v * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

const rateColor = (v) => {
  if (v === null || v === undefined || isNaN(v)) return ''
  if (v > 0) return upColor
  if (v < 0) return downColor
  return ''
}

// 点击行弹出历史曲线
const showChart = ref(false)
const currentFund = ref(null)
const openChart = (row) => {
  currentFund.value = { fund_code: row.fund_code, fund_name: row.fund_name }
  showChart.value = true
}

onMounted(loadRanking)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="title">全部基金排行</h2>
        <p class="subtitle">
          共 {{ total }} 只基金有
          {{ currentRange === 'TODAY' ? '今日' : currentRange === '1W' ? '近1周' : currentRange === '1M' ? '近1月' : currentRange === '3M' ? '近3月' : currentRange === '1Y' ? '近1年' : currentRange === '3Y' ? '近3年' : currentRange === '5Y' ? '近5年' : '全部' }}
          净值数据，点击行查看历史曲线
        </p>
      </div>
      <div class="controls">
        <el-switch
          :model-value="sortDesc()"
          active-text="涨幅优先"
          inactive-text="跌幅优先"
          @change="onSortChange"
        />
      </div>
    </div>

    <el-card shadow="never" class="rank-card">
      <div class="range-bar">
        <el-radio-group v-model="currentRange" size="small" @change="onRangeChange">
          <el-radio-button v-for="r in ranges" :key="r.value" :value="r.value">
            {{ r.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <el-table
        :data="rows"
        v-loading="loading"
        stripe
        height="calc(100vh - 230px)"
        class="rank-table"
        @row-click="openChart"
      >
        <el-table-column label="#" width="60" align="center">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="fund_code" label="基金代码" width="110" />
        <el-table-column prop="fund_name" label="基金名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="区间起始净值" width="130" align="right">
          <template #default="{ row }">
            <span class="num">{{ row.first_nav?.toFixed(4) ?? '--' }}</span>
            <span class="date-tag">{{ row.first_date }}</span>
          </template>
        </el-table-column>
        <el-table-column label="区间结束净值" width="130" align="right">
          <template #default="{ row }">
            <span class="num">{{ row.last_nav?.toFixed(4) ?? '--' }}</span>
            <span class="date-tag">{{ row.last_date }}</span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="130" align="right" fixed="right">
          <template #default="{ row }">
            <span class="rate" :style="{ color: rateColor(row.change_rate) }">
              {{ fmtRate(row.change_rate) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <!-- 历史净值曲线弹窗 -->
    <FundChartDialog v-model="showChart" :fund="currentFund" />
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
.controls {
  display: flex;
  align-items: center;
}
.rank-card {
  border-radius: 10px;
  border: 1px solid rgba(11, 11, 11, 0.10);
}
.range-bar {
  margin-bottom: 12px;
}
.rank-table {
  width: 100%;
}
.rank-table :deep(.el-table__row) {
  cursor: pointer;
}
.num {
  font-variant-numeric: tabular-nums;
  margin-right: 6px;
}
.date-tag {
  font-size: 11px;
  color: #898781;
}
.rate {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
