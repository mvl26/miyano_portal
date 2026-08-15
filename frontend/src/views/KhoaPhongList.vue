<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'
import { fmtVND } from '../format'
import { useIsMobile } from '../useMobile'
import KhoaPhongModal from '../components/KhoaPhongModal.vue'
import PhanTrang from '../components/PhanTrang.vue'

const isMobile = useIsMobile()
const rows = ref([])
const loading = ref(true)
const error = ref('')
// Brief 2026-08-15 (phân trang) — truyền `limit` nên kho_khoa_phong_list
// trả dạng {rows, tong} (nhánh phân trang, KHÁC nhánh dropdown).
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

const modalOpen = ref(false)
const modalMode = ref('tao')
const modalInitial = ref({})

// "Bắt buộc chọn khoa phòng khi Xuất sử dụng" (US-E8.2/BR-CP2): CHỈ ĐỌC ở
// đây, KHÔNG có ô bấm để khách tự bật/tắt. Bản mẫu (pg-kkp) vẽ nó như một
// checkbox ngay trên màn này, nhưng 30_API_Spec.md không đặc tả endpoint
// nào cho khách tự đổi cờ này, và Customer Warehouse — đúng như bảy doctype
// kho còn lại — không có DocPerm nào cho role Customer (chỉ Miyano chỉnh
// qua Desk). Đây là NGHIỆP VỤ CHỦ ĐỘNG của Miyano (bắt buộc truy vết cấp
// phát), không phải một tuỳ chọn hiển thị của khách hàng, nên hiển thị
// trạng thái hiện tại làm THÔNG TIN, không dựng một endpoint mới để suy
// diễn hành vi ghi mà đặc tả chưa nói tới — xem ghi chú gửi kèm báo cáo epic.
const batBuoc = ref(null)

async function loadTrangThaiBatBuoc() {
  try {
    const me = await api.callKho('kho_me')
    batBuoc.value = !!me.bat_buoc_khoa_phong
  } catch (e) {
    batBuoc.value = null
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    // ca_inactive=1: khoa đã tắt vẫn phải hiện trong danh mục (làm mờ +
    // badge "Đã tắt"), không được biến mất — cùng lý do NccList.vue.
    const res = await api.callKho('kho_khoa_phong_list', {
      ca_inactive: 1,
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục khoa phòng.'
  } finally {
    loading.value = false
  }
}

watch([trang, soDong], load)

function moTao() {
  modalMode.value = 'tao'
  modalInitial.value = {}
  modalOpen.value = true
}

function moSua(r) {
  modalMode.value = 'sua'
  modalInitial.value = { name: r.name, ten_khoa_phong: r.ten_khoa_phong, ma_khoa: r.ma_khoa, ghi_chu: r.ghi_chu, active: r.active }
  modalOpen.value = true
}

function onSaved() {
  modalOpen.value = false
  load()
}

onMounted(() => {
  load()
  loadTrangThaiBatBuoc()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Danh mục khoa phòng</h2>
        <div class="sub">Nơi nhận cấp phát của kho — phiếu Xuất sử dụng chọn từ danh mục này</div>
      </div>
      <div class="flex" style="gap: 8px">
        <button class="btn btn-sm" @click="moTao">+ Thêm khoa phòng</button>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Danh mục khoa phòng</h2>
      <button class="btn btn-sm" @click="moTao">+ Thêm khoa phòng</button>
    </div>

    <div v-if="batBuoc !== null" class="note" :class="batBuoc ? 'note-b' : ''" style="margin-bottom: 12px">
      ⚙ Bắt buộc chọn khoa phòng khi Xuất sử dụng:
      <b>{{ batBuoc ? 'đang BẬT' : 'đang TẮT' }}</b>
      <span class="tag"> — chỉ áp phiếu tạo sau khi bật (BR-CP2); do Miyano cấu hình, liên hệ nhân viên kinh doanh nếu cần đổi.</span>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">
      Chưa có khoa phòng nào. Bấm "+ Thêm khoa phòng" để tạo khoa phòng đầu tiên — hoặc thêm ngay khi lập phiếu xuất.
    </div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Tên khoa phòng</th>
            <th>Mã khoa</th>
            <th class="right">Phiếu 90 ngày</th>
            <th class="right">Giá trị 90 ngày</th>
            <th>Trạng thái</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" :style="!r.active ? 'opacity:.55' : ''">
            <td><b>{{ r.ten_khoa_phong }}</b></td>
            <td>{{ r.ma_khoa || '—' }}</td>
            <td class="right">{{ r.so_phieu_90n }}</td>
            <td class="right">{{ fmtVND(r.gia_tri_90n) }}</td>
            <td>
              <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
                {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
              </span>
            </td>
            <td>
              <!-- LUÔN hiện "Sửa" — kể cả khoa đã tắt và đã dùng trên phiếu:
                   đây là đường DUY NHẤT để bật lại một khoa cũ (cùng lý do
                   NccList.vue — E3 đã trả giá vì thiếu ô nhập tương đương). -->
              <button class="btn-o btn-sm" @click="moSua(r)">Sửa</button>
              <div v-if="!r.active && r.so_phieu_90n" class="tag">đã dùng trên phiếu — không xoá được</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10" :style="!r.active ? 'opacity:.55' : ''">
        <div class="sb">
          <b>{{ r.ten_khoa_phong }}</b>
          <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
            {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
          </span>
        </div>
        <p class="tag" style="margin-top: 4px">Mã {{ r.ma_khoa || '—' }}</p>
        <p class="sb" style="margin-top: 8px; font-size: 13px">
          <span>{{ r.so_phieu_90n }} phiếu (90 ngày)</span>
          <b>{{ fmtVND(r.gia_tri_90n) }}</b>
        </p>
        <button class="btn-o btn-sm" style="margin-top: 8px" @click="moSua(r)">Sửa</button>
        <p v-if="!r.active && r.so_phieu_90n" class="tag" style="margin-top: 6px">đã dùng trên phiếu — không xoá được</p>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />

    <KhoaPhongModal :open="modalOpen" :initial="modalInitial" :mode="modalMode" @saved="onSaved" @close="modalOpen = false" />
  </div>
</template>
