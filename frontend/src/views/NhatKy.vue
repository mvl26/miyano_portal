<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const isMobile = useIsMobile()

function pad(n) {
  return String(n).padStart(2, '0')
}
function isoDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const now = new Date()
const tuNgay = ref(isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 30)))
const denNgay = ref(isoDate(now))

// --- Vật tư (bắt buộc — F-18: empty state "Chọn vật tư để xem nhật ký") ---
const vatTuList = ref([])
const vatTuChon = ref('')

// --- NCC (để dựng chip "Nguồn") ---
const nccList = ref([])

// --- Bộ lọc ---
const loaiFilter = ref('') // '' | 'Nhập' | 'Xuất'
const nguonFilter = ref('') // '' | 'Miyano' | tên NCC
const loFilter = ref('') // '' | số lô
const lotOptions = ref([]) // dựng lại mỗi lần tải KHÔNG lọc theo lô

const loading = ref(false)
const error = ref('')
const result = ref({ tong_dong: 0, trang: 1, so_dong_moi_trang: 50, dong: [] })
const trang = ref(1)

const tongTrang = computed(() =>
  Math.max(1, Math.ceil((result.value.tong_dong || 0) / (result.value.so_dong_moi_trang || 50)))
)

function fmtQty(v) {
  return Number(v || 0).toLocaleString('vi-VN')
}

function tenVatTu(vt) {
  const v = vatTuList.value.find((x) => x.name === vt)
  return v ? `${v.ma_vat_tu} — ${v.ten_vat_tu}` : vt
}

async function loadVatTu() {
  try {
    vatTuList.value = await api.callKho('kho_vat_tu_list')
  } catch (e) {
    // Chọn vật tư sẽ trống nếu lỗi — không chặn màn hình.
  }
}

async function loadNcc() {
  try {
    nccList.value = await api.callKho('kho_ncc_list', {})
  } catch (e) {
    // Chip nguồn theo NCC sẽ chỉ thiếu, không chặn màn hình.
  }
}

async function load() {
  if (!vatTuChon.value) {
    result.value = { tong_dong: 0, trang: 1, so_dong_moi_trang: 50, dong: [] }
    return
  }
  loading.value = true
  error.value = ''
  try {
    const out = await api.callKho('kho_nhat_ky', {
      vat_tu: vatTuChon.value,
      tu_ngay: tuNgay.value,
      den_ngay: denNgay.value,
      loai: loaiFilter.value || undefined,
      nguon: nguonFilter.value || undefined,
      lo: loFilter.value || undefined,
      trang: trang.value,
    })
    result.value = out
    if (!loFilter.value) {
      const lots = new Set()
      for (const r of out.dong) if (r.lo) lots.add(r.lo)
      lotOptions.value = [...lots].sort()
    }
  } catch (e) {
    error.value = e.message || 'Không tải được nhật ký vật tư.'
    result.value = { tong_dong: 0, trang: 1, so_dong_moi_trang: 50, dong: [] }
  } finally {
    loading.value = false
  }
}

function chonBoLoc(nextLoai, nextNguon) {
  loaiFilter.value = nextLoai
  nguonFilter.value = nextNguon
  trang.value = 1
  load()
}

function chonLo(lo) {
  loFilter.value = loFilter.value === lo ? '' : lo
  trang.value = 1
  load()
}

watch([vatTuChon, tuNgay, denNgay], () => {
  trang.value = 1
  load()
})

function trangTruoc() {
  if (trang.value <= 1) return
  trang.value -= 1
  load()
}
function trangSau() {
  if (trang.value >= tongTrang.value) return
  trang.value += 1
  load()
}

function phieuUrl(r) {
  return r.loai === 'Nhập' ? `/kho/nhap/${r.phieu}` : `/kho/xuat/${r.phieu}`
}

// Chưa có cột "nhat_ky" trong kho_bao_cao_excel (chỉ hỗ trợ nxt/the_kho/
// canh_bao) — báo gap thay vì gọi một endpoint chắc chắn lỗi hoặc âm thầm
// không làm gì khi bấm nút.
function xuatExcel() {
  if (!tuNgay.value || !denNgay.value) {
    showToast('Chọn kỳ trước khi xuất Excel.', 'error')
    return
  }
  showToast(
    'Xuất Excel cho Nhật ký vật tư chưa được backend hỗ trợ — báo Miyano để bổ sung endpoint.',
    'error'
  )
}

