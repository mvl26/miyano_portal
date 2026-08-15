<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'
import VatTuModal from '../components/VatTuModal.vue'
import PhanTrang from '../components/PhanTrang.vue'

const isMobile = useIsMobile()
const rows = ref([])
const loading = ref(true)
const error = ref('')
const tim = ref('')
const caTat = ref(false)
// Brief 2026-08-15 (phân trang) — truyền `limit` nên kho_vat_tu_list trả
// dạng {rows, tong} (nhánh phân trang của endpoint, KHÁC nhánh dropdown
// không truyền limit mà NhatKy.vue/BaoCaoNXT.vue dùng).
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)
let timTimer = null

const modalOpen = ref(false)
const modalMode = ref('tao')
const modalInitial = ref({})
const modalVatTu = ref('')
const modalCoPhatSinh = ref(false)

const exportUrl = api.khoDownloadUrl('kho_vat_tu_export')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.callKho('kho_vat_tu_list', {
      ca_tat: caTat.value ? 1 : 0,
      tim: tim.value.trim() || undefined,
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục vật tư.'
  } finally {
    loading.value = false
  }
}

watch([trang, soDong], load)
function locThayDoi() {
  trang.value = 1
  load()
}
// Debounce 300ms — cùng khuôn ngăn Mua lẻ của Catalog.vue.
watch(tim, () => {
  clearTimeout(timTimer)
  trang.value = 1
  timTimer = setTimeout(() => load(), 300)
})

function moTao() {
  modalMode.value = 'tao'
  modalInitial.value = {}
  modalVatTu.value = ''
  modalCoPhatSinh.value = false
  modalOpen.value = true
}

function moSua(r) {
  modalMode.value = 'sua'
  modalInitial.value = { ...r }
  modalVatTu.value = r.name
  modalCoPhatSinh.value = !!r.co_phat_sinh
  modalOpen.value = true
}

function onSaved() {
  modalOpen.value = false
  showToast('Đã lưu danh mục.')
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar">
      <h2>Danh mục vật tư</h2>
      <div class="flex" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn-sm" @click="moTao">+ Thêm vật tư</button>
        <a class="btn-o btn-sm" :href="exportUrl">⬇ Xuất danh mục</a>
        <router-link to="/kho/vat-tu/import" class="btn-o btn-sm">⬆ Nhập danh mục</router-link>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>

    <div class="card mb10 flex" style="gap: 12px; align-items: center; flex-wrap: wrap">
      <input v-model="tim" placeholder="Tìm theo mã hoặc tên…" style="flex: 1; min-width: 200px" />
      <label style="display: flex; align-items: center; gap: 6px">
        <input type="checkbox" v-model="caTat" @change="locThayDoi" />
        Hiện cả vật tư đã tắt
      </label>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">Chưa có vật tư nào.</div>

    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã</th><th>Tên</th><th>ĐVT</th><th>Mã hàng Miyano</th>
            <th>Quy cách</th><th>Nhóm</th><th>Đang dùng</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name">
            <td>{{ r.ma_vat_tu }}</td>
            <td>{{ r.ten_vat_tu }}</td>
            <td>{{ r.dvt }}</td>
            <td>{{ r.item_code || '—' }}</td>
            <td>{{ r.quy_cach || '—' }}</td>
            <td>{{ r.nhom || '—' }}</td>
            <td>
              <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
                {{ r.active ? 'Đang dùng' : 'Đã tắt' }}
              </span>
            </td>
            <td><button class="btn-o btn-sm" @click="moSua(r)">Sửa</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else>
      <div v-for="r in rows" :key="r.name" class="card mb10">
        <div class="sb">
          <b>{{ r.ma_vat_tu }}</b>
          <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
            {{ r.active ? 'Đang dùng' : 'Đã tắt' }}
          </span>
        </div>
        <div>{{ r.ten_vat_tu }}</div>
        <p class="tag">ĐVT {{ r.dvt }} · {{ r.item_code ? 'Mã Miyano ' + r.item_code : 'Mã riêng' }}</p>
        <button class="btn-o btn-sm" @click="moSua(r)">Sửa</button>
      </div>
    </div>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />

    <VatTuModal
      :open="modalOpen"
      :initial="modalInitial"
      :mode="modalMode"
      :vat-tu="modalVatTu"
      :co-phat-sinh="modalCoPhatSinh"
      @saved="onSaved"
      @close="modalOpen = false"
    />
  </div>
</template>
