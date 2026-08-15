<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import {
  NXT_COLUMNS, NXT_LOT_COLUMNS, THE_KHO_COLUMNS, CANH_BAO_COLUMNS,
} from '../kho-bao-cao-columns'
import PhanTrang from '../components/PhanTrang.vue'

const isMobile = useIsMobile()

// Brief 2026-08-15 (phân trang) — MỘT bộ trang/số dòng/tong DÙNG CHUNG cho
// cả năm tab (chỉ một tab hiện trên màn tại một thời điểm — xem chuỗi
// v-if/v-else-if của template). Xuất Excel (`kho_bao_cao_excel`) KHÔNG
// dùng các state này — nó gọi thẳng `reports.*_rows()` ở server, luôn
// xuất TOÀN BỘ bất kể trang JSON đang xem (đã có test canh:
// test_phan_trang.TestBaoCaoExcelLuonXuatToanBo).
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

// --- Khoảng ngày: mặc định tháng hiện tại ---
function pad(n) {
  return String(n).padStart(2, '0')
}
function isoDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const now = new Date()
const tuNgay = ref(isoDate(new Date(now.getFullYear(), now.getMonth(), 1)))
const denNgay = ref(isoDate(now))

const TABS = [
  { key: 'nxt', label: 'Nhập - Xuất - Tồn' },
  { key: 'the_kho', label: 'Thẻ kho' },
  { key: 'canh_bao', label: 'Cảnh báo hạn dùng' },
  { key: 'dot', label: 'NXT theo đợt hàng' },
  { key: 'cp', label: 'Cấp phát theo khoa' },
]
const tab = ref('nxt')

function fmtQty(v) {
  return Number(v || 0).toLocaleString('vi-VN')
}

// --- N-X-T ---
const nxtLoading = ref(false)
const nxtError = ref('')
const nxtRows = ref([])
const search = ref('')
let searchTimer = null

const expanded = reactive({}) // vat_tu -> bool
const lotRows = reactive({}) // vat_tu -> { loading, error, data }

