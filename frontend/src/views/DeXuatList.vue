<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDateTime, deXuatBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'

const isMobile = useIsMobile()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const filter = ref('') // '' = Tất cả

// Chip theo ĐÚNG các giá trị `trang_thai` của doctype (`Nháp / Chờ duyệt /
// Đã duyệt / Chờ duyệt sửa / Từ chối / Đã huỷ`) — TẤT CẢ, không thiếu cái
// nào.
//
// Việc (d) — bản đầu bỏ "Chờ duyệt sửa" vì brief task-3 chỉ liệt kê sáu
// chip. Nhưng đó là một trạng thái THẬT mà người dùng tự đưa phiếu vào: vừa
// bấm "Xin sửa số lượng" xong, phiếu rời "Đã duyệt" sang "Chờ duyệt sửa" —
// bấm "Đã duyệt" không thấy, bấm "Chờ duyệt" cũng không thấy, chỉ "Tất cả"
// mới ra. Người vừa gửi yêu cầu là người đi tìm nó ngay sau đó.
const FILTERS = ['', 'Nháp', 'Chờ duyệt', 'Đã duyệt', 'Chờ duyệt sửa', 'Từ chối', 'Đã huỷ']

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

watch(filter, (f) => {
  // C3 — chip đang chọn sống trong URL để nút "Quay lại" của màn chi tiết
  // dựng lại được đúng nó. `replace`: đổi chip không phải một bước lịch sử.
  router.replace({ name: 'de-xuat', query: f ? { chip: f } : {} })
  load()
})

// C3 — ghi NƠI ĐÃ TỚI vào query khi mở phiếu, để màn chi tiết quay về đúng
// danh sách này kèm đúng chip (và App.vue sáng đúng mục nav — việc (c)).
//
// Vòng sửa 1 (review, Task 8) — phiếu Nháp mở sang màn SỬA (`de-xuat-lap`),
// không phải màn chi tiết chỉ đọc (`de-xuat-detail`): `DeXuatDetail.vue`
// không có ô nhập số lượng cho `so_luong_de_xuat` ("Khoá vĩnh viễn từ lúc
// gửi duyệt" — đúng cho MỌI trạng thái SAU Nháp, nhưng một phiếu Nháp thì
// chưa từng gửi duyệt). Thiếu nhánh này, một phiếu Lưu-nháp-rồi-đóng-tab
// không còn đường nào sửa lại — đúng phát hiện Critical của vòng review 1.
function moPhieu(r) {
  if (r.trang_thai === 'Nháp') {
    router.push({ name: 'de-xuat-lap', params: { ten: r.name } })
    return
  }
  router.push({
    name: 'de-xuat-detail',
    params: { ten: r.name },
    query: { tu: 'de-xuat', ...(filter.value ? { chip: filter.value } : {}) },
  })
}

onMounted(async () => {
  loadKhoaPhongList()
  // C3 — khôi phục chip từ URL. Đặt TRƯỚC `load()` cuối hàm; gán vào
  // `filter` kích hoạt watch ở trên nên `load()` chạy đúng một lần với chip
  // đã khôi phục... trừ khi query trống, nên vẫn gọi `load()` như cũ ở dưới
  // và chấp nhận một lời gọi thừa duy nhất khi có `?chip=` (rẻ hơn nhiều so
  // với một nhánh điều kiện quanh `load()`).
  if (route.query.chip && FILTERS.includes(String(route.query.chip))) {
    filter.value = String(route.query.chip)
  }
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
      <!-- Vòng sửa 1 — lối vào TẠO PHIẾU MỚI ngay tại danh sách, cùng khuôn
           "+ Tạo phiếu ..." của PhieuNhap.vue/PhieuXuat.vue. Mục nav
           "Lập phiếu đề xuất" (App.vue) đã có nhưng chỉ hiện ở sidebar
           desktop — nút này là lối vào THỨ HAI, ngay tại nơi khách đang
           nhìn danh sách của họ. -->
      <router-link :to="{ name: 'de-xuat-lap' }"><button class="btn">+ Lập phiếu</button></router-link>
    </div>
    <div v-else class="mb10">
      <router-link :to="{ name: 'de-xuat-lap' }"><button class="btn btn-sm">+ Lập phiếu</button></router-link>
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
    <!-- Việc (b) — câu rỗng phải nói ĐÚNG VAI người đang đọc. Quản lý xem
         phạm vi toàn đơn vị (subtitle ở trên đã nói vậy) mà câu rỗng lại
         bảo "Khoa chưa có phiếu" — hai câu trên cùng một màn nói hai phạm vi
         khác nhau, và câu sai là câu duy nhất hiện khi màn trống. -->
    <div v-else-if="!rows.length" class="empty">
      {{ store.me?.la_quan_ly ? 'Đơn vị chưa có phiếu đề xuất nào.' : 'Khoa chưa có phiếu đề xuất nào.' }}
    </div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã phiếu</th><th>Khoa phòng</th><th>Trạng thái</th><th>Thời điểm gửi</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in rows"
            :key="r.name"
            style="cursor: pointer"
            @click="moPhieu(r)"
          >
            <td>
              <b v-if="r.ma_de_xuat">{{ r.ma_de_xuat }}</b>
              <span v-else class="tag">(chưa gửi duyệt)</span>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td><span class="badge" :class="deXuatBadge(r.trang_thai)">{{ r.trang_thai }}</span></td>
            <td>{{ r.thoi_diem_gui ? fmtDateTime(r.thoi_diem_gui) : '—' }}</td>
            <!-- Vòng sửa 1 — nút SỬA tường minh cho phiếu Nháp, không chỉ
                 dựa vào việc cả dòng bấm được (đúng góp ý review: một tính
                 năng không có LỐI VÀO NHÌN THẤY ĐƯỢC coi như không tồn tại
                 — dự án này đã dính lỗi đó hai lần). `.stop` vì dòng cha đã
                 tự có `@click="moPhieu(r)"` (cùng đích cho phiếu Nháp) —
                 chặn nổi bọt để khỏi điều hướng hai lần. -->
            <td>
              <button v-if="r.trang_thai === 'Nháp'" class="btn-o btn-sm" @click.stop="moPhieu(r)">Sửa</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div
        v-for="r in rows"
        :key="r.name"
        class="card mb10"
        style="cursor: pointer"
        @click="moPhieu(r)"
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
        <button
          v-if="r.trang_thai === 'Nháp'"
          class="btn-o btn-sm"
          style="margin-top: 8px"
          @click.stop="moPhieu(r)"
        >Sửa</button>
      </div>
    </template>
  </div>
</template>
