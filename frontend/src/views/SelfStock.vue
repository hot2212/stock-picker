<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="font-size:18px;font-weight:600">⭐ 自选股分析</h2>
      <div style="display:flex;gap:8px;align-items:center">
        <input v-model="addCode" class="input" placeholder="输入股票代码" style="width:140px" @keyup.enter="addStock" />
        <button class="btn btn-primary btn-sm" @click="addStock">+ 添加</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="stocks.length === 0" class="card">
      <div class="empty">暂无自选股，输入股票代码添加</div>
    </div>

    <div v-else>
      <div class="card" v-for="s in stocks" :key="s.id" style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div>
            <strong style="font-size:16px">{{ s.name }}</strong>
            <span style="color:#888;font-size:13px;margin-left:8px">{{ s.code }}</span>
            <span style="color:#555;font-size:12px;margin-left:8px">添加于 {{ s.added_date }}</span>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <span v-if="s.realtime" :class="getColor(s.realtime.change_pct)" style="font-size:18px;font-weight:700">{{ s.realtime.price }}</span>
            <span v-if="s.realtime" :class="getColor(s.realtime.change_pct)" style="font-size:14px">{{ fmtPct(s.realtime.change_pct) }}</span>
            <button class="btn btn-danger btn-sm" @click="remove(s.id)">✕ 删除</button>
          </div>
        </div>

        <!-- 分析结果 -->
        <div v-if="s.score !== null" style="display:grid;grid-template-columns:1fr 2fr;gap:12px">
          <!-- 评分面板 -->
          <div style="background:#15152a;border-radius:8px;padding:12px">
            <div style="text-align:center;margin-bottom:8px">
              <div style="font-size:32px;font-weight:700" :class="scoreColor(s.score)">{{ s.score }}</div>
              <div style="font-size:13px;color:#888">综合评分</div>
              <div style="margin-top:4px">
                <span class="badge" :class="s.buy_advice?.includes('✅') ? 'badge-up' : s.buy_advice?.includes('⏳') ? 'badge-hot' : 'badge-lose'" style="font-size:12px">
                  {{ s.buy_advice || '-' }}
                </span>
              </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px">
              <div v-for="(v,k) in scoreDetail(s)" :key="k" style="display:flex;justify-content:space-between;padding:2px 4px">
                <span style="color:#888">{{ k }}</span>
                <span :class="scoreColor(v*5)">{{ v }}</span>
              </div>
            </div>
          </div>

          <!-- 买卖建议 -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">
            <div style="background:#15152a;border-radius:6px;padding:10px">
              <div style="color:#888;margin-bottom:4px">买入区间</div>
              <div style="color:#e74c3c;font-weight:600">{{ s.buy_range_low || '-' }} ~ {{ s.buy_range_high || '-' }}</div>
            </div>
            <div style="background:#15152a;border-radius:6px;padding:10px">
              <div style="color:#888;margin-bottom:4px">目标价位</div>
              <div style="color:#f0b90b;font-weight:600">
                ① {{ s.target_price1 || '-' }}
                <span style="color:#888;font-weight:400"> ② {{ s.target_price2 || '-' }}</span>
              </div>
            </div>
            <div style="background:#15152a;border-radius:6px;padding:10px">
              <div style="color:#888;margin-bottom:4px">止损价位</div>
              <div style="color:#27ae60;font-weight:600">{{ s.stop_loss || '-' }}</div>
            </div>
            <div style="background:#15152a;border-radius:6px;padding:10px">
              <div style="color:#888;margin-bottom:4px">分析时间</div>
              <div style="color:#aaa">{{ s.analysis_date ? s.analysis_date.slice(0,16) : '-' }}</div>
            </div>

            <!-- 分析依据 -->
            <div style="grid-column:1/-1;background:#15152a;border-radius:6px;padding:10px;margin-top:4px">
              <div style="color:#f0b90b;font-size:12px;margin-bottom:6px">📋 分析依据</div>
              <div v-if="s.analysis_reason" style="color:#aaa;font-size:12px;white-space:pre-line;line-height:1.6">{{ s.analysis_reason }}</div>
              <div v-else style="color:#555;font-size:12px">暂无分析数据</div>
            </div>
          </div>
        </div>

        <div v-else class="empty" style="padding:12px">⏳ 分析中...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const stocks = ref([])
const loading = ref(true)
const addCode = ref('')
let pollTimer = null

function getColor(v) {
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}

function scoreColor(score) {
  score = parseFloat(score) || 0
  if (score >= 70) return 'up'
  if (score >= 55) return 'flat'
  return 'down'
}

function fmtPct(v) {
  v = parseFloat(v) || 0
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

function scoreDetail(s) {
  try {
    return JSON.parse(s.score_detail || '{}')
  } catch { return {} }
}

async function fetchStocks() {
  try {
    const r = await fetch('/api/self-stocks')
    stocks.value = await r.json()
  } catch (e) {
    console.error('获取自选股失败:', e)
  } finally {
    loading.value = false
  }
}

async function addStock() {
  const code = addCode.value.trim()
  if (!code) return
  try {
    await fetch(`/api/self-stocks/add?code=${code}`, { method: 'POST' })
    addCode.value = ''
    await fetchStocks()
  } catch (e) {
    console.error('添加失败:', e)
  }
}

async function remove(id) {
  try {
    await fetch(`/api/self-stocks/${id}`, { method: 'DELETE' })
    await fetchStocks()
  } catch (e) {
    console.error('删除失败:', e)
  }
}

onMounted(() => {
  fetchStocks()
  pollTimer = setInterval(fetchStocks, 30000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
