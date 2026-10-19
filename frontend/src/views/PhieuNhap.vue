<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { trangThaiBadge } from '../kho-actions'
import { useIsMobile } from '../useMobile'
import PhanTrang from '../components/PhanTrang.vue'
import Icon from '../components/Icon.vue'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
// BR-N2/NL-7.2 (F-14): lọc phiếu "thiếu chứng từ NCC" — backend đã hỗ trợ
// (kho_phieu_list(thieu_chung_tu=1)) nhưng chưa màn nào hiện bộ lọc.
const chiThieuChungTu = ref(false)
// Brief 2026-08-15 (phân trang).
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.callKho('kho_phieu_list', {
      loai: 'nhap',
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      thieu_chung_tu: chiThieuChungTu.value ? 1 : undefined,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách phiếu nhập.'
  } finally {
    loading.value = false
  }
}

watch([trang, soDong], load)
function locThayDoi() {
  trang.value = 1
  load()
}

function badge(docstatus) {
  return trangThaiBadge(docstatus)
}

function open(row) {
  router.push(`/kho/nhap/${row.name}`)
}

function taoMoi() {
  router.push('/kho/nhap/moi')
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div class="grow">
        <h2>Phiếu nhập kho</h2>
        <div class="sub">Danh sách phiếu nhập đã lập cho kho của bạn</div>
      </div>
      <button class="btn" @click="taoMoi"><Icon name="plus" :size="18" />Tạo phiếu nhập</button>
    </div>
    <div class="sb mb12" v-else>
      <h2>Phiếu nhập kho</h2>
      <button class="btn btn-sm" @click="taoMoi"><Icon name="plus" :size="16" />Tạo phiếu</button>
    </div>

    <label class="card mb10 pn-loc">
      <input type="checkbox" v-model="chiThieuChungTu" @change="locThayDoi" />
      Chỉ phiếu thiếu chứng từ NCC
    </label>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">
      {{ chiThieuChungTu ? 'Không có phiếu nào thiếu chứng từ NCC.' : 'Chưa có phiếu nhập nào. Bấm "Tạo phiếu nhập" để lập phiếu đầu tiên.' }}
    </div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card card-flush">
      <div class="tbl-scroll">
      <table>
        <thead>
          <tr>
            <th>Số phiếu</th>
            <th>Ngày</th>
            <th>Loại nhập</th>
            <th>Người giao</th>
            <th class="right">Tổng tiền</th>
            <th>Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="clickable" @click="open(r)">
            <td class="cell-code nowrap">{{ r.name }}</td>
            <td>{{ fmtDate(r.ngay) }}</td>
            <td>{{ r.loai_nhap }}</td>
            <td>{{ r.nguoi_giao || '—' }}</td>
            <td class="right">{{ fmtVND(r.tong_tien) }}</td>
            <td>
              <span class="badge" :class="badge(r.docstatus).cls">{{ badge(r.docstatus).label }}</span>
              <span v-if="r.thieu_chung_tu" class="badge b-orange ml4">Thiếu chứng từ</span>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <!-- MOBILE -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10 clickable" @click="open(r)">
        <div class="sb">
          <b class="cell-code">{{ r.name }}</b>
          <span class="badge" :class="badge(r.docstatus).cls">{{ badge(r.docstatus).label }}</span>
        </div>
        <p class="tag mt4">{{ r.loai_nhap }} · {{ fmtDate(r.ngay) }}</p>
        <p class="sb mt8 fs13">
          <span>Người giao: {{ r.nguoi_giao || '—' }}</span>
          <b class="tnum">{{ fmtVND(r.tong_tien) }}</b>
        </p>
        <span v-if="r.thieu_chung_tu" class="badge b-orange mt6">Thiếu chứng từ</span>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
  </div>
</template>

<style scoped>
/* Ô lọc "Chỉ phiếu thiếu chứng từ NCC": thẻ nhỏ vừa nội dung, bấm cả ô. */
.pn-loc {
  display: flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  min-height: 44px;
  padding: 10px 14px;
  font-size: 13px;
  cursor: pointer;
}
</style>
