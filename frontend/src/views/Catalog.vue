<script setup>
import { ref, computed, watch, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const loadingItems = ref(false)
const error = ref('')
const contracts = ref([])
const selected = ref('')
const items = ref([])
const search = ref('')
const group = ref('')
const qtys = reactive({}) // item_code → số lượng đang chọn ở stepper

const groups = computed(() => {
  const s = new Set()
  items.value.forEach((it) => it.item_group && s.add(it.item_group))
  return Array.from(s)
})

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return items.value.filter((it) => {
    if (group.value && it.item_group !== group.value) return false
    if (!q) return true
    return (
      it.item_code.toLowerCase().includes(q) ||
      (it.item_name || '').toLowerCase().includes(q)
    )
  })
})

function usedPct(it) {
  return it.total ? Math.round((it.used / it.total) * 100) : 0
}
function inCart(code) {
  return store.cart[code]?.qty || 0
}
// Hạn mức còn có thể thêm = remaining (API) trừ số đã có trong giỏ.
// `remaining === null` nghĩa là KHÔNG GIỚI HẠN (BR-O15) — trả `null` chứ
// không phải một con số lớn, để nơi gọi phải xử lý trường hợp này tường minh.
// Bản trước viết `it.remaining || 0`, biến null thành 0 và khoá sạch mặt hàng
// khai hạn mức 0 — đúng ngược quy ước.
function availableToAdd(it) {
  if (it.khong_gioi_han) return null
  return Math.max(0, (it.remaining || 0) - inCart(it.item_code))
}
// Bội số quy cách đóng gói (BR-O11). 0/rỗng = không ràng buộc.
function boiSo(it) {
  return parseInt(it.boi_so_dat) || 1
}

async function loadItems() {
  if (!selected.value) return
  loadingItems.value = true
  error.value = ''
  try {
    items.value = (await api.call('portal_catalog', { contract: selected.value })) || []
    items.value.forEach((it) => {
      // Khởi tạo bằng ĐÚNG một lô: mặt hàng bán theo hộp 10 thì mặc định 1 sẽ
      // luôn sai bội số ngay từ lần bấm đầu tiên.
      if (!(it.item_code in qtys)) qtys[it.item_code] = boiSo(it)
    })
    store.setContract(selected.value)
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục hợp đồng.'
  } finally {
    loadingItems.value = false
  }
}

// Bước nhảy của stepper = bội số quy cách, không phải 1 (BR-O11).
function stepDown(code) {
  const b = boiSo(itemTheoMa(code))
  qtys[code] = Math.max(b, (parseInt(qtys[code]) || b) - b)
}
function stepUp(code) {
  const b = boiSo(itemTheoMa(code))
  qtys[code] = (parseInt(qtys[code]) || 0) + b
}
function itemTheoMa(code) {
  return items.value.find((i) => i.item_code === code) || {}
}
// Gõ tay xong thì kéo về bội số hợp lệ gần nhất, LÀM TRÒN LÊN — giống hệt
// quy tắc server (`portal_dat_hang.kiem_boi_so`). Client chỉ là UX; server
// vẫn là chốt cuối và sẽ báo cùng một thông điệp nếu lọt qua.
function normalize(code) {
  const b = boiSo(itemTheoMa(code))
  const n = Math.max(b, parseInt(qtys[code]) || b)
  qtys[code] = Math.ceil(n / b) * b
}

function add(it) {
  normalize(it.item_code)
  const qty = parseInt(qtys[it.item_code])
  const left = availableToAdd(it)
  // `left === null` = không giới hạn, bỏ qua phép so.
  if (left !== null && qty > left) {
    // FormSpec §1.3 cấm `alert()` của trình duyệt — lỗi hiển thị bằng toast
    // và dòng chữ tại chỗ, không phải hộp thoại chặn cả trang.
    showToast(
      `Không đặt được: ${it.item_code} chỉ còn ${left} ${it.uom} theo hạn mức HĐNT.`,
      'error'
    )
    return
  }
  store.addToCart(it, qty)
  showToast(`Đã thêm ${qty} ${it.uom} · ${it.item_name} vào giỏ hàng`)
  qtys[it.item_code] = boiSo(it)
}

onMounted(async () => {
  try {
    contracts.value = (await api.call('portal_contracts')) || []
    if (contracts.value.length) {
      selected.value =
        store.contract && contracts.value.some((c) => c.name === store.contract)
          ? store.contract
          : contracts.value[0].name
      await loadItems()
    }
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách hợp đồng.'
  } finally {
    loading.value = false
  }
})

watch(selected, loadItems)
</script>

