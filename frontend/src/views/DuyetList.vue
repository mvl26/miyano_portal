<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { fmtDateTime, deXuatBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'

const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])

// Task 5 — "quản lý sẽ filter theo khoa … cốt lõi là để quản lý biết được
// khoa nào đang mua cái gì mà để duyệt" (yêu cầu gốc chủ đầu tư). Dropdown
// lấy giá trị từ CHÍNH các phiếu đang hiện — không gọi thêm endpoint nào
// (không có endpoint danh mục khoa "đang có phiếu chờ").
const khoaFilter = ref('') // '' = Tất cả các khoa

// Khoa phòng chỉ có MÃ (`KP-00001`) trong payload danh sách — cùng khuôn
// DeXuatList.vue/DeXuatDetail.vue: nạp danh mục khoa phòng của kho rồi tự
// map mã -> tên. Best-effort: lỗi ở đây chỉ làm dropdown hiện mã thô, không
// chặn cả hàng chờ duyệt.
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Im lặng — xem giải thích ở trên.
  }
}
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}

// Danh sách khoa để đổ vào dropdown — CHỈ những khoa THẬT SỰ có phiếu đang
// chờ (không phải toàn bộ danh mục khoa phòng của viện): một khoa không có
// gì để duyệt thì không cần xuất hiện trong ô lọc của màn hàng chờ.
const khoaOptions = computed(() => {
  const ma = [...new Set(rows.value.map((r) => r.khoa_phong).filter(Boolean))]
  return ma
    .map((m) => ({ ma: m, ten: tenKhoa(m) }))
    .sort((a, b) => a.ten.localeCompare(b.ten, 'vi'))
})

const filteredRows = computed(() => {
  if (!khoaFilter.value) return rows.value
  return rows.value.filter((r) => r.khoa_phong === khoaFilter.value)
})

// `de_xuat_danh_sach` chỉ nhận MỘT `trang_thai` (chuỗi) mỗi lần gọi — gộp
// "Chờ duyệt" và "Chờ duyệt sửa" ở ĐÂY (client), không đổi chữ ký endpoint:
// truyền thẳng một mảng vào tham số đó sẽ vướng đúng cái bẫy filter Frappe
// coi list 2 phần tử là (operator, value) thay vì "in" — endpoint hiện tại
// không tự bọc `["in", [...]]`.
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [choDuyet, choDuyetSua] = await Promise.all([
      api.callDeXuat('de_xuat_danh_sach', { trang_thai: 'Chờ duyệt', limit: 200 }),
      api.callDeXuat('de_xuat_danh_sach', { trang_thai: 'Chờ duyệt sửa', limit: 200 }),
    ])
    rows.value = [...choDuyet, ...choDuyetSua].sort((a, b) =>
      (b.thoi_diem_gui || '').localeCompare(a.thoi_diem_gui || '')
    )
  } catch (e) {
    error.value = e.message || 'Không tải được hàng chờ duyệt.'
  } finally {
    loading.value = false
  }
}

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
        <h2>Duyệt</h2>
        <div class="sub">Phiếu đề xuất mua đang chờ bạn duyệt — cả gửi mới và xin sửa số lượng</div>
      </div>
    </div>

    <div class="card mb10">
      <div class="field" style="margin-bottom: 0; max-width: 320px">
        <label>Khoa phòng</label>
        <select v-model="khoaFilter">
          <option value="">— Tất cả các khoa —</option>
          <option v-for="k in khoaOptions" :key="k.ma" :value="k.ma">{{ k.ten }}</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!filteredRows.length" class="empty">Không có phiếu nào chờ duyệt.</div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã phiếu</th><th>Khoa phòng</th><th>Trạng thái</th><th>Thời điểm gửi</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in filteredRows"
            :key="r.name"
            style="cursor: pointer"
            @click="$router.push({ name: 'de-xuat-detail', params: { ten: r.name } })"
          >
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
      <div
        v-for="r in filteredRows"
        :key="r.name"
        class="card mb10"
        style="cursor: pointer"
        @click="$router.push({ name: 'de-xuat-detail', params: { ten: r.name } })"
      >
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
