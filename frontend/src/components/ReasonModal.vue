<script setup>
// Modal "lý do bắt buộc ≥ N ký tự" dùng chung — FormSpec quy định lỗi hiển
// thị TẠI TRƯỜNG (không phải window.prompt/alert của trình duyệt) cho mọi
// hành động "Không đồng ý"/"Huỷ" cần lý do (F-07 báo giá, F-23 huỷ yêu cầu).
import { ref, watch, computed } from 'vue'
import { useIsMobile } from '../useMobile'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'Cần lý do' },
  desc: { type: String, default: 'Lý do bắt buộc (≥ 10 ký tự) — được ghi vào chứng từ và gửi cho bên còn lại.' },
  placeholder: { type: String, default: '' },
  minLen: { type: Number, default: 10 },
  submitting: { type: Boolean, default: false },
  submitLabel: { type: String, default: 'Gửi' },
})
const emit = defineEmits(['submit', 'close'])

const isMobile = useIsMobile()
const value = ref('')
const touched = ref(false)

watch(
  () => props.open,
  (v) => {
    if (v) {
      value.value = ''
      touched.value = false
    }
  }
)

const err = computed(() => {
  if (!touched.value) return ''
  return value.value.trim().length < props.minLen
    ? `Vui lòng nhập ít nhất ${props.minLen} ký tự.`
    : ''
})

function submit() {
  touched.value = true
  if (value.value.trim().length < props.minLen) return
  emit('submit', value.value.trim())
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <h3 style="color: var(--red)">{{ title }}</h3>
      <p style="font-size: 13px; margin: 10px 0">{{ desc }}</p>
      <textarea
        v-model="value"
        rows="3"
        :placeholder="placeholder"
        @blur="touched = true"
      ></textarea>
      <div v-if="err" class="err" style="color: var(--red); font-size: 12px; margin-top: 4px">{{ err }}</div>
      <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
        <button class="btn-o" :disabled="submitting" @click="emit('close')">Quay lại</button>
        <button class="btn btn-danger" :disabled="submitting" @click="submit">
          {{ submitting ? 'Đang gửi…' : submitLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