async function loadNXT() {
  nxtLoading.value = true
  nxtError.value = ''
  try {
    const out = await api.callKho('kho_bao_cao_nxt', {
      tu_ngay: tuNgay.value, den_ngay: denNgay.value, tim: search.value || undefined,
      start: (trang.value - 1) * soDong.value, limit: soDong.value,
    })
    nxtRows.value = out.rows || []
    tong.value = out.tong || 0
  } catch (e) {
    nxtError.value = e.message || 'Không tải được báo cáo Nhập - Xuất - Tồn.'
  } finally {
    nxtLoading.value = false
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  trang.value = 1
  searchTimer = setTimeout(loadNXT, 300)
}

function toggleLot(row) {
  const key = row.vat_tu
  expanded[key] = !expanded[key]
  if (expanded[key] && !lotRows[key]) {
    lotRows[key] = { loading: true, error: '', data: [] }
    api
      .callKho('kho_bao_cao_nxt', { tu_ngay: tuNgay.value, den_ngay: denNgay.value, vat_tu: key })
      .then((out) => {
        lotRows[key].data = out.rows || []
      })
      .catch((e) => {
        lotRows[key].error = e.message || 'Không tải được chi tiết theo lô.'
      })
      .finally(() => {
        lotRows[key].loading = false
      })
  }
}

// --- Thẻ kho ---
const vatTuList = ref([])
const vatTuChon = ref('')
const theKhoLoading = ref(false)
const theKhoError = ref('')
const theKhoRows = ref([])

async function loadVatTuList() {
  try {
    vatTuList.value = await api.callKho('kho_vat_tu_list')
  } catch (e) {
    // Chọn vật tư sẽ trống nếu lỗi — không chặn các tab khác.
  }
}

async function loadTheKho() {
  if (!vatTuChon.value) {
    theKhoRows.value = []
    tong.value = 0
    return
  }
  theKhoLoading.value = true
  theKhoError.value = ''
  try {
    const res = await api.callKho('kho_the_kho', {
      vat_tu: vatTuChon.value, tu_ngay: tuNgay.value, den_ngay: denNgay.value,
      start: (trang.value - 1) * soDong.value, limit: soDong.value,
    })
    theKhoRows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    theKhoError.value = e.message || 'Không tải được thẻ kho.'
  } finally {
    theKhoLoading.value = false
  }
}

// --- Cảnh báo hạn dùng ---
const soNgay = ref(90)
const canhBaoLoading = ref(false)
const canhBaoError = ref('')
const canhBaoRows = ref([])

async function loadCanhBao() {
  canhBaoLoading.value = true
  canhBaoError.value = ''
  try {
    const res = await api.callKho('kho_canh_bao_han', {
      so_ngay: soNgay.value,
      start: (trang.value - 1) * soDong.value, limit: soDong.value,
    })
    canhBaoRows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    canhBaoError.value = e.message || 'Không tải được cảnh báo hạn dùng.'
  } finally {
    canhBaoLoading.value = false
  }
}

// --- NXT theo đợt hàng (US-E4.7/UC-44) ---
const dotLoading = ref(false)
const dotError = ref('')
const dotRows = ref([])
const dotVatTuChon = ref('') // '' = tất cả vật tư
const dotNguon = ref('') // '' = tất cả nguồn
const nccList = ref([])
// Danh mục vật tư RIÊNG cho tab này (khác vatTuList dùng chung với tab Thẻ
// kho ở trên) — tải CẢ vật tư đã tắt (ca_tat=1). Một vật tư chỉ tắt được
// khi hết tồn (vat_tu._chan_tat_khi_con_ton), tức là chính vật tư có sổ đầy
// đủ nhất; lọc active=1 sẽ khoá đúng những đợt hàng đáng xem nhất ra khỏi ô
// chọn VÀ khiến tenVatTu() hiện tên trống cho các dòng của nó. Không đụng
// tới vatTuList/loadVatTuList() (tab Thẻ kho, có sẵn từ trước, ngoài phạm vi).
const dotVatTuList = ref([])

async function loadDotVatTuList() {
  try {
    dotVatTuList.value = await api.callKho('kho_vat_tu_list', { ca_tat: 1 })
  } catch (e) {
    // Ô chọn vật tư của tab này sẽ chỉ thiếu, không chặn tab.
  }
}

async function loadNccList() {
  try {
    // ca_inactive=1: một đợt hàng cũ từ NCC đã tắt vẫn phải lọc được theo
    // đúng NCC đó — cùng lý do với dotVatTuList ở trên.
    nccList.value = await api.callKho('kho_ncc_list', { ca_inactive: 1 })
  } catch (e) {
    // Chip lọc nguồn theo NCC sẽ chỉ thiếu, không chặn tab.
  }
}

function tenVatTu(vt) {
  const v = dotVatTuList.value.find((x) => x.name === vt)
  return v ? `${v.ma_vat_tu} — ${v.ten_vat_tu}` : vt
}

async function loadDot() {
  dotLoading.value = true
  dotError.value = ''
  try {
    const res = await api.callKho('kho_bao_cao_dot', {
      tu_ngay: tuNgay.value, den_ngay: denNgay.value,
      vat_tu: dotVatTuChon.value || undefined,
      nguon: dotNguon.value || undefined,
      start: (trang.value - 1) * soDong.value, limit: soDong.value,
    })
    dotRows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    dotError.value = e.message || 'Không tải được báo cáo NXT theo đợt.'
  } finally {
    dotLoading.value = false
  }
}

// --- Cấp phát theo khoa phòng (US-E8.5/UC-56) ---
const cpLoading = ref(false)
const cpError = ref('')
const cpResult = ref({ tong_gia_tri: 0, nhom: [] })

async function loadCp() {
  cpLoading.value = true
  cpError.value = ''
  try {
    // Phân trang theo ĐƠN VỊ NHÓM (khoa phòng) — xem docstring
    // kho_bao_cao_cap_phat (api/kho.py). `tong` ở đây là số NHÓM, không
    // phải số dòng chi tiết.
    const res = await api.callKho('kho_bao_cao_cap_phat', {
      tu_ngay: tuNgay.value, den_ngay: denNgay.value,
      start: (trang.value - 1) * soDong.value, limit: soDong.value,
    })
    cpResult.value = res
    tong.value = res?.tong || 0
  } catch (e) {
    cpError.value = e.message || 'Không tải được báo cáo cấp phát theo khoa.'
  } finally {
    cpLoading.value = false
  }
}

function reload() {
  if (tab.value === 'nxt') loadNXT()
  else if (tab.value === 'the_kho') loadTheKho()
  else if (tab.value === 'canh_bao') loadCanhBao()
  else if (tab.value === 'dot') loadDot()
  else loadCp()
}

// Đổi tab/bộ lọc -> về lại trang 1 (trang cũ của tab/bộ lọc trước có thể
// không còn tồn tại ở dữ liệu mới) rồi nạp lại.
function locThayDoi() {
  trang.value = 1
  reload()
}

function chonTab(key) {
  tab.value = key
  locThayDoi()
}

watch(vatTuChon, () => {
  if (tab.value === 'the_kho') locThayDoi()
})

watch([dotVatTuChon, dotNguon], () => {
  if (tab.value === 'dot') locThayDoi()
})

// PhanTrang.vue tự đổi trang.value/soDong.value (v-model) — nghe ở đây để
// gọi lại API của tab đang xem.
watch([trang, soDong], reload)

// --- Xuất Excel: cùng bộ tham số của tab đang xem, gọi thẳng endpoint (GET,
// mở tab mới) — cùng khuôn mẫu với nút "In phiếu" ở PhieuNhapDetail.vue/
// PhieuXuatDetail.vue (kho_phieu_pdf), không qua api.callKho() vì đây là tải
// file nhị phân chứ không phải JSON.
function exportUrl() {
  const base = '/api/method/miyano_portal.api.kho.kho_bao_cao_excel'
  if (tab.value === 'nxt') {
    let u = `${base}?loai=nxt&tu_ngay=${encodeURIComponent(tuNgay.value)}&den_ngay=${encodeURIComponent(denNgay.value)}`
    if (search.value) u += `&tim=${encodeURIComponent(search.value)}`
    return u
  }
  if (tab.value === 'the_kho') {
    if (!vatTuChon.value) return ''
    return `${base}?loai=the_kho&vat_tu=${encodeURIComponent(vatTuChon.value)}`
      + `&tu_ngay=${encodeURIComponent(tuNgay.value)}&den_ngay=${encodeURIComponent(denNgay.value)}`
  }
  if (tab.value === 'canh_bao') {
    return `${base}?loai=canh_bao&so_ngay=${encodeURIComponent(soNgay.value)}`
  }
  if (tab.value === 'cp') {
    // E8: kho_bao_cao_excel CHƯA hỗ trợ loai="cap_phat" (ngoài phạm vi tối
    // thiểu của epic — xem báo cáo bàn giao). Trả rỗng để nút Excel tự ẩn
    // hành vi (xuatExcel() không mở tab nào khi url rỗng) thay vì gọi một
    // endpoint sẽ bị chặn ở whitelist _BAO_CAO_LOAI.
    return ''
  }
  // (Review E4 phần B, Gap 2 — ĐÃ SỬA) kho_bao_cao_excel giờ nhận loai="dot".
  let u = `${base}?loai=dot&tu_ngay=${encodeURIComponent(tuNgay.value)}&den_ngay=${encodeURIComponent(denNgay.value)}`
  if (dotVatTuChon.value) u += `&vat_tu=${encodeURIComponent(dotVatTuChon.value)}`
  if (dotNguon.value) u += `&nguon=${encodeURIComponent(dotNguon.value)}`
  return u
}

function xuatExcel() {
  const url = exportUrl()
  if (!url) return
  window.open(url, '_blank')
}

onMounted(() => {
  loadVatTuList()
  loadDotVatTuList()
  loadNccList()
  loadNXT()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Báo cáo kho</h2>
        <div class="sub">Nhập - Xuất - Tồn, thẻ kho theo vật tư, cảnh báo hạn dùng</div>
      </div>
    </div>
    <h2 v-else style="margin-bottom: 12px">Báo cáo kho</h2>

    <!-- Bộ lọc dùng chung: khoảng ngày -->
    <div class="card mb10">
      <div class="flex" style="flex-wrap: wrap; gap: 14px">
        <div class="field" style="margin-bottom: 0">
          <label>Từ ngày</label>
          <input type="date" v-model="tuNgay" @change="locThayDoi" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Đến ngày</label>
          <input type="date" v-model="denNgay" @change="locThayDoi" />
        </div>
        <div class="field" style="margin-bottom: 0; flex: 1; min-width: 200px" v-if="tab === 'nxt'">
          <label>Tìm vật tư</label>
          <input type="text" v-model="search" @input="onSearchInput" placeholder="Mã hoặc tên vật tư…" />
        </div>
        <div class="field" style="margin-bottom: 0" v-if="tab === 'the_kho'">
          <label>Vật tư</label>
          <select v-model="vatTuChon">
            <option value="">— Chọn vật tư —</option>
            <option v-for="vt in vatTuList" :key="vt.name" :value="vt.name">
              {{ vt.ma_vat_tu }} — {{ vt.ten_vat_tu }}
            </option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0" v-if="tab === 'canh_bao'">
          <label>Số ngày cảnh báo</label>
          <input
            type="number" min="0" v-model.number="soNgay" @change="locThayDoi"
            style="width: 100px"
          />
        </div>
        <div class="field" style="margin-bottom: 0" v-if="tab === 'dot'">
          <label>Vật tư</label>
          <select v-model="dotVatTuChon">
            <option value="">— Tất cả —</option>
            <option v-for="vt in dotVatTuList" :key="vt.name" :value="vt.name">
              {{ vt.ma_vat_tu }} — {{ vt.ten_vat_tu }}{{ vt.active ? '' : ' (đã tắt)' }}
            </option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0" v-if="tab === 'dot'">
          <label>Nguồn</label>
          <select v-model="dotNguon">
            <option value="">— Tất cả —</option>
            <option value="Miyano">Miyano</option>
            <option v-for="n in nccList" :key="n.name" :value="n.ten_ncc">
              {{ n.ten_ncc }}{{ n.active ? '' : ' (đã tắt)' }}
            </option>
          </select>
        </div>
        <!-- F-5 (review E8): kho_bao_cao_excel CHƯA hỗ trợ tab "Cấp phát
             theo khoa" (loai="cap_phat" không có trong _BAO_CAO_LOAI — quyết
             định phạm vi, xem báo cáo bàn giao) — exportUrl() đã trả ''
             cho tab này nên bấm không làm gì, nhưng nút vẫn hiện, im lặng,
             không có gì báo cho người dùng biết vì sao không tải được gì.
             Ẩn hẳn nút thay vì để một hành vi chết đứng trên màn hình. -->
        <button v-if="tab !== 'cp'" class="btn-o btn-sm" style="margin-left: auto" @click="xuatExcel">
          ⬇ Xuất Excel
        </button>
      </div>
    </div>

    <div class="chips mb10">
      <button
        v-for="t in TABS" :key="t.key" class="chip" :class="{ on: tab === t.key }"
        @click="chonTab(t.key)"
      >{{ t.label }}</button>
    </div>

    <!-- ============ TAB: NHẬP - XUẤT - TỒN ============ -->
    <template v-if="tab === 'nxt'">
      <div v-if="nxtLoading" class="loading">Đang tải…</div>
      <div v-else-if="nxtError" class="empty">{{ nxtError }}</div>
      <div v-else-if="!nxtRows.length" class="empty">Không có phát sinh trong khoảng ngày đã chọn.</div>

      <div v-else class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th v-for="c in NXT_COLUMNS" :key="c.field" :class="{ right: c.field !== 'ma_vat_tu' && c.field !== 'ten_vat_tu' && c.field !== 'dvt' }">
                {{ c.label }}
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in nxtRows" :key="row.vat_tu">
              <tr class="clickable" @click="toggleLot(row)">
                <td v-for="c in NXT_COLUMNS" :key="c.field" :class="{ right: c.field !== 'ma_vat_tu' && c.field !== 'ten_vat_tu' && c.field !== 'dvt' }">
                  <b v-if="c.field === 'ma_vat_tu'">{{ row[c.field] }}</b>
                  <template v-else-if="c.field.endsWith('_tt')">{{ fmtVND(row[c.field]) }}</template>
                  <template v-else-if="c.field.endsWith('_sl')">{{ fmtQty(row[c.field]) }}</template>
                  <template v-else>{{ row[c.field] }}</template>
                </td>
                <td>{{ expanded[row.vat_tu] ? '▾' : '▸' }}</td>
              </tr>
              <tr v-if="expanded[row.vat_tu]">
                <td :colspan="NXT_COLUMNS.length + 1" style="background: #f8fafc; padding: 12px 16px">
                  <div v-if="lotRows[row.vat_tu]?.loading" class="loading">Đang tải theo lô…</div>
                  <div v-else-if="lotRows[row.vat_tu]?.error" class="empty">{{ lotRows[row.vat_tu].error }}</div>
                  <div v-else-if="!lotRows[row.vat_tu]?.data?.length" class="empty">Không có lô nào phát sinh trong kỳ.</div>
                  <div v-else style="overflow-x: auto">
                    <table style="background: transparent">
                      <thead>
                        <tr>
                          <th v-for="c in NXT_LOT_COLUMNS" :key="c.field" :class="{ right: c.field !== 'so_lo' && c.field !== 'han_su_dung' }">
                            {{ c.label }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="lo in lotRows[row.vat_tu].data" :key="lo.so_lo">
                          <td v-for="c in NXT_LOT_COLUMNS" :key="c.field" :class="{ right: c.field !== 'so_lo' && c.field !== 'han_su_dung' }">
                            <template v-if="c.field === 'han_su_dung'">{{ lo.han_su_dung ? fmtDate(lo.han_su_dung) : '—' }}</template>
                            <template v-else-if="c.field.endsWith('_tt')">{{ fmtVND(lo[c.field]) }}</template>
                            <template v-else-if="c.field.endsWith('_sl')">{{ fmtQty(lo[c.field]) }}</template>
                            <template v-else>{{ lo[c.field] }}</template>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
    </template>

    <!-- ============ TAB: THẺ KHO ============ -->
    <template v-else-if="tab === 'the_kho'">
      <div v-if="!vatTuChon" class="empty">Chọn một vật tư ở trên để xem thẻ kho.</div>
      <div v-else-if="theKhoLoading" class="loading">Đang tải…</div>
      <div v-else-if="theKhoError" class="empty">{{ theKhoError }}</div>
      <div v-else-if="!theKhoRows.length" class="empty">Không có phát sinh trong khoảng ngày đã chọn.</div>
      <div v-else class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th v-for="c in THE_KHO_COLUMNS" :key="c.field" :class="{ right: ['sl_nhap', 'sl_xuat', 'ton_luy_ke'].includes(c.field) }">
                {{ c.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in theKhoRows" :key="idx">
              <td v-for="c in THE_KHO_COLUMNS" :key="c.field" :class="{ right: ['sl_nhap', 'sl_xuat', 'ton_luy_ke'].includes(c.field) }">
                <template v-if="c.field === 'ngay'">{{ fmtDate(r.ngay) }}</template>
                <template v-else-if="c.field === 'chung_tu'"><b>{{ r.chung_tu }}</b></template>
                <template v-else-if="['sl_nhap', 'sl_xuat', 'ton_luy_ke'].includes(c.field)">{{ fmtQty(r[c.field]) }}</template>
                <template v-else>{{ r[c.field] || '—' }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PhanTrang v-if="vatTuChon" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
    </template>

    <!-- ============ TAB: CẢNH BÁO HẠN DÙNG ============ -->
    <template v-else-if="tab === 'canh_bao'">
      <div v-if="canhBaoLoading" class="loading">Đang tải…</div>
      <div v-else-if="canhBaoError" class="empty">{{ canhBaoError }}</div>
      <div v-else-if="!canhBaoRows.length" class="empty">Không có lô nào hết hạn hoặc sắp hết hạn.</div>
      <div v-else class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th v-for="c in CANH_BAO_COLUMNS" :key="c.field" :class="{ right: ['so_ngay_con_lai', 'so_luong'].includes(c.field) }">
                {{ c.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in canhBaoRows" :key="idx">
              <td v-for="c in CANH_BAO_COLUMNS" :key="c.field" :class="{ right: ['so_ngay_con_lai', 'so_luong'].includes(c.field) }">
                <b v-if="c.field === 'ma_vat_tu'">{{ r.ma_vat_tu }}</b>
                <template v-else-if="c.field === 'han_su_dung'">{{ fmtDate(r.han_su_dung) }}</template>
                <template v-else-if="c.field === 'so_luong'">{{ fmtQty(r.so_luong) }}</template>
                <template v-else-if="c.field === 'trang_thai'">
                  <!-- VĐ-2: "Không có hạn dùng" là một GHI CHÚ dữ liệu, không
                       phải một cảnh báo — badge xám trung tính, không icon
                       cảnh báo, để không lặp lại đúng lỗi "báo động sai" mà
                       bản sửa canh_bao_han_rows() vừa dọn ở tầng dữ liệu. -->
                  <span
                    class="badge"
                    :class="r.trang_thai === 'Đã hết hạn' ? 'b-red' : r.trang_thai === 'Sắp hết hạn' ? 'b-orange' : 'b-gray'"
                  >
                    {{ r.trang_thai === 'Đã hết hạn' ? '⛔' : r.trang_thai === 'Sắp hết hạn' ? '⚠' : '' }} {{ r.trang_thai }}
                  </span>
                </template>
                <template v-else>{{ r[c.field] }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
    </template>

    <!-- ============ TAB: NXT THEO ĐỢT HÀNG (US-E4.7) ============ -->
    <template v-else-if="tab === 'dot'">
      <div v-if="dotLoading" class="loading">Đang tải…</div>
      <div v-else-if="dotError" class="empty">{{ dotError }}</div>
      <div v-else-if="!dotRows.length" class="empty">Không có đợt hàng nào trong khoảng ngày đã chọn.</div>
      <template v-else>
        <div class="card" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Đợt (phiếu nhập)</th>
                <th>Ngày nhận</th>
                <th>Nguồn</th>
                <th>Vật tư / lô</th>
                <th class="right">SL nhập</th>
                <th class="right">Đã xuất</th>
                <th class="right">Còn lại</th>
                <th class="right">Tuổi tồn</th>
                <th class="right">%TT</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, idx) in dotRows" :key="idx" :style="r.cham_luan_chuyen ? 'background:#fff7ed' : ''">
                <td>
                  <router-link :to="`/kho/nhap/${r.dot}`" class="mono"><b>{{ r.dot }}</b></router-link>
                </td>
                <td>{{ fmtDate(r.ngay_nhan) }}</td>
                <td>{{ r.nguon }}<span v-if="r.chung_tu" class="tag"> · {{ r.chung_tu }}</span></td>
                <td>{{ tenVatTu(r.vat_tu) }} <span class="mono tag">· {{ r.lo }}</span></td>
                <td class="right">{{ fmtQty(r.sl_nhap) }}</td>
                <td class="right">{{ fmtQty(r.da_xuat) }}</td>
                <td class="right"><b>{{ fmtQty(r.con_lai) }}</b></td>
                <td class="right">{{ r.tuoi_ton_ngay }} ngày</td>
                <td class="right">{{ r.pct_tieu_thu }}%</td>
                <td>
                  <span v-if="r.cham_luan_chuyen" class="badge b-orange">Chậm luân chuyển</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="tag" style="margin-top: 8px">
          Số xuất phân bổ cho đợt cũ trước (FIFO trong từng vật tư + lô — BR-D1). Cờ chậm luân chuyển khi
          tuổi tồn vượt ngưỡng cấu hình của kho (Miyano Portal Settings).
        </p>
        <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
      </template>
    </template>

    <!-- ============ TAB: CẤP PHÁT THEO KHOA (US-E8.5) ============ -->
    <template v-else>
      <div v-if="cpLoading" class="loading">Đang tải…</div>
      <div v-else-if="cpError" class="empty">{{ cpError }}</div>
      <div v-else-if="!cpResult.nhom.length" class="empty">Không có phiếu Xuất sử dụng nào trong khoảng ngày đã chọn.</div>
      <template v-else>
        <div class="card" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Khoa phòng</th>
                <th>Vật tư</th>
                <th class="right">SL</th>
                <th class="right">Giá trị</th>
                <th>Người nhận</th>
                <th>Phiếu</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="n in cpResult.nhom" :key="n.khoa_phong || '__chua_gan__'">
                <tr :style="n.khoa_phong ? 'background:#f1f5f9' : 'background:#fffbeb'">
                  <td colspan="3">
                    <b>{{ n.ten_hien_thi }} — {{ n.pct }}%</b>
                    <span v-if="!n.khoa_phong" class="tag"> (phiếu trước khi bật bắt buộc, hoặc kho chưa bật)</span>
                  </td>
                  <td class="right"><b>{{ fmtVND(n.gia_tri) }}</b></td>
                  <td colspan="2"></td>
                </tr>
                <tr v-for="(d, idx) in n.dong" :key="idx">
                  <!-- F-4 (review E8): nhóm "Chưa gắn khoa" hiện lại noi_nhan
                       (ô "Nơi nhận" tự do, có TRƯỚC khi khoa_phong tồn tại) —
                       phiếu cũ rất có thể đã ghi đúng tên khoa vào đó, giấu
                       đi là mất luôn dữ liệu còn cứu được. -->
                  <td>
                    <span v-if="!n.khoa_phong && d.noi_nhan" class="tag">Nơi nhận (cũ): {{ d.noi_nhan }}</span>
                  </td>
                  <td>{{ d.vat_tu }}</td>
                  <td class="right">{{ fmtQty(d.sl) }} {{ d.dvt }}</td>
                  <td class="right">{{ fmtVND(d.gia_tri) }}</td>
                  <td>{{ d.nguoi_nhan || '—' }}</td>
                  <td><router-link :to="`/kho/xuat/${d.phieu}`" class="mono">{{ d.phieu }}</router-link></td>
                </tr>
              </template>
            </tbody>
            <tfoot>
              <tr>
                <!-- Brief 2026-08-15 (phân trang) — báo cáo này cắt theo
                     ĐƠN VỊ NHÓM (khoa phòng), nên "Tổng cộng" ở đây vẫn LUÔN
                     là tổng TOÀN KỲ (mọi khoa, mọi trang) — server tính
                     trước khi cắt trang. Ghi rõ "toàn kỳ" để không hiểu
                     nhầm là tổng của riêng các nhóm đang hiện trên trang. -->
                <td colspan="3" style="text-align: right"><b>Tổng cộng (toàn kỳ)</b></td>
                <td class="right"><b>{{ fmtVND(cpResult.tong_gia_tri) }}</b></td>
                <td colspan="2"></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <p class="tag" style="margin-top: 8px">
          Nhóm theo khoa, drill xuống phiếu; "Chưa gắn khoa" tách riêng — không lẫn vào khoa nào (BR-CP4).
          Phiếu bị đảo không tính vào báo cáo.
        </p>
        <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
      </template>
    </template>
  </div>
</template>
