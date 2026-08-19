<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'
import { fmtDateTime, deXuatBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'

const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const filter = ref('') // '' = Tất cả

// Brief task-3: chip theo ĐÚNG các giá trị `trang_thai` của doctype
// (`Nháp / Chờ duyệt / Đã duyệt / Chờ duyệt sửa / Từ chối / Đã huỷ`), trừ
// "Chờ duyệt sửa" — brief liệt kê đúng sáu chip này, không thêm.
const FILTERS = ['', 'Nháp', 'Chờ duyệt', 'Đã duyệt', 'Từ chối', 'Đã huỷ']

// Khoa phòng chỉ có MÃ (`KP-00001`) trong payload danh sách — cùng khuôn
// PhieuXuat.vue/NhatKy.vue: nạp danh mục khoa phòng của kho rồi tự map
// mã -> tên. Best-effort: một khách chưa mở kho (hoặc endpoint lỗi) vẫn
// phải xem được danh sách phiếu, chỉ mất phần dịch tên khoa.
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Im lặng — cột khoa phòng rơi về hiện mã thô, không chặn cả danh sách.
  }
}
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.callDeXuat('de_xuat_danh_sach', {
      trang_thai: filter.value || undefined,
      limit: 50,
    })
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách đề xuất.'
  } finally {
    loading.value = false
  }
}

// Ruling P1 (Task 3) — route 'de-xuat-detail' do Task 4 tạo. Danh sách này
// CỐ Ý không có hàm điều hướng/click-để-mở sang chi tiết: nối trước route
// đó tồn tại là link chết.

watch(filter, load)

onMounted(async () => {
  loadKhoaPhongList()
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Subtitle phạm vi chỉ là gợi ý phụ — im lặng bỏ qua.
    }
  }
  load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Đề xuất mua</h2>
        <div class="sub">
          {{ store.me?.la_quan_ly ? 'Toàn bộ phiếu đề xuất mua của đơn vị' : 'Phiếu đề xuất mua của khoa bạn' }}
        </div>
      </div>
    </div>

    <div class="chips">
      <button
        v-for="f in FILTERS"
        :key="f"
        class="chip"
        :class="{ on: filter === f }"
        @click="filter = f"
      >
        {{ f || 'Tất cả' }}
      </button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">Khoa chưa có phiếu đề xuất nào.</div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã phiếu</th><th>Khoa phòng</th><th>Trạng thái</th><th>Thời điểm gửi</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name">
            <td>
              <b v-if="r.ma_de_xuat">{{ r.ma_de_xuat }}</b>
              <span v-else class="tag">(chưa gửi duyệt)</span>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td><span class="badge" :class="deXuatBadge(r.trang_thai)">{{ r.trang_thai }}</span></td>
            <td>{{ r.thoi_diem_gui ? fmtDateTime(r.thoi_diem_gui) : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10">
        <div class="sb">
          <b v-if="r.ma_de_xuat">{{ r.ma_de_xuat }}</b>
          <span v-else class="tag">(chưa gửi duyệt)</span>
          <span class="badge" :class="deXuatBadge(r.trang_thai)">{{ r.trang_thai }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">
          {{ tenKhoa(r.khoa_phong) }}
          <template v-if="r.thoi_diem_gui"> · Gửi {{ fmtDateTime(r.thoi_diem_gui) }}</template>
        </p>
      </div>
    </template>
  </div>
</template>
