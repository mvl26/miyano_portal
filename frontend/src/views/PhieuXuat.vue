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

// E8/US-E8.4: lọc danh sách phiếu xuất theo khoa phòng.
const khoaPhongList = ref([])
const khoaPhongLoc = ref('') // '' = tất cả

async function loadKhoaPhongList() {
  try {
    // ca_inactive=1: một phiếu cũ gắn khoa đã tắt vẫn phải lọc được.
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Ô lọc sẽ chỉ thiếu tuỳ chọn, không chặn cả danh sách.
  }
}

function tenKhoa(name) {
  const k = khoaPhongList.value.find((x) => x.name === name)
  return k ? k.ten_khoa_phong : name
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.callKho('kho_phieu_list', {
      loai: 'xuat', limit: 50, khoa_phong: khoaPhongLoc.value || undefined,
    })
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách phiếu xuất.'
  } finally {
    loading.value = false
  }
}

function badge(docstatus) {
  return trangThaiBadge(docstatus)
}

function open(row) {
  router.push(`/kho/xuat/${row.name}`)
}

function taoMoi() {
  router.push('/kho/xuat/moi')
}

onMounted(() => {
  loadKhoaPhongList()
  load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Phiếu xuất kho</h2>
        <div class="sub">Danh sách phiếu xuất đã lập cho kho của bạn</div>
      </div>
      <button class="btn" @click="taoMoi">+ Tạo phiếu xuất</button>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Phiếu xuất kho</h2>
      <button class="btn btn-sm" @click="taoMoi">+ Tạo phiếu</button>
    </div>

    <!-- E8/US-E8.4: lọc theo khoa phòng -->
    <div class="field" style="max-width: 320px">
      <label>Khoa phòng nhận</label>
      <select v-model="khoaPhongLoc" @change="load">
        <option value="">— Tất cả —</option>
        <option v-for="k in khoaPhongList" :key="k.name" :value="k.name">
          {{ k.ten_khoa_phong }}{{ k.active ? '' : ' (đã tắt)' }}
        </option>
      </select>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">
      {{ khoaPhongLoc ? 'Không có phiếu xuất nào của khoa phòng đã chọn.' : 'Chưa có phiếu xuất nào. Bấm "Tạo phiếu xuất" để lập phiếu đầu tiên.' }}
    </div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Số phiếu</th>
            <th>Ngày</th>
            <th>Loại xuất</th>
            <th>Khoa phòng</th>
            <th>Nơi nhận</th>
            <th class="right">Tổng tiền</th>
            <th>Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="clickable" @click="open(r)">
            <td><b>{{ r.name }}</b></td>
            <td>{{ fmtDate(r.ngay) }}</td>
            <td>{{ r.loai_xuat }}</td>
            <td>{{ r.khoa_phong ? tenKhoa(r.khoa_phong) : '—' }}</td>
            <td>{{ r.noi_nhan || '—' }}</td>
            <td class="right">{{ fmtVND(r.tong_tien) }}</td>
            <td><span class="badge" :class="badge(r.docstatus).cls">{{ badge(r.docstatus).label }}</span></td>
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
        <p class="tag" style="margin-top: 4px">{{ r.loai_xuat }} · {{ fmtDate(r.ngay) }}</p>
        <p class="sb" style="margin-top: 8px; font-size: 13px">
          <span>{{ r.khoa_phong ? tenKhoa(r.khoa_phong) : (r.noi_nhan || '—') }}</span>
          <b>{{ fmtVND(r.tong_tien) }}</b>
        </p>
      </div>
    </template>
  </div>
</template>
