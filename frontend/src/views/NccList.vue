<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { fmtVND } from '../format'
import { useIsMobile } from '../useMobile'
import NccModal from '../components/NccModal.vue'

const isMobile = useIsMobile()
const rows = ref([])
const loading = ref(true)
const error = ref('')

const modalOpen = ref(false)
const modalMode = ref('tao')
const modalInitial = ref({})

async function load() {
  loading.value = true
  error.value = ''
  try {
    // ca_inactive=1: NCC đã tắt vẫn phải hiện trong danh mục (làm mờ + badge
    // "Đã tắt"), không được biến mất — người dùng cần thấy lịch sử NCC từng
    // dùng, chỉ ô chọn trên phiếu mới lọc active=1.
    rows.value = await api.callKho('kho_ncc_list', { ca_inactive: 1 })
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục NCC.'
  } finally {
    loading.value = false
  }
}

function moTao() {
  modalMode.value = 'tao'
  modalInitial.value = {}
  modalOpen.value = true
}

function moSua(r) {
  modalMode.value = 'sua'
  modalInitial.value = { name: r.name, ten_ncc: r.ten_ncc, mst: r.mst, active: r.active }
  modalOpen.value = true
}

function onSaved() {
  modalOpen.value = false
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>NCC của tôi</h2>
        <div class="sub">Danh mục nhà cung ứng ngoài Miyano — phục vụ phiếu nhập mua ngoài</div>
      </div>
      <div class="flex" style="gap: 8px">
        <button class="btn btn-sm" @click="moTao">+ Thêm NCC</button>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>NCC của tôi</h2>
      <button class="btn btn-sm" @click="moTao">+ Thêm NCC</button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">
      Chưa có NCC nào. Bấm "+ Thêm NCC" để tạo NCC đầu tiên — hoặc thêm ngay khi lập phiếu "Mua ngoài".
    </div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Tên NCC</th>
            <th>MST</th>
            <th class="right">Số phiếu</th>
            <th class="right">Giá trị 90 ngày</th>
            <th>Trạng thái</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" :style="!r.active ? 'opacity:.55' : ''">
            <td><b>{{ r.ten_ncc }}</b></td>
            <td>{{ r.mst || '—' }}</td>
            <td class="right">{{ r.so_phieu }}</td>
            <td class="right">{{ fmtVND(r.gia_tri_90n) }}</td>
            <td>
              <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
                {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
              </span>
            </td>
            <td>
              <!-- LUÔN hiện "Sửa" — kể cả NCC đã tắt và đã dùng trên phiếu:
                   đây là đường DUY NHẤT để bật lại một NCC cũ (kho_ncc_save
                   cho toggle active hai chiều không giới hạn, chỉ frappe
                   không cho XOÁ hẳn — không có nút xoá nào ở màn này để thay
                   thế). Ẩn nút ở đây sẽ tự khoá luôn đường bật lại, giống
                   đúng bẫy "quy tắc có nhưng quên ô nhập" đã trả giá ở E3. -->
              <button class="btn-o btn-sm" @click="moSua(r)">Sửa</button>
              <div v-if="!r.active && r.so_phieu" class="tag">đã dùng trên phiếu — không xoá được</div>
            </td>
          </tr>
        </tbody>
      </table>
      <!-- Cột "Điện thoại" của bản mẫu KHÔNG dựng được: kho_ncc_list hiện chỉ
           trả name/ten_ncc/mst/so_phieu/gia_tri_90n/active — thiếu dien_thoai.
           Xem báo cáo cuối phần C. -->
    </div>

    <!-- MOBILE -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10" :style="!r.active ? 'opacity:.55' : ''">
        <div class="sb">
          <b>{{ r.ten_ncc }}</b>
          <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
            {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
          </span>
        </div>
        <p class="tag" style="margin-top: 4px">MST {{ r.mst || '—' }}</p>
        <p class="sb" style="margin-top: 8px; font-size: 13px">
          <span>{{ r.so_phieu }} phiếu</span>
          <b>{{ fmtVND(r.gia_tri_90n) }}</b>
        </p>
        <button class="btn-o btn-sm" style="margin-top: 8px" @click="moSua(r)">Sửa</button>
        <p v-if="!r.active && r.so_phieu" class="tag" style="margin-top: 6px">đã dùng trên phiếu — không xoá được</p>
      </div>
    </template>

    <NccModal :open="modalOpen" :initial="modalInitial" :mode="modalMode" @saved="onSaved" @close="modalOpen = false" />
  </div>
</template>
