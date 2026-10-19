<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { useIsMobile } from '../useMobile'
import ThietBiModal from '../components/ThietBiModal.vue'
import PhanTrang from '../components/PhanTrang.vue'
import Icon from '../components/Icon.vue'

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

// Vòng sửa 1 (review) — câu trạng thái rỗng PHẢI khớp thực trạng dữ liệu lúc
// đó, không chỉ khớp trạng thái ô lọc. Ba nhánh, đúng thứ tự ưu tiên:
//   1. Đang tìm (so `tim.trim()` — CÙNG điều kiện `load()` dùng để quyết định
//      có gửi `tim_kiem` hay không, không phải `tim` thô — gõ toàn khoảng
//      trắng thì server không lọc gì, câu "khớp bộ lọc" sẽ là câu sai).
//   2. Không tìm, CHƯA bật "Hiện cả máy đã tắt" — rỗng ở đây có thể vì kho
//      trống HOẶC vì mọi máy đều đã tắt (bị `ca_inactive:0` che đi); "Chưa
//      khai máy nào" là một lời NÓI DỐI khi rơi vào ca thứ hai (máy đó vẫn
//      tồn tại) và còn xui người dùng tạo trùng thay vì bật bộ lọc — không
//      biết chắc ca nào nên câu phải mời cả hai lối ra, không khẳng định.
//   3. Không tìm, ĐÃ bật "Hiện cả máy đã tắt" — `ca_inactive:1` đã cho thấy
//      MỌI máy (kể cả đã tắt) rồi mà vẫn rỗng, nên đây mới thật sự là "chưa
//      khai máy nào" — hienCaTat là cờ MỞ RỘNG phạm vi (không bao giờ làm
//      hẹp kết quả), nên nó không thuộc nhánh (1)/"đang lọc" như bản trước.
const trangThaiRong = computed(() => {
  if (tim.value.trim()) return 'Không có máy nào khớp bộ lọc.'
  if (!hienCaTat.value) {
    return 'Không có máy nào đang hoạt động. Bấm "Hiện cả máy đã tắt" để xem máy đã tắt, hoặc Thêm để khai máy mới.'
  }
  return 'Chưa khai máy nào. Bấm Thêm để khai máy đầu tiên.'
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
      <div class="row gap8">
        <router-link to="/kho" class="btn-o btn-sm"><Icon name="arrow-left" :size="16" />Quay lại</router-link>
        <button class="btn btn-sm" @click="moTao"><Icon name="plus" :size="16" />Thêm thiết bị</button>
      </div>
    </div>
    <div class="sb mb12 gap8" v-else>
      <h2 class="mb0">Danh mục thiết bị</h2>
      <button class="btn btn-sm shrink0" @click="moTao"><Icon name="plus" :size="16" />Thêm thiết bị</button>
    </div>

    <div class="card mb10 flex wrap gap12 loc-tb">
      <div class="o-tim">
        <Icon name="search" :size="16" class="o-tim-ic" />
        <input v-model="tim" placeholder="Tìm theo mã hoặc tên máy…" />
      </div>
      <label class="o-tich">
        <input type="checkbox" v-model="hienCaTat" @change="locThayDoi" />
        Hiện cả máy đã tắt
      </label>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">{{ trangThaiRong }}</div>

    <!-- DESKTOP -->
    <div v-else-if="!isMobile" class="card card-flush">
      <div class="tbl-scroll">
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
          <tr v-for="r in rows" :key="r.name" :class="{ 'dong-tat': !r.active }">
            <td class="cell-code">{{ r.ma_thiet_bi }}</td>
            <td><b>{{ r.ten_thiet_bi }}{{ r.active ? '' : ' (đã tắt)' }}</b></td>
            <td>{{ r.ten_khoa_phong || 'Dùng chung' }}</td>
            <td>{{ r.hang_san_xuat || '—' }}</td>
            <td>{{ r.xuat_xu || '—' }}</td>
            <td class="mono">{{ r.so_serial || '—' }}</td>
            <td>
              <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
                {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
              </span>
            </td>
            <td class="right"><button class="btn-o btn-sm" @click="moSua(r)"><Icon name="pencil" :size="15" />Sửa</button></td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <!-- MOBILE -->
    <template v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10" :class="{ 'the-tat': !r.active }">
        <div class="sb ai-start">
          <b>{{ r.ten_thiet_bi }}{{ r.active ? '' : ' (đã tắt)' }}</b>
          <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
            {{ r.active ? 'Hoạt động' : 'Đã tắt' }}
          </span>
        </div>
        <p class="tag mt4">
          Mã {{ r.ma_thiet_bi }} · {{ r.ten_khoa_phong || 'Dùng chung' }}
        </p>
        <p class="tag mt4">
          {{ r.hang_san_xuat || '—' }} · {{ r.xuat_xu || '—' }} · Serial {{ r.so_serial || '—' }}
        </p>
        <button class="btn-o btn-sm mt8" @click="moSua(r)"><Icon name="pencil" :size="15" />Sửa</button>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />

    <ThietBiModal :open="modalOpen" :initial="modalInitial" :mode="modalMode" @saved="onSaved" @close="modalOpen = false" />
  </div>
</template>

<style scoped>
.loc-tb { align-items: center; padding: 12px 16px; }
.o-tim { position: relative; flex: 1; min-width: 200px; }
.o-tim input { padding-left: 36px; }
.o-tim-ic { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--text-3); pointer-events: none; }
.o-tich { display: flex; align-items: center; gap: 8px; min-height: 40px; cursor: pointer; font-size: 14px; }
tr.dong-tat td { opacity: 0.55; }
.the-tat { opacity: 0.55; }
</style>
