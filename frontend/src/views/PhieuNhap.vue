<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { trangThaiBadge } from '../kho-actions'
import { useIsMobile } from '../useMobile'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
// BR-N2/NL-7.2 (F-14): lọc phiếu "thiếu chứng từ NCC" — backend đã hỗ trợ
// (kho_phieu_list(thieu_chung_tu=1)) nhưng chưa màn nào hiện bộ lọc.
const chiThieuChungTu = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.callKho('kho_phieu_list', {
      loai: 'nhap', limit: 50,
      thieu_chung_tu: chiThieuChungTu.value ? 1 : undefined,
    })
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách phiếu nhập.'
  } finally {
    loading.value = false
  }
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
      <div>
        <h2>Phiếu nhập kho</h2>
        <div class="sub">Danh sách phiếu nhập đã lập cho kho của bạn</div>
      </div>
      <button class="btn" @click="taoMoi">+ Tạo phiếu nhập</button>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Phiếu nhập kho</h2>
      <button class="btn btn-sm" @click="taoMoi">+ Tạo phiếu</button>
    </div>

    <label class="card mb10" style="display: flex; align-items: center; gap: 8px; font-size: 13px; width: fit-content">
      <input type="checkbox" v-model="chiThieuChungTu" @change="load" style="width: auto" />
      Chỉ phiếu thiếu chứng từ NCC
    </label>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">
      {{ chiThieuChungTu ? 'Không có phiếu nào thiếu chứng từ NCC.' : 'Chưa có phiếu nhập nào. Bấm "Tạo phiếu nhập" để lập phiếu đầu tiên.' }}
    </div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
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
            <td><b>{{ r.name }}</b></td>
            <td>{{ fmtDate(r.ngay) }}</td>
            <td>{{ r.loai_nhap }}</td>
            <td>{{ r.nguoi_giao || '—' }}</td>
            <td class="right">{{ fmtVND(r.tong_tien) }}</td>
            <td>
              <span class="badge" :class="badge(r.docstatus).cls">{{ badge(r.docstatus).label }}</span>
              <span v-if="r.thieu_chung_tu" class="badge b-orange" style="margin-left: 4px">Thiếu chứng từ</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10 clickable" @click="open(r)">
        <div class="sb">
          <b>{{ r.name }}</b>
          <span class="badge" :class="badge(r.docstatus).cls">{{ badge(r.docstatus).label }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">{{ r.loai_nhap }} · {{ fmtDate(r.ngay) }}</p>
        <p class="sb" style="margin-top: 8px; font-size: 13px">
          <span>Người giao: {{ r.nguoi_giao || '—' }}</span>
          <b>{{ fmtVND(r.tong_tien) }}</b>
        </p>
        <span v-if="r.thieu_chung_tu" class="badge b-orange" style="margin-top: 6px">Thiếu chứng từ</span>
      </div>
    </template>
  </div>
</template>
