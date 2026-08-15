<script setup>
import { ref, computed, watch, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'
import PhanTrang from '../components/PhanTrang.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

// ---------------------------------------------------------------------
// E6/QT10 — bộ chuyển "Theo HĐNT | Mua lẻ" (F-03/F-21). Chỉ hiện khi khách
// được bật `Customer.custom_cho_phep_mua_le`.
//
// `portal_me()` giờ TRẢ THẲNG cờ này (`cho_phep_mua_le` — thêm ở review E6
// phần B round 1, dọn dẹp ở round 2). Bản trước không có cờ này nên phải dò
// bằng cách gọi thử `portal_catalog_ban_le` lúc vào trang và đọc mã lỗi
// (403 `khong_duoc_mua_le` → ẩn bộ chuyển) — một round-trip THỪA chỉ để
// biết có nên hiện một cái nút hay không, và còn sai trong lúc chờ (bộ
// chuyển nhấp nháy ẩn→hiện nếu API chậm). `mucLeChoPhep` giờ là `computed`
// từ `store.me`, không còn là state tự quản lý bằng try/catch nữa —
// `portal_catalog_ban_le` chỉ còn gọi để LẤY DỮ LIỆU khi khách thật sự vào
// ngăn Mua lẻ (`loadLe()` bên dưới), không còn kiêm luôn việc dò quyền.
const mode = ref('hd') // 'hd' | 'le'
const mucLeChoPhep = computed(() => !!store.me?.cho_phep_mua_le)

// ---------------------------------------------------------------------
// Ngăn Theo HĐNT — [Hiện có], KHÔNG đổi hành vi so với bản trước E6.
// ---------------------------------------------------------------------
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

// Brief 2026-08-15 (phân trang) — ngăn Theo HĐNT lọc PHÍA CLIENT (danh mục
// đã tải hết về một lần, theo hạn mức hợp đồng — không phải server-side
// như ngăn Mua lẻ), nên phân trang ở đây cũng CẮT PHÍA CLIENT trên mảng
// `filtered` đã có sẵn, không gọi thêm API.
const trangHd = ref(1)
const soDongHd = ref(20)
const filteredTrang = computed(() => {
  const bd = (trangHd.value - 1) * soDongHd.value
  return filtered.value.slice(bd, bd + soDongHd.value)
})
// Đổi bộ lọc (tìm/nhóm/hợp đồng) hoặc đổi số dòng/trang -> về lại trang 1,
// nếu không khách có thể đứng ở một trang không còn dữ liệu.
watch([search, group, selected], () => {
  trangHd.value = 1
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
      `Không đặt được: ${it.item_code} chỉ còn ${left} ${it.uom} theo hạn mức hợp đồng khung.`,
      'error'
    )
    return
  }
  store.addToCart(it, qty)
  showToast(`Đã thêm ${qty} ${it.uom} · ${it.item_name} vào giỏ hàng`)
  qtys[it.item_code] = boiSo(it)
}

// ---------------------------------------------------------------------
// Ngăn Mua lẻ [MỚI — F-21/QT10]. Danh mục tìm server-side (`tim_kiem`),
// KHÔNG lọc phía client như ngăn HĐNT — endpoint không trả toàn bộ mặt hàng
// một lần (BR-R6: không phơi toàn bộ kho hàng Miyano), tìm rỗng phải hỏi lại.
// ---------------------------------------------------------------------
const leItems = ref([])
const leLoading = ref(false)
const leError = ref('')
const leQtys = reactive({})
let leSearchTimer = null

const leTong = ref(0)
// Brief 2026-08-15 (phân trang) — ĐỔI nút "Tải thêm" (tích luỹ dòng) sang
// PhanTrang.vue (cùng bộ phân trang với cả cổng): mỗi trang là MỘT lượt
// gọi API độc lập, không còn nối chồng danh sách.
const leTrang = ref(1)
const leSoDong = ref(20)

function availableLeQty(code) {
  return leQtys[code] ?? 1
}

