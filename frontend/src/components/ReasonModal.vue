<script setup>
// Modal "lý do bắt buộc ≥ N ký tự" dùng chung — FormSpec quy định lỗi hiển
// thị TẠI TRƯỜNG (không phải window.prompt/alert của trình duyệt) cho mọi
// hành động "Không đồng ý"/"Huỷ" cần lý do (F-07 báo giá, F-23 huỷ yêu cầu).
import { ref, watch, computed } from 'vue'
import { useIsMobile } from '../useMobile'
import Icon from './Icon.vue'

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
    <div class="card" :class="{ in: isMobile }">
      <div v-if="isMobile" class="grab"></div>
      <h3 class="text-red">{{ title }}</h3>
      <p class="fs13 text-2 mo-ta">{{ desc }}</p>
      <textarea
        v-model="value"
        rows="3"
        :placeholder="placeholder"
        @blur="touched = true"
      ></textarea>
      <div v-if="err" class="err text-red fs12 mt4 inline-flex gap4"><Icon name="alert-circle" :size="14" />{{ err }}</div>
      <div class="flex jc-end mt14 gap8 wrap">
        <button class="btn-o" :disabled="submitting" @click="emit('close')">Quay lại</button>
        <button class="btn btn-danger" :disabled="submitting" @click="submit">
          {{ submitting ? 'Đang gửi…' : submitLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mo-ta { margin: 10px 0; }
</style>