onMounted(() => {
  loadVatTu()
  loadNcc()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Nhật ký vật tư</h2>
        <div class="sub">Mọi biến động — dựng từ sổ kho, chỉ đọc</div>
      </div>
      <div class="flex" style="gap: 8px">
        <button class="btn-o btn-sm" @click="xuatExcel">⬇ Excel (bắt buộc chọn kỳ)</button>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Nhật ký vật tư</h2>
      <button class="btn-o btn-sm" @click="xuatExcel">⬇ Excel</button>
    </div>

    <div class="card mb10">
      <div class="flex" style="flex-wrap: wrap; gap: 14px">
        <div class="field" style="margin-bottom: 0; flex: 1; min-width: 260px">
          <label>Vật tư (bắt buộc)</label>
          <select v-model="vatTuChon">
            <option value="">— Chọn vật tư —</option>
            <option v-for="v in vatTuList" :key="v.name" :value="v.name">
              {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
            </option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Từ ngày</label>
          <input type="date" v-model="tuNgay" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Đến ngày</label>
          <input type="date" v-model="denNgay" />
        </div>
      </div>

      <div v-if="vatTuChon" class="flex" style="margin-top: 10px; flex-wrap: wrap; gap: 8px">
        <button class="chip" :class="{ on: !loaiFilter && !nguonFilter }" @click="chonBoLoc('', '')">Tất cả</button>
        <button class="chip" :class="{ on: loaiFilter === 'Nhập' }" @click="chonBoLoc('Nhập', nguonFilter)">Chỉ nhập</button>
        <button class="chip" :class="{ on: loaiFilter === 'Xuất' }" @click="chonBoLoc('Xuất', nguonFilter)">Chỉ xuất</button>
        <button class="chip" :class="{ on: nguonFilter === 'Miyano' }" @click="chonBoLoc(loaiFilter, 'Miyano')">Nguồn: Miyano</button>
        <button
          v-for="n in nccList" :key="n.name" class="chip" :class="{ on: nguonFilter === n.ten_ncc }"
          @click="chonBoLoc(loaiFilter, n.ten_ncc)"
        >{{ n.ten_ncc }}</button>
        <button v-for="lo in lotOptions" :key="lo" class="chip" :class="{ on: loFilter === lo }" @click="chonLo(lo)">
          Lô {{ lo }}
        </button>
      </div>
    </div>

    <div v-if="!vatTuChon" class="empty">Chọn vật tư để xem nhật ký.</div>
    <div v-else-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!result.dong.length" class="empty">Không có phát sinh trong khoảng ngày đã chọn.</div>

    <template v-else>
      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Ngày</th>
              <th>Phiếu</th>
              <th>Loại</th>
              <th>Nguồn / đợt</th>
              <th>Lô</th>
              <th class="right">Nhập</th>
              <th class="right">Xuất</th>
              <th class="right">Đơn giá</th>
              <th class="right">Tồn sau GD</th>
              <th>Người ghi sổ</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in result.dong" :key="idx" :class="{ rowdim: r.da_dao }">
              <td>{{ fmtDate(r.ngay) }}</td>
              <td>
                <router-link :to="phieuUrl(r)" class="mono"><b>{{ r.phieu }}</b></router-link>
              </td>
              <td>
                {{ r.loai }}
                <span v-if="r.da_dao" class="badge b-gray" style="margin-left: 4px">đã đảo</span>
              </td>
              <td>{{ r.nguon || '—' }}</td>
              <td class="mono">{{ r.lo }}</td>
              <td class="right">{{ r.sl_nhap ? fmtQty(r.sl_nhap) : '' }}</td>
              <td class="right">{{ r.sl_xuat ? fmtQty(r.sl_xuat) : '' }}</td>
              <td class="right">{{ fmtVND(r.don_gia) }}</td>
              <td class="right"><b>{{ fmtQty(r.ton_sau) }}</b></td>
              <td class="tag">{{ r.nguoi_ghi_so }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex" style="justify-content: space-between; margin-top: 10px">
        <p class="tag">{{ result.tong_dong }} dòng · trang {{ trang }}/{{ tongTrang }}</p>
        <div class="flex" style="gap: 8px">
          <button class="btn-o btn-sm" :disabled="trang <= 1" @click="trangTruoc">‹ Trang trước</button>
          <button class="btn-o btn-sm" :disabled="trang >= tongTrang" @click="trangSau">Trang sau ›</button>
        </div>
      </div>
      <p class="tag" style="margin-top: 6px">
        Vật tư đang xem: {{ tenVatTu(vatTuChon) }}.
        <template v-if="!loaiFilter && !nguonFilter && !loFilter && trang >= tongTrang">
          Tồn sau giao dịch dòng cuối = tồn hiện tại (đối chiếu màn Tồn kho).
        </template>
      </p>
    </template>
  </div>
</template>