async function loadLe() {
  // `mucLeChoPhep` giờ đến từ `store.me.cho_phep_mua_le` (dữ liệu THẬT,
  // không phải suy từ kết quả gọi này) — hàm này chỉ còn việc NẠP DANH MỤC
  // cho ngăn Mua lẻ, không kiêm việc dò quyền nữa (xem ghi chú ở khai báo
  // `mucLeChoPhep` phía trên).
  leLoading.value = true
  leError.value = ''
  try {
    const res = await api.call('portal_catalog_ban_le', {
      tim_kiem: search.value.trim() || undefined,
      start: (leTrang.value - 1) * leSoDong.value,
      limit: leSoDong.value,
    })
    leItems.value = res.items || []
    leTong.value = res.tong || 0
    leItems.value.forEach((it) => {
      if (!(it.item_code in leQtys)) leQtys[it.item_code] = 1
    })
  } catch (e) {
    if (e.name === 'PermissionError') {
      // Vẫn có thể xảy ra (hiếm): cờ vừa bị tắt giữa lúc trang đã mở và lúc
      // khách bấm vào ngăn Mua lẻ (server luôn kiểm lại, NL-10.1) — về lại
      // ngăn HĐNT thay vì hiện một danh mục rỗng dưới một bộ chuyển vẫn hiện.
      if (mode.value === 'le') mode.value = 'hd'
      leError.value = e.message || 'Đơn vị của bạn chưa được bật chế độ Mua lẻ.'
    } else {
      // Lỗi khác (mạng, server 5xx...) — hiện thông điệp thật tại ngăn Mua
      // lẻ, không chôn trong một nhánh không ai vào được.
      leError.value = e.message || 'Không tải được danh mục mua lẻ.'
    }
  } finally {
    leLoading.value = false
  }
}

function addLe(it) {
  const qty = Math.max(1, parseInt(leQtys[it.item_code]) || 1)
  // §3.3 — KHÔNG truyền `rate`/`vat_pct`: endpoint không trả giá nữa.
  store.addToCartLe(
    { item_code: it.item_code, item_name: it.ten, uom: it.dvt },
    qty
  )
  showToast(`Đã thêm ${qty} ${it.dvt} · ${it.ten} vào giỏ mua lẻ`)
  leQtys[it.item_code] = 1
}

// Bấm nhãn "Có trong HĐNT" (BR-R7/NL-10.7) → chuyển chế độ, giữ nguyên
// mã hàng làm bộ lọc để khách thấy ngay đúng dòng đó ở danh mục HĐNT.
function chuyenSangHdnt(itemCode) {
  mode.value = 'hd'
  search.value = itemCode
}

function setMode(m) {
  mode.value = m
}

// Nạp lại MỖI LẦN chuyển sang ngăn Mua lẻ, không chỉ lần đầu — nếu không, gõ
// từ khoá trong lúc đang ở ngăn HĐNT rồi chuyển sang Mua lẻ sẽ giữ nguyên
// kết quả cũ (lần dò quyền lúc vào trang) trong khi ô tìm kiếm đã đổi chữ,
// bảng và ô tìm kiếm lệch nhau.
watch(mode, (m) => {
  if (m === 'le') {
    leTrang.value = 1
    loadLe()
  }
})

// Debounce 300ms (FormSpec §1.2) — chỉ áp cho ngăn Mua lẻ, ngăn HĐNT lọc
// tức thời phía client (không cần debounce một phép lọc trong bộ nhớ).
watch(search, () => {
  if (mode.value !== 'le') return
  clearTimeout(leSearchTimer)
  // Đổi từ khoá tìm -> về lại trang 1 (trang cũ có thể không còn khớp kết
  // quả mới). Luôn gọi loadLe() lại sau debounce dù `leTrang` có đổi hay
  // không (đang sẵn ở trang 1 thì gán lại không tự kích hoạt watch bên
  // dưới) — chốt cuối là lần gọi debounce này, không phải watch trang.
  leTrang.value = 1
  leSearchTimer = setTimeout(() => loadLe(), 300)
})

