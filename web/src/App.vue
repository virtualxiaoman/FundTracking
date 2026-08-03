<script setup>
import { useRoute } from 'vue-router'

// 图标组件已全局注册
const menus = [
  { path: '/', label: '首页', icon: 'HomeFilled' },
  { path: '/holdings', label: '持仓', icon: 'Coin' },
  { path: '/ranking', label: '全部基金排行', icon: 'TrendCharts' },
]

const route = useRoute()
const active = () => {
  if (route.path.startsWith('/holdings')) return '/holdings'
  if (route.path.startsWith('/ranking')) return '/ranking'
  return '/'
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="180px" class="aside">
      <div class="brand">
        <el-icon :size="22"><Wallet /></el-icon>
        <span>基金看板</span>
      </div>
      <el-menu :default-active="active()" router class="menu">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background: #1f2d3d;
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  padding: 18px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.menu {
  border-right: none;
  background: transparent;
  flex: 1;
}
.menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.72);
}
.menu :deep(.el-menu-item.is-active) {
  color: #409eff;
  background: rgba(64, 158, 255, 0.12);
}
.menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
}
.main {
  background: #f2f4f8;
  padding: 20px;
  overflow: auto;
}
</style>
