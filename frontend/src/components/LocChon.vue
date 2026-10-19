<script setup>
import { ref, computed, watch } from 'vue'
import Icon from './Icon.vue'

// Ô lọc "tìm kiếm + dropdown" (màn Đặt hàng: Nhóm vật tư, Nhà cung cấp).
// Gõ để thu hẹp danh sách, bấm một dòng để chọn; dòng đầu "Tất cả" = bỏ lọc
// (modelValue ''). Lọc KHÔNG DẤU phía client — danh sách lựa chọn nhỏ, đã có
// đủ trong tay, không cần gọi lại server mỗi phím gõ.
// `@mousedown.prevent` (không `@click`) — cùng lý do `ThietBiPicker.vue`: blur
// của ô nhập đóng dropdown TRƯỚC khi click kịp chạy.
const props = defineProps({
  modelValue: { type: String, default: '' },
  // [{ value, label }] hoặc [string]
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Tất cả' },
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const tuKhoa = ref('')

const ds = computed(() =>
  props.options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o))
)
const nhanDaChon = computed(() => ds.value.find((o) => o.value === props.modelValue)?.label || '')

const khongDau = (s) =>
  (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase()

const loc = computed(() => {
  const k = khongDau(tuKhoa.value.trim())
  return k ? ds.value.filter((o) => khongDau(o.label).includes(k)) : ds.value
})

// Ô nhập hiện NHÃN đã chọn khi đóng, chữ đang gõ khi mở.
watch(nhanDaChon, (v) => { if (!open.value) tuKhoa.value = v }, { immediate: true })

function moRa() {
  open.value = true
  tuKhoa.value = ''
}
function dong() {
  open.value = false
  tuKhoa.value = nhanDaChon.value
}
function chon(v) {
  emit('update:modelValue', v)
  open.value = false
  tuKhoa.value = ds.value.find((o) => o.value === v)?.label || ''
}
</script>

<template>
  <div class="loc-chon">
    <input
      v-model="tuKhoa"
      :placeholder="open ? 'Gõ để tìm…' : placeholder"
      @focus="moRa"
      @blur="dong"
      @keydown.esc="$event.target.blur()"
      @keydown.enter.prevent="loc.length && chon(loc[0].value)"
    />
    <button
      v-if="modelValue"
      class="loc-xoa"
      title="Bỏ lọc"
      aria-label="Bỏ lọc"
      @mousedown.prevent="chon('')"
    ><Icon name="x" :size="16" /></button>
    <div v-if="open" class="loc-ds">
      <div class="loc-dong" :class="{ on: !modelValue }" @mousedown.prevent="chon('')">
        <span class="grow">Tất cả</span><Icon v-if="!modelValue" name="check" :size="16" class="loc-tick" />
      </div>
      <div
        v-for="o in loc"
        :key="o.value"
        class="loc-dong"
        :class="{ on: o.value === modelValue }"
        @mousedown.prevent="chon(o.value)"
      ><span class="grow">{{ o.label }}</span><Icon v-if="o.value === modelValue" name="check" :size="16" class="loc-tick" /></div>
      <div v-if="!loc.length" class="loc-dong muted">Không có lựa chọn khớp</div>
    </div>
  </div>
</template>

<style scoped>
.loc-chon { position: relative; }
.loc-chon input { width: 100%; padding-right: 40px; }
.loc-xoa {
  position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
  width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center;
  border: none; background: none; border-radius: var(--r-sm); line-height: 1; cursor: pointer; color: var(--text-3);
}
.loc-xoa:hover { background: var(--surface-2); color: var(--navy); }
.loc-ds {
  position: absolute; z-index: 20; left: 0; right: 0; top: calc(100% + 4px);
  max-height: 260px; overflow-y: auto; background: var(--surface); padding: 4px;
  border: 1px solid var(--line); border-radius: var(--r-md); box-shadow: var(--sh-2);
}
.loc-dong {
  display: flex; align-items: center; gap: 8px; min-height: 36px;
  padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 14px; color: var(--text);
}
.loc-dong:hover { background: var(--surface-2); }
.loc-dong.on { font-weight: 600; color: var(--navy); background: var(--accent-soft); }
.loc-dong.muted { color: var(--text-3); cursor: default; }
.loc-dong.muted:hover { background: none; }
.loc-tick { color: var(--accent); }
@media (max-width: 900px) {
  .loc-xoa { width: 40px; height: 40px; right: 0; }
  .loc-dong { min-height: 44px; }
}
</style>
