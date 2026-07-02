<template>
  <div>
    <!-- 顶部大盘 -->
    <div class="grid-3" style="margin-bottom: 16px;">
      <div class="card" v-for="(idx, name) in indexLabels" :key="name">
        <div class="card-title" style="border:none;margin-bottom:4px;padding-bottom:0">{{ name }}</div>
        <div v-if="indexData[name]" :class="getColor(indexData[name].change_pct)">
          <span style="font-size:24px;font-weight:700">{{ indexData[name].price }}</span>
          <span style="font-size:14px;margin-left:8px">{{ indexData[name].change_pct >= 0 ? '+' : '' }}{{ indexData[name].change_pct }}%</span>
        </div>
        <div v-else style="color:#555;font-size:14px">加载中...</div>
      </div>
    </div>

    <div class="grid-2">
      <!-- 左栏 -->
      <div>
        <!-- 早盘精选 -->
        <div class="card">
          <div class="card-title">🌅 早盘精选（今日 9:27）<span v-if="todayData.morning_ready" class="badge badge-up" style="margin-left:8px">已更新</span></div>
          <div v-if="todayData.morning && todayData.morning.length > 0">
            <table class="data-table">
              <thead><tr><th>#</th><th>代码</th><th>名称</th><th>现价</th><th>涨幅</th><th>成交额</th><th>理由</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in todayData.morning" :key="s.id" @click="showDetail(s, 'morning')" style="cursor:pointer">
                  <td style="color:#f0b90b;font-weight:700">{{ i + 1 }}</td>
                  <td>{{ s.code }}</td>
                  <td><strong>{{ s.name }}</strong></td>
                  <td :class="getColor(getRT(s,'change_pct'))">{{ getRT(s,'price') }}</td>
                  <td :class="getColor(getRT(s,'change_pct'))">{{ fmtPct(getRT(s,'change_pct')) }}</td>
                  <td>{{ fmtAmount(getRT(s,'amount_wan')) }}</td>
                  <td><span class="reason-text">{{ s.reason }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty">⏳ 等待 9:27 选股...</div>
        </div>

        <!-- 昨日尾盘（实时跟踪） -->
        <div class="card">
          <div class="card-title">🌆 昨日尾盘（实时跟踪）<span v-if="todayData.afternoon_yesterday && todayData.afternoon_yesterday.length > 0" class="badge badge-info" style="margin-left:8px">盘中</span></div>
          <div v-if="todayData.afternoon_yesterday && todayData.afternoon_yesterday.length > 0">
            <table class="data-table">
              <thead><tr><th>#</th><th>代码</th><th>名称</th><th>选股价</th><th>选股涨幅</th><th>现价</th><th>实时涨幅</th><th>盈亏</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in todayData.afternoon_yesterday" :key="s.id" @click="showDetail(s, 'afternoon')" style="cursor:pointer">
                  <td style="color:#3498db;font-weight:700">{{ i + 1 }}</td>
                  <td>{{ s.code }}</td>
                  <td><strong>{{ s.name }}</strong></td>
                  <td>{{ s.pick_price }}</td>
                  <td :class="getColor(s.pick_change)">{{ fmtPct(s.pick_change) }}</td>
                  <td>{{ getRT(s,'price') }}</td>
                  <td :class="getColor(getRT(s,'change_pct'))">{{ fmtPct(getRT(s,'change_pct')) }}</td>
                  <td :class="getColor(getProfit(s))">{{ fmtPct(getProfit(s)) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty">暂无昨日尾盘数据</div>
        </div>
      </div>

      <!-- 右栏 -->
      <div>
        <!-- 今日尾盘 -->
        <div class="card">
          <div class="card-title">🌆 今日尾盘（14:30）<span v-if="todayData.afternoon_ready" class="badge badge-up" style="margin-left:8px">已更新</span></div>
          <div v-if="todayData.afternoon_today && todayData.afternoon_today.length > 0">
            <table class="data-table">
              <thead><tr><th>#</th><th>代码</th><th>名称</th><th>选股价</th><th>涨幅</th><th>主力净流入</th><th>理由</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in todayData.afternoon_today" :key="s.id" @click="showDetail(s, 'afternoon')" style="cursor:pointer">
                  <td style="color:#f0b90b;font-weight:700">{{ i + 1 }}</td>
                  <td>{{ s.code }}</td>
                  <td><strong>{{ s.name }}</strong></td>
                  <td>{{ s.pick_price }}</td>
                  <td :class="getColor(s.pick_change)">{{ fmtPct(s.pick_change) }}</td>
                  <td :class="getColor(s.main_net_inflow || 0)">{{ fmtAmount((s.main_net_inflow || 0)/10000) }}</td>
                  <td><span class="reason-text">{{ s.reason }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty">⏳ 等待 14:30 尾盘选股...</div>
        </div>

        <!-- 热门板块 -->
        <div class="card">
          <div class="card-title">📊 热门板块 TOP10</div>
          <div v-if="sectors && sectors.top && sectors.top.length > 0">
            <table class="data-table">
              <thead><tr><th>排名</th><th>板块</th><th>涨幅</th><th>涨/跌家数</th><th>领涨股</th></tr></thead>
              <tbody>
                <tr v-for="s in sectors.top.slice(0, 10)" :key="s.rank">
                  <td>{{ s.rank }}</td>
                  <td><strong>{{ s.name }}</strong></td>
                  <td :class="getColor(s.change_pct)">{{ fmtPct(s.change_pct) }}</td>
                  <td><span class="badge badge-up">{{ s.up_count }}</span>/<span class="badge badge-down">{{ s.down_count }}</span></td>
                  <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ s.leader || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty">加载中...</div>
        </div>

        <!-- 题材热度 -->
        <div class="card">
          <div class="card-title">🔥 热门题材</div>
          <div v-if="Object.keys(themes).length > 0">
            <div style="display:flex;flex-wrap:wrap;gap:8px">
              <div v-for="(v, k) in themes" :key="k" class="theme-tag">
                <strong>{{ k }}</strong>
                <span class="badge badge-up" style="margin-left:6px">{{ v.count }}只</span>
                <span :class="v.avg_zhangfu >= 0 ? 'up' : 'down'" style="font-size:11px;margin-left:4px">{{ v.avg_zhangfu >= 0 ? '+' : '' }}{{ v.avg_zhangfu }}%</span>
              </div>
            </div>
          </div>
          <div v-else class="empty">加载中...</div>
        </div>
      </div>
    </div>

    <!-- 个股详情弹窗 -->
    <div v-if="detailStock" class="modal-overlay" @click.self="detailStock = null">
      <div class="modal">
        <div class="modal-title">
          <span>{{ detailStock.name }} ({{ detailStock.code }})</span>
          <button class="modal-close" @click="detailStock = null">✕</button>
        </div>

        <div style="margin-bottom:12px">
          <span class="badge" :class="detailType === 'morning' ? 'badge-up' : 'badge-info'">
            {{ detailType === 'morning' ? '🌅 早盘精选' : '🌆 尾盘精选' }}
          </span>
          <span style="margin-left:8px;color:#888;font-size:13px">{{ detailStock.pick_date }}</span>
        </div>

        <div class="grid-2" style="margin-bottom:12px">
          <div><span style="color:#888">选股价：</span><strong>{{ detailStock.pick_price }}</strong></div>
          <div><span style="color:#888">选股涨幅：</span><strong :class="getColor(detailStock.pick_change)">{{ fmtPct(detailStock.pick_change) }}</strong></div>
          <div><span style="color:#888">现价：</span><strong>{{ getRT(detailStock,'price') }}</strong></div>
          <div><span style="color:#888">实时涨幅：</span><strong :class="getColor(getRT(detailStock,'change_pct'))">{{ fmtPct(getRT(detailStock,'change_pct')) }}</strong></div>
          <div><span style="color:#888">成交额：</span><strong>{{ fmtAmount(getRT(detailStock,'amount_wan')) }}</strong></div>
          <div><span style="color:#888">换手率：</span><strong>{{ fmtPct(getRT(detailStock,'turnover_pct')) }}</strong></div>
        </div>

        <div v-if="detailStock.reason" style="margin-top:8px;padding:10px;background:#15152a;border-radius:6px">
          <div style="color:#f0b90b;font-size:13px;margin-bottom:4px">选股理由</div>
          <div style="color:#aaa;font-size:13px">{{ detailStock.reason }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const todayData = ref({ morning: [], afternoon_today: [], afternoon_yesterday: [] })
const sectors = ref({ top: [] })
const themes = ref({})
const indexData = ref({})
const detailStock = ref(null)
const detailType = ref('morning')

const indexLabels = { 'sh': '上证指数', 'hs300': '沪深300', 'cyb': '创业板指' }

let pollTimer = null

function getRT(stock, field) {
  return stock.realtime?.[field] ?? stock[field] ?? 0
}

function getProfit(stock) {
  const cur = getRT(stock, 'price')
  const base = stock.pick_price
  if (base && base > 0 && cur > 0) {
    return ((cur - base) / base * 100).toFixed(2)
  }
  return 0
}

function getColor(v) {
  if (v > 0) return 'up'
  if (v < 0) return 'down'
  return 'flat'
}

function fmtPct(v) {
  v = parseFloat(v) || 0
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

function fmtAmount(v) {
  v = parseFloat(v) || 0
  if (v >= 10000) return (v / 10000).toFixed(1) + '亿'
  if (v >= 1) return v.toFixed(0) + '万'
  return v.toFixed(0)
}

async function fetchData() {
  try {
    const r = await fetch('/api/today')
    const d = await r.json()
    todayData.value = d
    if (d.sectors) sectors.value = d.sectors
    if (d.themes) themes.value = d.themes
    if (d.index) indexData.value = d.index
  } catch (e) {
    console.error('获取数据失败:', e)
  }
}

function showDetail(stock, type) {
  detailStock.value = stock
  detailType.value = type
}

onMounted(() => {
  fetchData()
  pollTimer = setInterval(fetchData, 30000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.theme-tag {
  background: #15152a;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
}
</style>
