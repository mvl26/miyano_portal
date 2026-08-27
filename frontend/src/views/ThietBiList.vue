<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { useIsMobile } from '../useMobile'
import ThietBiModal from '../components/ThietBiModal.vue'
import PhanTrang from '../components/PhanTrang.vue'

// Task 12 — màn danh mục Thiết bị (khuôn giống DanhMucVatTu.vue: ô tìm
// debounce 300ms + checkbox "hiện cả đã tắt" + PhanTrang, KHÁC KhoaPhongList/
// NccList vốn luôn truyền ca_inactive:1 và không có ô tìm/checkbox riêng).
const isMobile = useIsMobile()
const rows = ref([])
const loading = ref(true)
const error = ref('')
const tim = ref('')
const hienCaTat = ref(false)
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)
let timTimer = null

const modalOpen = ref(false)
const modalMode = ref('tao')
const modalInitial = ref({})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.callKho('kho_thiet_bi_list', {
      tim_kiem: tim.value.trim() || undefined,
      ca_inactive: hienCaTat.value ? 1 : 0,
      limit: soDong.value,
      start: (trang.value - 1) * soDong.value,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục thiết bị.'
  } finally {
    loading.value = false
  }
}

watch([trang, soDong], load)

function locThayDoi() {
  trang.value = 1
  load()
}

// Debounce 300ms — cùng khuôn ô tìm của DanhMucVatTu.vue.
watch(tim, () => {
  clearTimeout(timTimer)
  trang.value = 1
  timTimer = setTimeout(() => load(), 300)
})

function moTao() {
  modalMode.value = 'tao'
  modalInitial.value = {}
  modalOpen.value = true
}

function moSua(r) {
  modalMode.value = 'sua'
  // Coi giá trị rỗng của server (null) là chuỗi rỗng để các ô input luôn ở
  // trạng thái "controlled" — `kho_thiet_bi_list` trả `nam_san_xuat: None`
  // khi trống, không tự chuẩn hoá về "" như các trường mô tả tự do khác.
  modalInitial.value = {
    ...r,
    khoa_phong: r.khoa_phong || '',
    nam_san_xuat: r.nam_san_xuat ?? '',
    ngay_lap_dat: r.ngay_lap_dat || '',
  }
  modalOpen.value = true
}

function onSaved() {
  modalOpen.value = false
  load()
}

onMounted(async () => {
  // Logic khoá ô Khoa phòng trong ThietBiModal đọc `store.me?.la_quan_ly` —
  // nạp trước khi tải danh sách, cùng khuôn LapPhieu.vue:719 (không nạp lại
  // nếu App.vue đã có sẵn).
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Best-effort — mất phần "biết vai trò để khoá ô" chứ không chặn màn.
    }
  }
  await load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Danh mục thiết bị</h2>
        <div class="sub">Máy đặt tại khoa phòng — dùng để chọn khi lập phiếu xuất sử dụng</div>
      </div>
      <div class="flex" style="gap: 8px">
        <button class="btn btn-sm" @click="moTao">+ Thêm thiết bị</button>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Danh mục thiết bị</h2>
      <button class="btn btn-sm" @click="moTao">+ Thêm thiết bị</button>
    </div>

    <div class="card mb10 flex" style="gap: 12px; align-items: center; flex-wrap: wrap">
      <input v-model="tim" placeholder="Tìm theo mã hoặc tên máy…" style="flex: 1; min-width: 200px" />
      <label style="display: flex; align-items: center; gap: 6px">
        <input type="checkbox" v-model="hienCaTat" @change="locThayDoi" />
        Hiện cả máy đã tắt
      </label>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">
      {{
        tim || hienCaTat
          ? 'Không có máy nào khớp bộ lọc.'
          : 'Chưa khai máy nào. Bấm Thêm để khai máy đầu tiên.'
      }}
    </div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã máy</th>
            <th>Tên máy</th>
            <th>Khoa phòng</th>
            <th>Hãng</th>
            <th>Xuất xứ</th>
            <th>Serial</th>
            <th>Trạng thái</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" :style="!r.active ? 'opacity:.55' : ''">
            <td>{{ r.ma_thiet_bi }}</td>
            <td><b>{{ r.ten_thiet_bi }}{{ r.active ? '' : ' (đã tắt)' }}</b></td>
            <td>{{ r.ten_khoa_phong || 'Dùng chung' }}</td>
            <td>{{ r.hang_san_xuat || '—' }}</td>
            <td>{{ r.xuat_xu || '—' }}</td>
            <td>{{ r.so_serial || '—' }}</td>
            <td>
              <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
                {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
              </span>
            </td>
            <td><button class="btn-o btn-sm" @click="moSua(r)">Sửa</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10" :style="!r.active ? 'opacity:.55' : ''">
        <div class="sb">
          <b>{{ r.ten_thiet_bi }}{{ r.active ? '' : ' (đã tắt)' }}</b>
          <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
            {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
          </span>
        </div>
        <p class="tag" style="margin-top: 4px">
          Mã {{ r.ma_thiet_bi }} · {{ r.ten_khoa_phong || 'Dùng chung' }}
        </p>
        <p class="tag" style="margin-top: 4px">
          {{ r.hang_san_xuat || '—' }} · {{ r.xuat_xu || '—' }} · Serial {{ r.so_serial || '—' }}
        </p>
        <button class="btn-o btn-sm" style="margin-top: 8px" @click="moSua(r)">Sửa</button>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />

    <ThietBiModal :open="modalOpen" :initial="modalInitial" :mode="modalMode" @saved="onSaved" @close="modalOpen = false" />
  </div>
</template>
