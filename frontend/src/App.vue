<template>
  <div class="app">
    <nav class="nav">
      <div class="nav-title">📈 短线选股系统</div>
      <div class="nav-links">
        <router-link v-for="r in routes" :key="r.path" :to="r.path" class="nav-link" active-class="active">
          {{ r.meta.title }}
        </router-link>
      </div>
      <div class="nav-time">{{ currentTime }}</div>
    </nav>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const routes = router.options.routes

const currentTime = ref('')
let timer = null

onMounted(() => {
  const update = () => {
    const now = new Date()
    currentTime.value = now.toLocaleString('zh-CN', { hour12: false })
  }
  update()
  timer = setInterval(update, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #0f0f1a;
  color: #e0e0e0;
  min-height: 100vh;
}

.app { min-height: 100vh; display: flex; flex-direction: column; }

.nav {
  background: #1a1a2e;
  border-bottom: 1px solid #2a2a4a;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 32px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-title {
  font-size: 18px;
  font-weight: 700;
  color: #f0b90b;
  white-space: nowrap;
}

.nav-links { display: flex; gap: 4px; flex: 1; }

.nav-link {
  color: #888;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  transition: all .2s;
}
.nav-link:hover { color: #fff; background: #2a2a4a; }
.nav-link.active { color: #fff; background: #f0b90b33; color: #f0b90b; }

.nav-time { color: #666; font-size: 13px; white-space: nowrap; }

.main {
  flex: 1;
  padding: 16px 24px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* 通用样式 */
.card {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #ccc;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #2a2a4a;
}

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  text-align: left;
  padding: 8px 10px;
  background: #15152a;
  color: #888;
  font-weight: 500;
  border-bottom: 1px solid #2a2a4a;
  white-space: nowrap;
}
.data-table td {
  padding: 10px;
  border-bottom: 1px solid #1e1e3a;
  white-space: nowrap;
}
.data-table tr:hover td { background: #1e1e3a; }

/* 涨跌颜色 */
.up { color: #e74c3c; }   /* A股红涨 */
.down { color: #27ae60; } /* A股绿跌 */
.flat { color: #888; }

/* 标签 */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.badge-up { background: #e74c3c22; color: #e74c3c; }
.badge-down { background: #27ae6022; color: #27ae60; }
.badge-hot { background: #f0b90b22; color: #f0b90b; }
.badge-info { background: #3498db22; color: #3498db; }
.badge-win { background: #e74c3c22; color: #e74c3c; }
.badge-lose { background: #555; color: #999; }

/* 按钮 */
.btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 14px; border-radius: 6px;
  border: 1px solid #2a2a4a; background: #15152a;
  color: #ccc; font-size: 13px; cursor: pointer; transition: all .2s;
}
.btn:hover { background: #2a2a4a; color: #fff; }
.btn-primary { background: #f0b90b; color: #1a1a2e; border-color: #f0b90b; }
.btn-primary:hover { background: #f5c824; }
.btn-danger { background: #e74c3c22; color: #e74c3c; border-color: #e74c3c44; }
.btn-danger:hover { background: #e74c3c44; }
.btn-sm { padding: 4px 10px; font-size: 12px; }

/* 输入框 */
.input {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid #2a2a4a;
  background: #15152a;
  color: #e0e0e0;
  font-size: 13px;
  outline: none;
}
.input:focus { border-color: #f0b90b; }

/* loading */
.loading {
  text-align: center;
  padding: 40px;
  color: #666;
  font-size: 14px;
}

/* 空状态 */
.empty {
  text-align: center;
  padding: 30px;
  color: #555;
  font-size: 14px;
}

/* 滚动条 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3a3a5a; }

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 12px;
  padding: 24px;
  max-width: 640px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}
.modal-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-close {
  cursor: pointer;
  color: #666;
  font-size: 20px;
  background: none;
  border: none;
}
.modal-close:hover { color: #fff; }

/* 网格布局 */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }

@media (max-width: 1024px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
  .main { padding: 12px; }
}

/* 选中理由 */
.reason-text { color: #888; font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
