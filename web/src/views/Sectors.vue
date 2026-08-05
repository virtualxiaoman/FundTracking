<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getSectorHistory, getSectorTree } from '@/api'

// ============================================================
// 数据
// ============================================================
const tree = ref([])
const loading = ref(false)
const collapsed = ref(false) // 折叠: 只显示大板块

const loadTree = async () => {
  loading.value = true
  try {
    const data = await getSectorTree()
    tree.value = data.sectors || []
  } catch (e) {
    ElMessage.error('加载板块失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// 涨跌用色：涨红跌绿（国内习惯）
const upColor = '#d03b3b'
const downColor = '#0ca30c'

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

// ============================================================
// 历史曲线弹窗（板块历史涨跌幅）
// ============================================================
const showChart = ref(false)
const chartLoading = ref(false)
const currentSector = ref(null)
const chartEl = ref(null)
let chart = null
let resizeObserver = null

const openChart = async (sector) => {
  currentSector.value = sector
  showChart.value = true
  await nextTick()
  await renderChart()
}

const renderChart = async () => {
  if (!showChart.value || !currentSector.value) return
  chartLoading.value = true
  try {
    const data = await getSectorHistory(currentSector.value.id)
    drawLine(data.items || [])
  } catch (e) {
    ElMessage.error('加载板块历史失败：' + e.message)
  } finally {
    chartLoading.value = false
  }
}

const drawLine = (items) => {
  const el = chartEl.value
  if (!el) {
    setTimeout(() => renderChart(), 120)
    return
  }
  if (!chart) {
    chart = echarts.init(el)
    resizeObserver = new ResizeObserver(() => chart && chart.resize())
    resizeObserver.observe(el)
  }
  const dates = items.map((i) => i.date)
  // 曲线画净值；悬浮时展示当日涨跌幅
  const navs = items.map((i) => (i.nav === null || i.nav === undefined ? null : i.nav))
  const rates = items.map((i) =>
    i.change_rate === null || i.change_rate === undefined ? null : i.change_rate * 100
  )

  chart.setOption(
    {
      animation: false,
      tooltip: {
        trigger: 'axis',
        confine: true,
        backgroundColor: '#ffffff',
        borderColor: 'rgba(11,11,11,0.10)',
        textStyle: { color: '#0b0b0b' },
        axisPointer: { type: 'cross' },
        formatter: (params) => {
          const list = Array.isArray(params) ? params : [params]
          if (!list.length) return ''
          const date = list[0].axisValue
          const idx = list[0].dataIndex
          const nav = navs[idx]
          const pct = rates[idx] !== null && rates[idx] !== undefined
            ? `${Number(rates[idx]).toFixed(2)}%`
            : '--'
          return `<div style="font-size:12px;color:#898781;margin-bottom:2px;">${date}</div>
            <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
              <span style="display:inline-block;width:14px;height:2px;border-radius:1px;background:#2a78d6;"></span>
              <span style="color:#52514e;">净值</span>
              <span style="margin-left:auto;font-weight:600;font-variant-numeric:tabular-nums;">${nav !== null && nav !== undefined ? Number(nav).toFixed(4) : '--'}</span>
            </div>
            <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
              <span style="color:#52514e;">涨跌幅</span>
              <span style="margin-left:auto;font-weight:600;font-variant-numeric:tabular-nums;">${pct}</span>
            </div>`
        },
      },
      grid: { left: 56, right: 56, top: 32, bottom: 40 },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLine: { lineStyle: { color: '#c3c2b7' } },
        axisTick: { show: false },
        axisLabel: { color: '#898781', fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value',
          scale: true,
          axisLabel: { color: '#898781', fontSize: 11 },
          splitLine: { lineStyle: { color: '#e1e0d9' } },
          name: '净值',
          nameTextStyle: { color: '#898781', fontSize: 11 },
        },
        {
          type: 'value',
          scale: true,
          axisLabel: { color: '#898781', fontSize: 11, formatter: '{value}%' },
          splitLine: { show: false },
          name: '涨跌幅',
          nameTextStyle: { color: '#898781', fontSize: 11 },
        },
      ],
      dataZoom: [
        { type: 'inside', throttle: 50 },
        { type: 'slider', height: 16, bottom: 6 },
      ],
      series: [
        {
          name: '净值',
          type: 'line',
          data: navs,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#2a78d6' },
          itemStyle: { color: '#2a78d6' },
          areaStyle: { color: 'rgba(42, 120, 214, 0.10)' },
          emphasis: { focus: 'series' },
        },
        {
          // 涨跌幅作为辅助序列，用于右轴与悬浮，不画线
          name: '涨跌幅',
          type: 'line',
          yAxisIndex: 1,
          data: rates,
          showSymbol: false,
          lineStyle: { width: 0 },
          itemStyle: { color: 'transparent' },
          tooltip: { show: false },
        },
      ],
    },
    true
  )
}

const closeChart = () => {
  showChart.value = false
  currentSector.value = null
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
}

onMounted(loadTree)
onBeforeUnmount(closeChart)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="title">板块涨跌幅</h2>
        <p class="subtitle">点击板块查看历史曲线 · 折叠后只看大板块</p>
      </div>
      <el-switch
        v-model="collapsed"
        active-text="展开"
        inactive-text="折叠"
        inline-prompt
      />
    </div>

    <el-skeleton :loading="loading" animated :rows="8" class="skeleton">
      <template #default>
        <div class="sector-list">
          <div v-for="main in tree" :key="main.id" class="main-sector">
            <div class="main-head" @click="openChart(main)">
              <span class="main-name">{{ main.name }}</span>
              <span class="main-rate" :style="{ color: rateColor(main.change_rate) }">
                {{ fmtRate(main.change_rate) }}
              </span>
            </div>

            <!-- 折叠时隐藏子板块 -->
            <div v-if="!collapsed" class="child-grid">
              <div
                v-for="child in main.children"
                :key="child.id"
                class="child-card"
                @click="openChart(child)"
              >
                <span class="child-name">{{ child.name }}</span>
                <span class="child-rate" :style="{ color: rateColor(child.change_rate) }">
                  {{ fmtRate(child.change_rate) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </el-skeleton>

    <!-- 板块历史曲线弹窗 -->
    <el-dialog
      v-model="showChart"
      :title="currentSector ? `${currentSector.name} 历史涨跌幅` : ''"
      width="78%"
      top="6vh"
      destroy-on-close
      @closed="closeChart"
    >
      <div v-loading="chartLoading" class="chart-box">
        <div ref="chartEl" class="chart"></div>
      </div>
    </el-dialog>
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
.sector-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.main-sector {
  background: #fcfcfb;
  border: 1px solid rgba(11, 11, 11, 0.10);
  border-radius: 10px;
  overflow: hidden;
}
.main-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  background: #f2f5fa;
  transition: background 0.15s;
}
.main-head:hover {
  background: #e6ecf5;
}
.main-name {
  font-weight: 600;
  font-size: 15px;
  color: #0b0b0b;
}
.main-rate {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.child-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
  padding: 12px 16px;
}
.child-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  border: 1px solid #eceef1;
  border-radius: 8px;
  transition: background 0.15s, border-color 0.15s;
}
.child-card:hover {
  background: #f7f9fc;
  border-color: #d6dce4;
}
.child-name {
  font-size: 13px;
  color: #52514e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.child-rate {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  font-size: 13px;
  margin-left: 6px;
  white-space: nowrap;
}
.skeleton {
  margin-top: 8px;
}
.chart-box {
  height: 420px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
