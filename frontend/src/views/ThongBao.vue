<script setup>
// Brief 2026-08-15 (trang thông báo) Phần 4 — "trang thông báo hiển thị
// những gì mới ... và link thẳng đến chứng từ đó". Bấm dòng nào -> gọi
// `portal_thong_bao_doc` (kiểm sở hữu + suy link ở SERVER, không tự đoán
// route ở client) rồi điều hướng NGAY TRONG SPA (router.push, không đổi
// window.location — giữ state trong bộ nhớ, đúng cảnh báo "gõ URL làm mất
// state" của controller).
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { fmtDateTime } from '../format'
import { store } from '../store'
import { showToast } from '../toast'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const items = ref([])
const dangMo = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.call('portal_thong_bao_list', { limit: 50 })
    items.value = res.items || []
    store.setChuaDocThongBao(res.chua_doc || 0)
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách thông báo.'
  } finally {
    loading.value = false
  }
}

async function mo(item) {
  if (dangMo.value) return
  dangMo.value = item.name
  try {
    const res = await api.call('portal_thong_bao_doc', { name: item.name })
    // Cập nhật NGAY tại chỗ — khỏi gọi lại portal_thong_bao_list chỉ để đổi
    // một dòng từ chưa đọc sang đã đọc.
    const dong = items.value.find((i) => i.name === item.name)
    if (dong && !dong.da_doc) {
      dong.da_doc = true
      store.setChuaDocThongBao(Math.max(0, store.chuaDocThongBao - 1))
    }
    if (res.link) {
      router.push(res.link)
    } else if (item.doc_type) {
      showToast('Không mở được chứng từ này (có thể đã bị huỷ hoặc không thuộc đơn vị của bạn).', 'error')
    }
  } catch (e) {
    showToast(e.message || 'Không mở được thông báo này.', 'error')
  } finally {
    dangMo.value = null
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <h2>Thông báo</h2>
        <div class="sub">Những gì mới với đơn vị của bạn — bấm để xem chứng từ</div>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!items.length" class="empty">Chưa có thông báo nào.</div>

    <template v-else>
      <div
        v-for="i in items"
        :key="i.name"
        class="card mb10"
        :class="{ clickable: true }"
        :style="{
          opacity: dangMo === i.name ? 0.6 : 1,
          borderLeft: i.da_doc ? '3px solid var(--line)' : '3px solid var(--orange)',
        }"
        @click="mo(i)"
      >
        <div class="sb">
          <b :style="{ fontWeight: i.da_doc ? 400 : 700 }">{{ i.subject }}</b>
          <span v-if="!i.da_doc" class="badge b-orange">Mới</span>
        </div>
        <p v-if="i.noi_dung" class="tag" style="margin-top: 4px; white-space: pre-line" v-html="i.noi_dung"></p>
        <p class="tag" style="margin-top: 6px">{{ fmtDateTime(i.ngay) }}</p>
      </div>
    </template>
  </div>
</template>
