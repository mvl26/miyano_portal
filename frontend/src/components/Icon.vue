<script setup>
import { computed } from 'vue'
import { ICONS } from '../icons'

// Icon SVG nội bộ (bộ vẽ theo Lucide trong `icons.js`). Mặc định là icon
// TRANG TRÍ (aria-hidden) — chữ bên cạnh đã nói nghĩa. Nút chỉ có icon thì
// truyền `label`: icon thành role="img" có tên đọc được.
const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  stroke: { type: [Number, String], default: 2 },
  label: { type: String, default: '' },
})

const body = computed(() => {
  const b = ICONS[props.name]
  if (!b && import.meta.env.DEV) console.warn(`Icon "${props.name}" chưa có trong icons.js`)
  return b || ''
})
</script>

<template>
  <svg
    class="ic"
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
    v-html="body"
  />
</template>
