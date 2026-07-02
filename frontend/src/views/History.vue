<template>
  <div>
    <h2 style="font-size:18px;font-weight:600;margin-bottom:16px">📅 历史记录</h2>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="historyData.length === 0" class="card">
      <div class="empty">暂无历史数据</div>
    </div>

    <div v-else>
      <div class="card" v-for="day in historyData" :key="day.date">
        <div style="display:flex;justify-content:space-between;align-items:center;cursor:pointer" @click="toggleDay(day.date)">
          <div>
            <strong style="font-size:15px">{{ day.date }}</strong>
            <span style="color:#888;font-size:13px;margin-left:12px">早盘 {{ day.morning_rate }}% ({{ day.morning_wins }}/{{ day.morning_count }})</span>
            <span style="color:#888;font-size:13px;margin-left:8px">尾盘 {{ day.afternoon_rate }}% ({{ day.afternoon_wins }}/{{ day.afternoon_count }})</span>
          </div>
          <span style="color:#666;font-size:12px">{{ expanded[day.date] ? '收起 ▲' : '展开 ▼' }}</span>
        </div>

        <div v-if="expanded[day.date]" style="margin-top:12px">
          <!-- 早盘 -->
          <div v-if="day.morning && day.morning.length > 0" style="margin-bottom:12px">
            <div style="color:#888;font-size:13px;margin-bottom:6px">🌅 早盘选股</div>
            <table class="data-table">
              <thead><tr><th>#</th><th>代码</th><th>名称</th><th>选股价</th><th>收盘价</th><th>收盘涨幅</th><td>持有1日</td><td>持有2日</td><th>胜负</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in day.morning" :key="s.id">
                  <td>{{ i+1 }}</td>
                  <td>{{ s.code }}</td>
                  <td><strong>{{ s.name }}</strong></td>
                  <td>{{ s.pick_price || '-' }}</td>
                  <td>{{ s.close_price || '-' }}</td>
                  <td :class="getColor(s.close_change)">{{ s.close_change ? fmtPct(s.close_change) : '-' }}</td>
                  <td :class="getColor(s.hold_1day_max)">{{ s.hold_1day_max ? fmtPct(s.hold_1day_max) : '-' }}</td>
                  <td :class="getColor(s.hold_2day_max)">{{ s.hold_2day_max ? fmtPct(s.hold_2day_max) : '-' }}</td>
                  <td><span :class="s.is_win ? 'badge badge-win' : 'badge badge-lose'">{{ s.is_win ? '✅' : '❌' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 尾盘 -->
          <div v-if="day.afternoon && day.afternoon.length > 0">
            <div style="color:#888;font-size:13px;margin-bottom:6px">🌆 尾盘选股</div>
            <table class="data-table">
              <thead><tr><th>#</th><th>代码</th><th>名称</th><th>选股价</th><th>收盘价</th><th>收盘涨幅</th><td>持有1日</td><td>持有2日</td><th>胜负</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in day.afternoon" :key="s.id">
                  <td>{{ i+1 }}</td>
                  <td>{{ s.code }}</td>
                  <td><strong>{{ s.name }}</strong></td>
                  <td>{{ s.pick_price || '-' }}</td>
                  <td>{{ s.close_price || '-' }}</td>
                  <td :class="getColor(s.close_change)">{{ s.close_change ? fmtPct(s.close_change) : '-' }}</td>
                  <td :class="getColor(s.hold_1day_max)">{{ s.hold_1day_max ? fmtPct(s.hold_1day_max) : '-' }}</td>
                  <td :class="getColor(s.hold_2day_max)">{{ s.hold_2day_max ? fmtPct(s.hold_2day_max) : '-' }}</td>
                  <td><span :class="s.is_win ? 'badge badge-win' : 'badge badge-lose'">{{ s.is_win ? '✅' : '❌' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const historyData = ref([])
const loading = ref(true)
const expanded = ref({})

function getColor(v) {
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}

function fmtPct(v) {
  v = parseFloat(v) || 0
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

function toggleDay(date) {
  expanded.value[date] = !expanded.value[date]
}

async function fetchHistory() {
  try {
    const r = await fetch('/api/history?days=30')
    historyData.value = await r.json()
  } catch (e) {
    console.error('获取历史失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchHistory)
</script>