<template>
  <div v-if="loading" class="loading">Đang tải…</div>
  <div v-else>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Đặt hàng theo Hợp đồng nguyên tắc</h2>
        <div class="sub">Giá &amp; danh mục theo hợp đồng đã ký – không áp dụng cho mặt hàng ngoài hợp đồng</div>
      </div>
    </div>

    <div v-if="!contracts.length" class="empty">Chưa có hợp đồng nguyên tắc còn hiệu lực.</div>

    <template v-else>
      <!-- Bộ lọc -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="flex" style="flex-wrap: wrap; align-items: flex-end">
          <div style="min-width: 260px; flex: 1">
            <label class="tag">Hợp đồng nguyên tắc</label>
            <select v-model="selected">
              <option v-for="c in contracts" :key="c.name" :value="c.name">
                {{ c.name }} ({{ fmtDate(c.from_date) }}–{{ fmtDate(c.to_date) }}) – còn hiệu lực
              </option>
            </select>
          </div>
          <div style="min-width: 220px; flex: 1">
            <label class="tag">Tìm kiếm</label>
            <input v-model="search" placeholder="Mã hoặc tên mặt hàng..." />
          </div>
        </div>
        <div class="chips" style="margin-top: 12px; margin-bottom: 0">
          <button class="chip" :class="{ on: group === '' }" @click="group = ''">Tất cả</button>
          <button
            v-for="g in groups"
            :key="g"
            class="chip"
            :class="{ on: group === g }"
            @click="group = g"
          >
            {{ g }}
          </button>
        </div>
      </div>

      <div v-if="error" class="empty">{{ error }}</div>
      <div v-else-if="loadingItems" class="loading">Đang tải danh mục…</div>
      <div v-else-if="!filtered.length" class="empty">Không có mặt hàng phù hợp.</div>

      <!-- DESKTOP: bảng -->
      <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Mã</th>
              <th>Tên mặt hàng / quy cách</th>
              <th>ĐVT</th>
              <th class="right">Đơn giá (chưa VAT)</th>
              <th style="min-width: 150px">Hạn mức còn lại</th>
              <th style="width: 120px">Số lượng</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in filtered" :key="it.item_code">
              <td><b>{{ it.item_code }}</b></td>
              <td>
                {{ it.item_name }}<br />
                <span class="tag">{{ it.item_group }} · VAT {{ it.vat_pct }}%</span>
              </td>
              <td>{{ it.uom }}</td>
              <td class="right">{{ fmtVND(it.rate) }}</td>
              <td>
                <!-- BR-O15 / NL-1.11: hạn mức khai 0 = KHÔNG GIỚI HẠN, phải
                     nhìn khác hẳn "Hết hạn mức" (NL-1.2). Không thanh tiến
                     độ, không cảnh báo 80% — không có trần thì không có % -->
                <template v-if="it.khong_gioi_han">
                  <span class="tag tag-kgh">Không giới hạn</span>
                  <div class="muted sm">đã đặt {{ it.used }} {{ it.uom }}</div>
                </template>
                <template v-else-if="it.remaining <= 0">
                  <span class="tag tag-het">Hết hạn mức</span>
                </template>
                <template v-else>
                  còn {{ it.remaining }}/{{ it.total }} {{ it.uom }}
                  <div class="bar">
                    <i :style="{ width: Math.min(usedPct(it), 100) + '%', background: usedPct(it) >= 80 ? 'var(--red)' : '' }"></i>
                  </div>
                  <span v-if="usedPct(it) >= 80" class="warn">Sắp hết hạn mức</span>
                </template>
              </td>
              <td>
                <div class="step">
                  <button @click="stepDown(it.item_code)">−</button>
                  <input v-model="qtys[it.item_code]" @change="normalize(it.item_code)" inputmode="numeric" />
                  <button @click="stepUp(it.item_code)">+</button>
                </div>
                <div v-if="boiSo(it) > 1" class="muted sm">bội số {{ boiSo(it) }}</div>
              </td>
              <td>
                <button
                  class="btn btn-sm"
                  :disabled="availableToAdd(it) !== null && availableToAdd(it) <= 0"
                  @click="add(it)"
                >+ Giỏ</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="it in filtered" :key="it.item_code" class="card item mb10">
          <div class="nm">{{ it.item_code }} · {{ it.item_name }}</div>
          <div class="tag" style="margin: 2px 0 6px">{{ it.item_group }} · VAT {{ it.vat_pct }}% · {{ it.uom }}</div>
          <div class="sb">
            <span class="pr">{{ fmtVND(it.rate) }}</span>
            <span v-if="it.khong_gioi_han" class="tag tag-kgh">Không giới hạn</span>
            <span v-else-if="it.remaining <= 0" class="tag tag-het">Hết hạn mức</span>
            <span v-else class="tag">còn {{ it.remaining }}/{{ it.total }} {{ it.uom }}</span>
          </div>
          <!-- Không thanh tiến độ cho dòng không giới hạn: không có trần thì
               không có phần trăm để vẽ (BR-O15). -->
          <template v-if="!it.khong_gioi_han">
            <div class="bar" style="margin: 6px 0">
              <i :style="{ width: Math.min(usedPct(it), 100) + '%', background: usedPct(it) >= 80 ? 'var(--red)' : '' }"></i>
            </div>
            <span v-if="usedPct(it) >= 80" class="warn">Sắp hết hạn mức</span>
          </template>
          <div v-else class="muted sm" style="margin: 6px 0">
            đã đặt {{ it.used }} {{ it.uom }}
          </div>
          <div class="sb" style="margin-top: 10px">
            <div class="step">
              <button @click="stepDown(it.item_code)">−</button>
              <input v-model="qtys[it.item_code]" @change="normalize(it.item_code)" inputmode="numeric" />
              <button @click="stepUp(it.item_code)">+</button>
            </div>
            <button
              class="btn btn-sm"
              :disabled="availableToAdd(it) !== null && availableToAdd(it) <= 0"
              @click="add(it)"
            >+ Thêm vào giỏ</button>
          </div>
          <div v-if="boiSo(it) > 1" class="muted sm">Đặt theo bội số {{ boiSo(it) }} {{ it.uom }}</div>
        </div>
      </template>
    </template>

    <!-- Sticky cart bar (mobile) -->
    <div v-if="isMobile && store.cartCount" class="cartbar">
      <button class="btn" @click="router.push('/cart')">
        <span>🧺 {{ store.cartCount }} mặt hàng</span>
        <span>{{ fmtVND(store.cartTotal) }}</span>
        <span>Xem giỏ ›</span>
      </button>
    </div>
  </div>
</template>
