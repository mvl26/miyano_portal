<script setup>
import { ref, computed, watch } from 'vue'

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
      @mousedown.prevent="chon('')"
    >×</button>
    <div v-if="open" class="loc-ds">
      <div class="loc-dong" :class="{ on: !modelValue }" @mousedown.prevent="chon('')">
        Tất cả
      </div>
      <div
        v-for="o in loc"
        :key="o.value"
        class="loc-dong"
        :class="{ on: o.value === modelValue }"
        @mousedown.prevent="chon(o.value)"
      >{{ o.label }}</div>
      <div v-if="!loc.length" class="loc-dong muted">Không có lựa chọn khớp</div>
    </div>
  </div>
</template>

<style scoped>
.loc-chon { position: relative; }
.loc-chon input { width: 100%; padding-right: 28px; }
.loc-xoa {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  border: none; background: none; font-size: 18px; line-height: 1; cursor: pointer; color: var(--gray);
}
.loc-ds {
  position: absolute; z-index: 20; left: 0; right: 0; top: calc(100% + 2px);
  max-height: 260px; overflow-y: auto; background: #fff;
  border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 6px 18px rgba(0, 0, 0, 0.1);
}
.loc-dong { padding: 8px 12px; cursor: pointer; font-size: 14px; }
.loc-dong:hover { background: var(--bg); }
.loc-dong.on { font-weight: 600; }
</style>
