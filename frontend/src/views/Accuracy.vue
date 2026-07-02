<template>
  <div>
    <h2 style="font-size:18px;font-weight:600;margin-bottom:16px">📈 准确率看板</h2>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else>
      <!-- 总览卡片 -->
      <div class="grid-3" style="margin-bottom:16px">
        <div class="card" style="text-align:center">
          <div style="color:#888;font-size:13px;margin-bottom:4px">早盘选股</div>
          <div style="font-size:28px;font-weight:700" :class="getColor(stats.morning.win_rate - 50)">{{ stats.morning.win_rate }}%</div>
          <div style="font-size:13px;color:#888">{{ stats.morning.wins }}/{{ stats.morning.total }}</div>
        </div>
        <div class="card" style="text-align:center">
          <div style="color:#888;font-size:13px;margin-bottom:4px">尾盘选股</div>
          <div style="font-size:28px;font-weight:700" :class="getColor(stats.afternoon.win_rate - 50)">{{ stats.afternoon.win_rate }}%</div>
          <div style="font-size:13px;color:#888">{{ stats.afternoon.wins }}/{{ stats.afternoon.total }}</div>
        </div>
        <div class="card" style="text-align:center">
          <div style="color:#888;font-size:13px;margin-bottom:4px">综合</div>
          <div style="font-size:28px;font-weight:700" :class="getColor(overallRate - 50)">{{ overallRate }}%</div>
          <div style="font-size:13px;color:#888">共 {{ totalPicks }} 次</div>
        </div>
      </div>

      <!-- 详细指标 -->
      <div class="grid-2" style="margin-bottom:16px">
        <div class="card">
          <div class="card-title">📊 收益指标</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div>
              <div style="color:#888;font-size:12px">早盘持有1日均值</div>
              <div :class="getColor(stats.morning.avg_hold_1day)" style="font-size:20px;font-weight:700">{{ stats.morning.avg_hold_1day }}%</div>
            </div>
            <div>
              <div style="color:#888;font-size:12px">早盘持有2日均值</div>
              <div :class="getColor(stats.morning.avg_hold_2day)" style="font-size:20px;font-weight:700">{{ stats.morning.avg_hold_2day }}%</div>
            </div>
            <div>
              <div style="color:#888;font-size:12px">尾盘持有1日均值</div>
              <div :class="getColor(stats.afternoon.avg_hold_1day)" style="font-size:20px;font-weight:700">{{ stats.afternoon.avg_hold_1day }}%</div>
            </div>
            <div>
              <div style="color:#888;font-size:12px">尾盘持有2日均值</div>
              <div :class="getColor(stats.afternoon.avg_hold_2day)" style="font-size:20px;font-weight:700">{{ stats.afternoon.avg_hold_2day }}%</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">📈 每日走势</div>
          <div v-if="trendData.length > 0" style="height:160px;position:relative">
            <svg width="100%" height="160" viewBox="0 0 600 160">
              <defs>
                <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#e74c3c" stop-opacity="0.3"/>
                  <stop offset="100%" stop-color="#e74c3c" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <!-- 网格线 -->
              <line v-for="i in [40,80,120]" :key="i" x1="0" y1="160-i" x2="600" y2="160-i" stroke="#1e1e3a" stroke-width="1"/>
              <!-- 面积 -->
              <path :d="areaPath" fill="url(#trendGrad)"/>
              <!-- 折线 -->
              <path :d="linePath" fill="none" stroke="#e74c3c" stroke-width="2"/>
              <!-- 点 -->
              <circle v-for="(d,i) in trendData" :key="i" :cx="40 + i * (520/(trendData.length-1||1))" :cy="160 - d.rate * 1.2" r="3" fill="#e74c3c"/>
            </svg>
          </div>
          <div v-else class="empty" style="height:160px;display:flex;align-items:center;justify-content:center">暂无数据</div>
        </div>
      </div>

      <!-- 周报 -->
      <div class="card">
        <div class="card-title">📋 最近周报</div>
        <div v-if="reports.length > 0">
          <div v-for="r in reports" :key="r.id" style="margin-bottom:8px;padding:10px;background:#15152a;border-radius:6px">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
              <strong style="font-size:14px">{{ r.week_start }} ~ {{ r.week_end }}</strong>
              <span style="color:#888;font-size:12px">生成于 {{ r.created_at?.slice(0,10) }}</span>
            </div>
            <div v-if="r.content" style="font-size:13px;color:#aaa">
              <div>早盘胜率：{{ r.content.morning_win_rate || r.content.summary?.morning_win_rate || '-' }}%</div>
              <div>尾盘胜率：{{ r.content.afternoon_win_rate || r.content.summary?.afternoon_win_rate || '-' }}%</div>
              <div v-if="r.content.recommendations && r.content.recommendations.length > 0">
                <div v-for="(rec, i) in r.content.recommendations" :key="i" style="color:#f0b90b">💡 {{ rec }}</div>
              </div>
              <div v-if="r.content.changes_made && r.content.changes_made.length > 0">
                <div v-for="(ch, i) in r.content.changes_made" :key="i" style="color:#3498db">🔄 {{ ch }}</div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty">暂无周报数据（每周六/日自动生成）</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const stats = ref({ morning: {}, afternoon: {} })
const reports = ref([])
const loading = ref(true)

const totalPicks = computed(() => (stats.value.morning.total || 0) + (stats.value.afternoon.total || 0))
const overallRate = computed(() => {
  const m = stats.value.morning
  const a = stats.value.afternoon
  const total = (m.total || 0) + (a.total || 0)
  const wins = (m.wins || 0) + (a.wins || 0)
  return total > 0 ? (wins / total * 100).toFixed(1) : 0
})

const trendData = computed(() => {
  // 从stats中提取daily_trend
  return stats.value.daily_trend || []
})

const linePath = computed(() => {
  const d = trendData.value
  if (!d || d.length < 2) return ''
  const points = d.map((p, i) => {
    const x = 40 + i * (520 / (d.length - 1))
    const y = 160 - p.rate * 1.2
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  })
  return points.join(' ')
})

const areaPath = computed(() => {
  const d = trendData.value
  if (!d || d.length < 2) return ''
  const last = d.length - 1
  const lastX = 40 + last * (520 / (d.length - 1))
  const firstX = 40
  return `${linePath.value} L${lastX},160 L${firstX},160 Z`
})

function getColor(v) {
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}

async function fetchStats() {
  try {
    const r = await fetch('/api/stats?days=30')
    stats.value = await r.json()
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
}

async function fetchReports() {
  try {
    const r = await fetch('/api/weekly-reports?limit=5')
    reports.value = await r.json()
  } catch (e) {
    console.error('获取周报失败:', e)
  }
}

onMounted(async () => {
  await Promise.all([fetchStats(), fetchReports()])
  loading.value = false
})
</script>
