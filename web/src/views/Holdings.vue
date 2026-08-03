<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { addHolding, addTransaction, listHoldings, removeHolding, searchFunds, setAmount } from '@/api'

// ============================================================
// 数据
// ============================================================
const holdings = ref([])
const loading = ref(false)
const saving = ref(false)

const loadHoldings = async () => {
  loading.value = true
  try {
    const data = await listHoldings()
    holdings.value = data.holdings || []
  } catch (e) {
    ElMessage.error('加载持仓失败：' + e.message)
  } finally {
    loading.value = false
  }
}

const fmtAmount = (v) => Number(v || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })

// ============================================================
// 添加基金
// ============================================================
const addDialog = ref(false)
const addLoading = ref(false)
const keyword = ref('')
const options = ref([])
const searching = ref(false)
const selectedCode = ref('')

const onSearch = async (query) => {
  keyword.value = query
  if (!query || query.trim().length === 0) {
    options.value = []
    return
  }
  searching.value = true
  try {
    const data = await searchFunds(query.trim(), 15)
    options.value = data.results || []
  } catch (e) {
    options.value = []
  } finally {
    searching.value = false
  }
}

const handleAdd = async () => {
  if (!selectedCode.value) {
    ElMessage.warning('请选择要添加的基金')
    return
  }
  addLoading.value = true
  try {
    await addHolding(selectedCode.value)
    ElMessage.success(`已添加 ${selectedCode.value}`)
    addDialog.value = false
    selectedCode.value = ''
    keyword.value = ''
    options.value = []
    await loadHoldings()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    addLoading.value = false
  }
}

// ============================================================
// 完全修改（当前金额 + 收益金额）
// ============================================================
const editDialog = ref(false)
const editLoading = ref(false)
const editForm = ref({
  fund_code: '',
  fund_name: '',
  current_amount: 0,
  profit_amount: 0,
})

const openEdit = (h) => {
  editForm.value = {
    fund_code: h.fund_code,
    fund_name: h.fund_name,
    current_amount: h.current_amount,
    profit_amount: h.profit_amount,
  }
  editDialog.value = true
}

const handleEdit = async () => {
  editLoading.value = true
  try {
    await setAmount(editForm.value.fund_code, editForm.value.current_amount, editForm.value.profit_amount)
    ElMessage.success('已保存')
    editDialog.value = false
    await loadHoldings()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    editLoading.value = false
  }
}

// ============================================================
// 加仓 / 减仓
// ============================================================
const txnDialog = ref(false)
const txnLoading = ref(false)
const txnForm = ref({
  fund_code: '',
  fund_name: '',
  txn_date: '',
  amount: 0,
})
const txnType = ref('add') // add | reduce
const txnUpdateAmount = ref(true) // 是否同时更新持仓金额

const openTxn = (h, type) => {
  txnType.value = type
  txnForm.value = {
    fund_code: h.fund_code,
    fund_name: h.fund_name,
    txn_date: '',
    amount: 0,
  }
  txnUpdateAmount.value = true
  txnDialog.value = true
}

const handleTxn = async () => {
  if (!txnForm.value.txn_date) {
    ElMessage.warning('请选择日期')
    return
  }
  if (!txnForm.value.amount || Number(txnForm.value.amount) <= 0) {
    ElMessage.warning('请输入大于 0 的金额')
    return
  }
  const sign = txnType.value === 'reduce' ? -1 : 1
  txnLoading.value = true
  try {
    await addTransaction(
      txnForm.value.fund_code,
      txnForm.value.txn_date,
      sign * Number(txnForm.value.amount),
      txnUpdateAmount.value
    )
    ElMessage.success('已记录')
    txnDialog.value = false
    await loadHoldings()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    txnLoading.value = false
  }
}

