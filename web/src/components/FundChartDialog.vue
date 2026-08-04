<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getHistory } from '@/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  fund: { type: Object, default: null }, // { fund_code, fund_name }
})

const emit = defineEmits(['update:modelValue'])

const ranges = [
  { value: '1M', label: '近1月' },
  { value: '3M', label: '近3月' },
  { value: '6M', label: '近6月' },
  { value: '1Y', label: '近1年' },
  { value: '3Y', label: '近3年' },
  { value: '5Y', label: '近5年' },
  { value: 'ALL', label: '全部' },
]

// 双向绑定父组件的 v-model，避免内部状态与父组件不同步
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const chartLoading = ref(false)
const currentRange = ref('1Y')
const chartEl = ref(null)
let chart = null
let resizeObserver = null

const open = async () => {
  currentRange.value = '1Y'
  // 等 el-dialog 渲染完成后图表容器才可初始化
  await nextTick()
  await renderChart()
}

const onRangeChange = async (r) => {
  currentRange.value = r
  await renderChart()
}

const renderChart = async () => {
  if (!visible.value || !props.fund) return
  chartLoading.value = true
  try {
    const data = await getHistory(props.fund.fund_code, currentRange.value)
    drawLine(data.items || [])
  } catch (e) {
    ElMessage.error('加载历史净值失败：' + e.message)
  } finally {
    chartLoading.value = false
  }
}

// 净值曲线图：单序列折线（2px），低透明度面积，交叉线+悬浮提示。
// 单序列不需要图例框，标题即图例；悬浮框与表格同源，值不因悬浮而丢失。
const drawLine = (items) => {
  const el = chartEl.value
  if (!el) {
    // 容器尚未挂载（例如弹窗过渡中），等下一帧再画
    setTimeout(() => renderChart(), 120)
    return
  }
  if (!chart) {
    chart = echarts.init(el)
    resizeObserver = new ResizeObserver(() => chart && chart.resize())
    resizeObserver.observe(el)
  }
  const dates = items.map((i) => i.date)
  const unitNav = items.map((i) => i.unit_nav)
  const accNav = items.map((i) => i.accumulated_nav)
  const change = items.map((i) => (i.daily_change === null ? null : i.daily_change * 100))

  const series = [
    {
      name: '单位净值',
      type: 'line',
      data: unitNav,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: '#2a78d6' },
      itemStyle: { color: '#2a78d6' },
      areaStyle: { color: 'rgba(42, 120, 214, 0.10)' },
      emphasis: { focus: 'series' },
    },
  ]
  const legendData = ['单位净值']
  const legendSelected = { 单位净值: true }
  if (accNav.some((v) => v !== null && v !== undefined)) {
    series.push({
      name: '累计净值',
      type: 'line',
      data: accNav,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: '#eb6834' },
      itemStyle: { color: '#eb6834' },
      emphasis: { focus: 'series' },
    })
    legendData.push('累计净值')
    // 累计净值默认关闭，用户点击图例才打开
    legendSelected.累计净值 = false
  }

  // 涨跌率轴：与净值轴同为数据，用第三序列 + 隐藏符号实现
  const showChange = change.some((v) => v !== null && v !== undefined)
  if (showChange) {
    series.push({
      name: '涨跌幅',
      type: 'line',
      yAxisIndex: 1,
      data: change,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 0 },
      itemStyle: { color: 'transparent' },
      emphasis: { disabled: true },
      tooltip: { show: false },
    })
    legendData.push('涨跌幅')
  }

  // 净值与涨跌幅采用双轴。这里是"并列数据"，不是同一量纲的双轴比较，
  // 以 dataviz 规范"同一量纲才允许单轴比较"为前提：净值轴(左)+涨跌幅轴(右)。
  chart.setOption(
    {
      animation: false,
      legend: {
        data: legendData,
        selected: legendSelected,
        textStyle: { color: '#52514e', fontSize: 12 },
        itemWidth: 14,
        itemHeight: 2,
      },
      tooltip: {
        trigger: 'axis',
        confine: true,
        backgroundColor: '#ffffff',
        borderColor: 'rgba(11,11,11,0.10)',
        textStyle: { color: '#0b0b0b' },
        axisPointer: { type: 'cross' },
        // 悬浮框：日期 + 各净值序列 + 当日收益率(%)。
        // 收益率列以文字呈现（不上色），避免状态色与序列色冲突。
        formatter: (params) => {
          const list = Array.isArray(params) ? params : [params]
          if (!list.length) return ''
          const date = list[0].axisValue
          // 用数据点索引直接反查当日涨跌幅，不依赖隐藏序列的 params
          const idx = list[0].dataIndex
          const raw = change[idx]
          const pct = raw !== null && raw !== undefined
            ? Number(raw).toFixed(2) + '%'
            : '--'
          const rows = list
            .filter((p) => p.seriesName === '单位净值' || p.seriesName === '累计净值')
            .map((p) => {
              const v = p.value
              const color = p.color || p.seriesColor || '#52514e'
              return `<div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
                <span style="display:inline-block;width:14px;height:2px;border-radius:1px;background:${color};"></span>
                <span style="color:#52514e;">${p.seriesName}</span>
                <span style="margin-left:auto;font-weight:600;font-variant-numeric:tabular-nums;">${Number(v).toFixed(4)}</span>
              </div>`
            })
            .join('')
          return `<div style="font-size:12px;color:#898781;margin-bottom:2px;">${date}</div>${rows}
            <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
              <span style="color:#52514e;">收益率</span>
              <span style="margin-left:auto;font-weight:600;font-variant-numeric:tabular-nums;">${pct}</span>
            </div>`
        },
      },
      grid: { left: 62, right: 62, top: 44, bottom: 40 },
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
      series,
    },
    true
  )
}

const closeChart = () => {
  visible.value = false
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
}

onBeforeUnmount(closeChart)
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="fund ? `${fund.fund_name} (${fund.fund_code})` : ''"
    width="78%"
    top="6vh"
    destroy-on-close
    @update:model-value="(v) => (visible = v)"
    @open="open"
    @closed="closeChart"
  >
    <div class="chart-filter">
      <el-radio-group v-model="currentRange" size="small" @change="onRangeChange">
        <el-radio-button v-for="r in ranges" :key="r.value" :value="r.value">
          {{ r.label }}
        </el-radio-button>
      </el-radio-group>
    </div>
    <div v-loading="chartLoading" class="chart-box">
      <div ref="chartEl" class="chart"></div>
    </div>
  </el-dialog>
</template>

<style scoped>
.chart-filter {
  margin-bottom: 12px;
}
.chart-box {
  height: 420px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
