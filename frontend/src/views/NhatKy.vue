<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import PhanTrang from '../components/PhanTrang.vue'

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

// --- E8/US-E8.4: khoa phòng (để dựng chip lọc) ---
const khoaPhongList = ref([])

// --- Bộ lọc ---
const loaiFilter = ref('') // '' | 'Nhập' | 'Xuất'
const nguonFilter = ref('') // '' | 'Miyano' | tên NCC
const loFilter = ref('') // '' | số lô
const khoaFilter = ref('') // '' | tên (docname) khoa phòng
const lotOptions = ref([]) // dựng lại mỗi lần tải KHÔNG lọc theo lô

const loading = ref(false)
const error = ref('')
const result = ref({ tong_dong: 0, trang: 1, so_dong_moi_trang: 20, dong: [] })
// Brief 2026-08-15 (phân trang) — ĐỔI cặp nút Trước/Sau tự chế trước đây
// sang PhanTrang.vue (cùng bộ phân trang với cả cổng, chọn được 10/20/50).
const trang = ref(1)
const soDong = ref(20)

function fmtQty(v) {
  return Number(v || 0).toLocaleString('vi-VN')
}

function tenVatTu(vt) {
  const v = vatTuList.value.find((x) => x.name === vt)
  return v ? `${v.ma_vat_tu} — ${v.ten_vat_tu}` : vt
}

async function loadVatTu() {
  try {
    // ca_tat=1: đây là màn ĐỌC LỊCH SỬ, không phải nơi tạo dòng phiếu mới —
    // một vật tư đã tắt (chỉ tắt được khi hết tồn, xem vat_tu._chan_tat_khi_
    // con_ton) vẫn có sổ, phải tra được nhật ký của nó. Lọc active=1 (mặc
    // định của kho_vat_tu_list) sẽ khoá đúng những vật tư có sổ đầy đủ nhất
    // nhưng hết tồn ra khỏi ô chọn.
    vatTuList.value = await api.callKho('kho_vat_tu_list', { ca_tat: 1 })
  } catch (e) {
    // Chọn vật tư sẽ trống nếu lỗi — không chặn màn hình.
  }
}

async function loadNcc() {
  try {
    // ca_inactive=1: cùng lý do trên — một phiếu nhập cũ từ NCC đã tắt vẫn
    // nằm trong nhật ký, chip "Nguồn" phải lọc được theo đúng NCC đó.
    nccList.value = await api.callKho('kho_ncc_list', { ca_inactive: 1 })
  } catch (e) {
    // Chip nguồn theo NCC sẽ chỉ thiếu, không chặn màn hình.
  }
}

async function loadKhoaPhong() {
  try {
    // ca_inactive=1: cùng lý do trên — một dòng xuất cũ gắn khoa đã tắt vẫn
    // nằm trong nhật ký, chip lọc phải tìm được đúng khoa đó.
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Chip lọc theo khoa sẽ chỉ thiếu, không chặn màn hình.
  }
}

async function load() {
  if (!vatTuChon.value) {
    result.value = { tong_dong: 0, trang: 1, so_dong_moi_trang: soDong.value, dong: [] }
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
      khoa_phong: khoaFilter.value || undefined,
      trang: trang.value,
      so_dong_moi_trang: soDong.value,
    })
    result.value = out
    if (!loFilter.value) {
      const lots = new Set()
      for (const r of out.dong) if (r.lo) lots.add(r.lo)
      lotOptions.value = [...lots].sort()
    }
  } catch (e) {
    error.value = e.message || 'Không tải được nhật ký vật tư.'
    result.value = { tong_dong: 0, trang: 1, so_dong_moi_trang: soDong.value, dong: [] }
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

function chonKhoa(khoa) {
  khoaFilter.value = khoaFilter.value === khoa ? '' : khoa
  trang.value = 1
  load()
}

watch([vatTuChon, tuNgay, denNgay], () => {
  trang.value = 1
  load()
})

// PhanTrang.vue tự đổi trang.value/soDong.value (v-model) khi khách bấm
// Trước/Sau hoặc đổi số dòng/trang — nghe ở đây để gọi lại API.
watch([trang, soDong], load)

function phieuUrl(r) {
  return r.loai === 'Nhập' ? `/kho/nhap/${r.phieu}` : `/kho/xuat/${r.phieu}`
}

// (Review E4 phần B, Gap 2 — ĐÃ SỬA) kho_bao_cao_excel giờ nhận loai="nhat_ky":
// cùng bộ lọc đang xem (vật tư/kỳ/lô/loại dòng/nguồn), KHÔNG cắt theo trang —
// khác `kho_nhat_ky` (màn hình, 50 dòng/trang), Excel lấy ĐỦ dữ liệu cả kỳ.
function excelUrl() {
  if (!vatTuChon.value) return ''
  const base = '/api/method/miyano_portal.api.kho.kho_bao_cao_excel'
  let u = `${base}?loai=nhat_ky&vat_tu=${encodeURIComponent(vatTuChon.value)}`
    + `&tu_ngay=${encodeURIComponent(tuNgay.value)}&den_ngay=${encodeURIComponent(denNgay.value)}`
  if (loFilter.value) u += `&lo=${encodeURIComponent(loFilter.value)}`
  if (loaiFilter.value) u += `&dong_loai=${encodeURIComponent(loaiFilter.value)}`
  if (nguonFilter.value) u += `&nguon=${encodeURIComponent(nguonFilter.value)}`
  if (khoaFilter.value) u += `&khoa_phong=${encodeURIComponent(khoaFilter.value)}`
  return u
}
function xuatExcel() {
  const url = excelUrl()
  if (!url) return
  window.open(url, '_blank')
}

onMounted(() => {
  loadVatTu()
  loadNcc()
  loadKhoaPhong()
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
        <button
          class="btn-o btn-sm" :disabled="!vatTuChon"
          :title="!vatTuChon ? 'Chọn vật tư trước khi xuất' : ''" @click="xuatExcel"
        >⬇ Excel (bắt buộc chọn kỳ)</button>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Nhật ký vật tư</h2>
      <button
        class="btn-o btn-sm" :disabled="!vatTuChon"
        :title="!vatTuChon ? 'Chọn vật tư trước khi xuất' : ''" @click="xuatExcel"
      >⬇ Excel</button>
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
        >{{ n.ten_ncc }}{{ n.active ? '' : ' (đã tắt)' }}</button>
        <button v-for="lo in lotOptions" :key="lo" class="chip" :class="{ on: loFilter === lo }" @click="chonLo(lo)">
          Lô {{ lo }}
        </button>
        <button
          v-for="k in khoaPhongList" :key="k.name" class="chip" :class="{ on: khoaFilter === k.name }"
          @click="chonKhoa(k.name)"
        >Khoa {{ k.ten_khoa_phong }}{{ k.active ? '' : ' (đã tắt)' }}</button>
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

      <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="result.tong_dong" />
      <p class="tag" style="margin-top: 6px">
        Vật tư đang xem: {{ tenVatTu(vatTuChon) }}.
        <template v-if="!loaiFilter && !nguonFilter && !loFilter && trang * soDong >= result.tong_dong">
          Tồn sau giao dịch dòng cuối = tồn hiện tại (đối chiếu màn Tồn kho).
        </template>
      </p>
    </template>
  </div>
</template>