// ============================================================
// 删除持仓
// ============================================================
const handleRemove = async (h) => {
  try {
    await ElMessageBox.confirm(
      `确定删除基金「${h.fund_name} (${h.fund_code})」及其全部增减仓记录吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return // 取消
  }
  try {
    await removeHolding(h.fund_code)
    ElMessage.success('已删除')
    await loadHoldings()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(loadHoldings)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="title">持仓管理</h2>
        <p class="subtitle">共 {{ holdings.length }} 只基金，点击表格中的操作修改持仓</p>
      </div>
      <el-button type="primary" :icon="'Plus'" @click="addDialog = true">
        添加基金
      </el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="holdings" v-loading="loading" stripe>
        <el-table-column prop="fund_code" label="基金代码" width="120" />
        <el-table-column prop="fund_name" label="基金名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="当前金额" width="150" align="right">
          <template #default="{ row }">
            <span class="num">{{ fmtAmount(row.current_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="收益金额" width="150" align="right">
          <template #default="{ row }">
            <span
              class="num"
              :style="{ color: (row.profit_amount || 0) >= 0 ? '#d03b3b' : '#0ca30c' }"
            >
              {{ (row.profit_amount || 0) >= 0 ? '+' : '' }}{{ fmtAmount(row.profit_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="增减仓记录" width="130" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.transactions?.length || 0 }} 条</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">完全修改</el-button>
            <el-button size="small" type="success" @click="openTxn(row, 'add')">加仓</el-button>
            <el-button size="small" type="warning" @click="openTxn(row, 'reduce')">减仓</el-button>
            <el-button size="small" type="danger" @click="handleRemove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加基金 -->
    <el-dialog v-model="addDialog" title="添加基金" width="480px" destroy-on-close>
      <el-form label-width="70px">
        <el-form-item label="基金" required>
          <el-select
            v-model="selectedCode"
            filterable
            remote
            clearable
            reserve-keyword
            placeholder="输入基金代码或名称搜索"
            :remote-method="onSearch"
            :loading="searching"
            style="width: 100%"
          >
            <el-option
              v-for="o in options"
              :key="o.fund_code"
              :value="o.fund_code"
              :label="`${o.fund_code} ${o.fund_name}`"
            >
              <span class="opt-code">{{ o.fund_code }}</span>
              <span class="opt-name">{{ o.fund_name }}</span>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialog = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAdd">添加</el-button>
      </template>
    </el-dialog>

    <!-- 完全修改 -->
    <el-dialog v-model="editDialog" title="完全修改持仓" width="440px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="基金">
          <span class="form-fund">{{ editForm.fund_name }} ({{ editForm.fund_code }})</span>
        </el-form-item>
        <el-form-item label="当前金额" required>
          <el-input-number
            v-model="editForm.current_amount"
            :min="0"
            :precision="2"
            :step="1000"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="收益金额" required>
          <el-input-number
            v-model="editForm.profit_amount"
            :precision="2"
            :step="100"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item>
          <span class="hint">收益金额可为负数（亏损）</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 加仓/减仓 -->
    <el-dialog
      v-model="txnDialog"
      :title="txnType === 'add' ? '加仓' : '减仓'"
      width="440px"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item label="基金">
          <span class="form-fund">{{ txnForm.fund_name }} ({{ txnForm.fund_code }})</span>
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker
            v-model="txnForm.txn_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择增减仓日期"
            :clearable="false"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="txnType === 'add' ? '加仓金额' : '减仓金额'" required>
          <el-input-number
            v-model="txnForm.amount"
            :min="0.01"
            :precision="2"
            :step="1000"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="持仓金额">
          <el-switch v-model="txnUpdateAmount" />
          <span class="hint txn-hint">
            {{ txnUpdateAmount ? '加仓将增加、减仓将扣减当前持仓金额' : '仅记录流水，不改变持仓金额' }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="txnDialog = false">取消</el-button>
        <el-button
          :type="txnType === 'add' ? 'success' : 'warning'"
          :loading="txnLoading"
          @click="handleTxn"
        >
          确认{{ txnType === 'add' ? '加仓' : '减仓' }}
        </el-button>
      </template>
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
.table-card {
  border-radius: 10px;
  border: 1px solid rgba(11, 11, 11, 0.10);
}
.num {
  font-variant-numeric: tabular-nums;
}
.opt-code {
  font-weight: 600;
  margin-right: 8px;
}
.opt-name {
  color: #52514e;
}
.form-fund {
  color: #0b0b0b;
}
.hint {
  font-size: 12px;
  color: #898781;
}
.txn-hint {
  margin-left: 8px;
}
</style>
