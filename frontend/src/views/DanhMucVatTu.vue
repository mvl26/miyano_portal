<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'
import VatTuModal from '../components/VatTuModal.vue'

const isMobile = useIsMobile()
const rows = ref([])
const loading = ref(true)
const error = ref('')
const tim = ref('')
const caTat = ref(false)

const modalOpen = ref(false)
const modalMode = ref('tao')
const modalInitial = ref({})
const modalVatTu = ref('')
const modalCoPhatSinh = ref(false)

const exportUrl = api.khoDownloadUrl('kho_vat_tu_export')

const hienThi = computed(() => {
  const q = tim.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((r) => `${r.ma_vat_tu} ${r.ten_vat_tu}`.toLowerCase().includes(q))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.callKho('kho_vat_tu_list', { ca_tat: caTat.value ? 1 : 0 })
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục vật tư.'
  } finally {
    loading.value = false
  }
}

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
        <input type="checkbox" v-model="caTat" @change="load" />
        Hiện cả vật tư đã tắt
      </label>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!hienThi.length" class="empty">Chưa có vật tư nào.</div>

    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã</th><th>Tên</th><th>ĐVT</th><th>Mã hàng Miyano</th>
            <th>Quy cách</th><th>Nhóm</th><th>Đang dùng</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in hienThi" :key="r.name">
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
      <div v-for="r in hienThi" :key="r.name" class="card mb10">
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
