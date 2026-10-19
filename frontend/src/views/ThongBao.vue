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
import Icon from '../components/Icon.vue'

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

    <div v-else class="card card-flush tb-ds">
      <div
        v-for="i in items"
        :key="i.name"
        class="tb-dong"
        :class="{ clickable: true, 'tb-moi': !i.da_doc, 'tb-dang-mo': dangMo === i.name }"
        role="button"
        tabindex="0"
        @click="mo(i)"
        @keydown.enter="mo(i)"
      >
        <span class="tb-cham" aria-hidden="true"></span>
        <div class="grow">
          <div class="sb ai-start">
            <b class="tb-tieu-de">{{ i.subject }}</b>
            <span v-if="!i.da_doc" class="badge b-blue shrink0">Mới</span>
          </div>
          <p v-if="i.noi_dung" class="tag tb-noi-dung" v-html="i.noi_dung"></p>
          <p class="tag mt6 row gap4"><Icon name="clock" :size="13" />{{ fmtDateTime(i.ngay) }}</p>
        </div>
        <Icon name="chevron-right" :size="18" class="tb-chev" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.tb-dong {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 20px 14px 16px; min-height: 56px; transition: background 0.15s ease;
}
.tb-dong + .tb-dong { border-top: 1px solid var(--line); }
.tb-dong:hover { background: var(--surface-2); }
.tb-dong:focus-visible { outline: none; box-shadow: inset var(--focus); }
.tb-dang-mo { opacity: 0.6; }
.tb-cham {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  margin-top: 7px; background: transparent;
}
.tb-moi .tb-cham { background: var(--accent); }
.tb-tieu-de { font-weight: 400; color: var(--text-2); line-height: 1.45; }
.tb-moi .tb-tieu-de { font-weight: 700; color: var(--text); }
.tb-moi { background: #fbfdff; }
.tb-noi-dung { margin-top: 4px; white-space: pre-line; line-height: 1.5; }
.tb-chev { color: var(--text-4); margin-top: 2px; flex-shrink: 0; }
.tb-dong:hover .tb-chev { color: var(--accent); }
@media (max-width: 900px) {
  .tb-dong { padding: 12px 14px 12px 12px; }
}
</style>
