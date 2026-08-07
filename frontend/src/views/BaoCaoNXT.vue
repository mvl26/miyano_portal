<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import {
  NXT_COLUMNS, NXT_LOT_COLUMNS, THE_KHO_COLUMNS, CANH_BAO_COLUMNS,
} from '../kho-bao-cao-columns'

const isMobile = useIsMobile()

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
    })
    nxtRows.value = out.rows || []
  } catch (e) {
    nxtError.value = e.message || 'Không tải được báo cáo Nhập - Xuất - Tồn.'
  } finally {
    nxtLoading.value = false
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
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
    return
  }
  theKhoLoading.value = true
  theKhoError.value = ''
  try {
    theKhoRows.value = await api.callKho('kho_the_kho', {
      vat_tu: vatTuChon.value, tu_ngay: tuNgay.value, den_ngay: denNgay.value,
    })
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
    canhBaoRows.value = await api.callKho('kho_canh_bao_han', { so_ngay: soNgay.value })
  } catch (e) {
    canhBaoError.value = e.message || 'Không tải được cảnh báo hạn dùng.'
  } finally {
    canhBaoLoading.value = false
  }
}

function reload() {
  if (tab.value === 'nxt') loadNXT()
  else if (tab.value === 'the_kho') loadTheKho()
  else loadCanhBao()
}

function chonTab(key) {
  tab.value = key
  reload()
}

watch(vatTuChon, () => {
  if (tab.value === 'the_kho') loadTheKho()
})

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
  return `${base}?loai=canh_bao&so_ngay=${encodeURIComponent(soNgay.value)}`
}

function xuatExcel() {
  const url = exportUrl()
  if (!url) return
  window.open(url, '_blank')
}

onMounted(() => {
  loadVatTuList()
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
          <input type="date" v-model="tuNgay" @change="reload" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Đến ngày</label>
          <input type="date" v-model="denNgay" @change="reload" />
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
            type="number" min="0" v-model.number="soNgay" @change="loadCanhBao"
            style="width: 100px"
          />
        </div>
        <button class="btn-o btn-sm" style="margin-left: auto" @click="xuatExcel">
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
    </template>

    <!-- ============ TAB: CẢNH BÁO HẠN DÙNG ============ -->
    <template v-else>
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
                  <span class="badge" :class="r.trang_thai === 'Đã hết hạn' ? 'b-red' : 'b-orange'">
                    {{ r.trang_thai === 'Đã hết hạn' ? '⛔' : '⚠' }} {{ r.trang_thai }}
                  </span>
                </template>
                <template v-else>{{ r[c.field] }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