// Brief 2026-08-15 (phân trang) — điều hướng trang/đổi số dòng của
// PhanTrang.vue (ngăn Mua lẻ) phải gọi lại API ngay, không debounce (khác
// gõ tìm kiếm ở trên).
watch([leTrang, leSoDong], () => loadLe())

// §3.4 — khối "hàng chưa có trong kho, cần đặt ngoài". Mở sẵn khi tìm không
// ra kết quả: đúng chỗ và đúng ý định mà nút "Gửi yêu cầu cho Miyano" cũ
// phục vụ, nhưng ở lại trên chính phiếu mua thay vì đẩy sang chứng từ khác.
const dnMoKhoi = ref(false)

const timKhongRa = computed(
  () => mode.value === 'le' && !leLoading.value && !leError.value && leTong.value === 0
)

watch(timKhongRa, (khong) => {
  if (!khong) return
  dnMoKhoi.value = true
  if (!store.cartDatNgoai.length) {
    store.themDongDatNgoai({ ten_hang: search.value.trim() })
  }
})

function themDongTrong() {
  store.themDongDatNgoai({})
  dnMoKhoi.value = true
}

onMounted(async () => {
  if (route.query.search) search.value = String(route.query.search)
  try {
    // `portal_me` (cho cờ `cho_phep_mua_le`) và `portal_contracts` song
    // song — không còn cần dò quyền mua lẻ bằng cách gọi thử
    // `portal_catalog_ban_le` nữa (xem ghi chú ở khai báo `mucLeChoPhep`).
    const [meRes, contractsRes] = await Promise.all([
      store.me ? Promise.resolve(store.me) : api.call('portal_me'),
      api.call('portal_contracts'),
    ])
    if (!store.me) store.setMe(meRes)
    contracts.value = contractsRes || []
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
  // Nạp danh mục Mua lẻ CHỈ khi khách thật sự được bật cờ — đỡ một
  // round-trip (và một lượt 403 vô nghĩa) cho phần lớn khách CHƯA bật.
  if (mucLeChoPhep.value) loadLe()
})

watch(selected, loadItems)
</script>

<template>
  <div v-if="loading" class="loading">Đang tải…</div>
  <div v-else>
    <div class="topbar">
      <div v-if="!isMobile">
        <h2>Đặt hàng</h2>
        <div class="sub">
          {{ mode === 'le' ? 'Giá bán lẻ ngoài hợp đồng khung' : 'Giá & danh mục theo hợp đồng đã ký — không áp dụng cho mặt hàng ngoài hợp đồng' }}
        </div>
      </div>
      <div v-if="mucLeChoPhep" class="seg">
        <button :class="{ on: mode === 'hd' }" @click="setMode('hd')">Theo hợp đồng khung</button>
        <button :class="{ on: mode === 'le' }" @click="setMode('le')">Mua lẻ <span class="newtag">MỚI</span></button>
      </div>
    </div>

    <div v-if="mode === 'le'" class="note note-b">
      ⚠ <b>Giá bán lẻ ngoài hợp đồng khung</b> — đơn cần Miyano xác nhận trước khi giao. Không áp dụng hạn mức.
    </div>

    <!-- Bộ lọc chung -->
    <div class="card" style="margin-bottom: 14px">
      <div class="flex" style="flex-wrap: wrap; align-items: flex-end">
        <div v-if="mode === 'hd' && contracts.length" style="min-width: 260px; flex: 1">
          <label class="tag">Hợp đồng khung</label>
          <select v-model="selected">
            <option v-for="c in contracts" :key="c.name" :value="c.name">
              {{ c.name }} ({{ fmtDate(c.from_date) }}–{{ fmtDate(c.to_date) }}) – còn hiệu lực
            </option>
          </select>
        </div>
        <div style="min-width: 220px; flex: 1">
          <label class="tag">Tìm kiếm{{ mode === 'le' ? ' (không dấu)' : '' }}</label>
          <input v-model="search" placeholder="Mã hoặc tên mặt hàng..." />
        </div>
        <div v-if="mode === 'hd' && groups.length" style="min-width: 170px">
          <label class="tag">Nhóm hàng</label>
          <select v-model="group">
            <option value="">Tất cả</option>
            <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- ============ NGĂN THEO HĐNT ============ -->
    <template v-if="mode === 'hd'">
      <div v-if="!contracts.length" class="empty">Chưa có hợp đồng khung còn hiệu lực.</div>
      <template v-else>
        <div v-if="error" class="empty">{{ error }}</div>
        <div v-else-if="loadingItems" class="loading">Đang tải danh mục…</div>
        <div v-else-if="!filtered.length" class="empty">
          Không có mặt hàng khớp — mặt hàng ngoài hợp đồng khung không hiển thị.
        </div>

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
              <tr v-for="it in filteredTrang" :key="it.item_code">
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
          <PhanTrang v-model:trang="trangHd" v-model:so-dong="soDongHd" :tong="filtered.length" />
        </div>

        <!-- MOBILE: thẻ -->
        <template v-else>
          <div v-for="it in filteredTrang" :key="it.item_code" class="card item mb10">
            <div class="nm">{{ it.item_code }} · {{ it.item_name }}</div>
            <div class="tag" style="margin: 2px 0 6px">{{ it.item_group }} · VAT {{ it.vat_pct }}% · {{ it.uom }}</div>
            <div class="sb">
              <span class="pr">{{ fmtVND(it.rate) }}</span>
              <span v-if="it.khong_gioi_han" class="tag tag-kgh">Không giới hạn</span>
              <span v-else-if="it.remaining <= 0" class="tag tag-het">Hết hạn mức</span>
              <span v-else class="tag">còn {{ it.remaining }}/{{ it.total }} {{ it.uom }}</span>
            </div>
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
          <PhanTrang v-model:trang="trangHd" v-model:so-dong="soDongHd" :tong="filtered.length" />
        </template>
      </template>
    </template>

    <!-- ============ NGĂN MUA LẺ [MỚI — F-21] ============ -->
    <template v-else>
      <div v-if="leError" class="empty">{{ leError }}</div>
      <div v-else-if="leLoading" class="loading">Đang tải danh mục…</div>
      <div v-else-if="!leItems.length" class="empty">Không có mặt hàng khớp tìm kiếm.</div>

      <!-- DESKTOP: bảng -->
      <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Mã</th><th>Tên / quy cách</th><th>ĐVT</th>
              <th>Tình trạng</th>
              <th style="width: 120px">Số lượng</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in leItems" :key="it.item_code" :style="it.thuoc_hdnt ? 'opacity:.6' : ''">
              <td><b>{{ it.item_code }}</b></td>
              <td>{{ it.ten }}<br /><span v-if="it.quy_cach" class="tag">{{ it.quy_cach }}</span></td>
              <td>{{ it.dvt }}</td>
              <template v-if="it.thuoc_hdnt">
                <td colspan="3">
                  <a href="#" @click.prevent="chuyenSangHdnt(it.item_code)">
                    <span class="badge b-blue">Có trong hợp đồng khung — đặt ở chế độ Theo hợp đồng khung</span>
                  </a>
                </td>
              </template>
              <template v-else-if="!it.san_sang_ban">
                <td colspan="3">
                  <span class="badge b-gray">Miyano đang cập nhật — vui lòng liên hệ</span>
                </td>
              </template>
              <template v-else>
                <td><span class="badge" :class="it.trang_thai_hang === 'Còn hàng' ? 'b-green' : 'b-gray'">{{ it.trang_thai_hang }}</span></td>
                <td>
                  <div class="step">
                    <button @click="leQtys[it.item_code] = Math.max(1, availableLeQty(it.item_code) - 1)">−</button>
                    <input v-model="leQtys[it.item_code]" inputmode="numeric" />
                    <button @click="leQtys[it.item_code] = availableLeQty(it.item_code) + 1">+</button>
                  </div>
                </td>
                <td><button class="btn btn-sm" @click="addLe(it)">+ Giỏ lẻ</button></td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="it in leItems" :key="it.item_code" class="card item mb10" :style="it.thuoc_hdnt ? 'opacity:.6' : ''">
          <div class="nm">{{ it.item_code }} · {{ it.ten }}</div>
          <div class="tag" style="margin: 2px 0 6px">{{ it.quy_cach ? it.quy_cach + ' · ' : '' }}{{ it.dvt }}</div>

          <template v-if="it.thuoc_hdnt">
            <a href="#" @click.prevent="chuyenSangHdnt(it.item_code)">
              <span class="badge b-blue">Có trong hợp đồng khung — đặt ở chế độ Theo hợp đồng khung</span>
            </a>
          </template>
          <template v-else-if="!it.san_sang_ban">
            <div class="sb"><span class="badge b-gray">Miyano đang cập nhật — vui lòng liên hệ</span></div>
          </template>
          <template v-else>
            <div class="sb">
              <span class="badge" :class="it.trang_thai_hang === 'Còn hàng' ? 'b-green' : 'b-gray'">{{ it.trang_thai_hang }}</span>
            </div>
            <div class="sb" style="margin-top: 10px">
              <div class="step">
                <button @click="leQtys[it.item_code] = Math.max(1, availableLeQty(it.item_code) - 1)">−</button>
                <input v-model="leQtys[it.item_code]" inputmode="numeric" />
                <button @click="leQtys[it.item_code] = availableLeQty(it.item_code) + 1">+</button>
              </div>
              <button class="btn btn-sm" @click="addLe(it)">+ Thêm vào giỏ lẻ</button>
            </div>
          </template>
        </div>
      </template>

      <PhanTrang v-model:trang="leTrang" v-model:so-dong="leSoDong" :tong="leTong" />

      <div class="card" style="margin-top: 12px">
        <div class="sb" style="cursor: pointer" @click="dnMoKhoi = !dnMoKhoi">
          <b>Không tìm thấy vật tư cần mua?</b>
          <span>{{ dnMoKhoi ? '▾' : '▸' }}</span>
        </div>
        <p class="tag" style="margin: 4px 0 0">
          Ghi thẳng vào đây. Miyano sẽ tìm nguồn và báo giá cho bạn.
        </p>

        <template v-if="dnMoKhoi">
          <div v-for="(d, i) in store.cartDatNgoai" :key="i" class="card mb10" style="margin-top: 10px">
            <div class="field">
              <label>Tên hàng <span class="req">*</span></label>
              <input v-model="d.ten_hang" placeholder="VD: Găng tay nitrile không bột size M" />
            </div>
            <div class="sb" style="gap: 8px">
              <div class="field" style="flex: 1">
                <label>ĐVT <span class="req">*</span></label>
                <input v-model="d.dvt" placeholder="Hộp" />
              </div>
              <div class="field" style="flex: 1">
                <label>Số lượng <span class="req">*</span></label>
                <input v-model="d.so_luong" inputmode="numeric" />
              </div>
            </div>
            <div class="field">
              <label>Ghi chú</label>
              <input v-model="d.ghi_chu" placeholder="Quy cách, hãng mong muốn…" />
            </div>
            <button class="btn-o btn-sm" @click="store.xoaDongDatNgoai(i)">Xoá dòng</button>
          </div>

          <button class="btn-o" style="width: 100%" @click="themDongTrong">+ Thêm dòng</button>
        </template>
      </div>
    </template>

    <!-- Sticky cart bar (mobile) — `store.cartCount` là SỐ DÒNG, không phải
         tiền, cộng CẢ BA phần: hai ngăn giỏ (Theo hợp đồng khung, Mua lẻ)
         VÀ mảng đặt ngoài chưa có mã (§3.4) — xem getter `cartCount`. -->
    <div v-if="isMobile && store.cartCount" class="cartbar">
      <button class="btn" @click="router.push('/cart')">
        <span>🧺 {{ store.cartCount }} mặt hàng</span>
        <span>Xem giỏ ›</span>
      </button>
    </div>
  </div>
</template>
