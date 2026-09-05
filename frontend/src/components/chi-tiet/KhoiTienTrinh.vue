<script setup>
// Mốc tiến trình của đơn. Tách khỏi `OrderDetail.vue` 03/09/2026 để màn
// chi tiết GỘP dùng lại nguyên vẹn — không chép lần hai.
import { computed } from 'vue'
import { useIsMobile } from '../../useMobile'

const props = defineProps({ milestones: { type: Array, default: () => [] } })
const isMobile = useIsMobile()

// Bước hiện tại = mốc đầu tiên chưa hoàn thành (để tô cam như mockup).
const currentIdx = computed(() => props.milestones.findIndex((m) => !m.done))
function stepClass(m, idx) {
  if (m.done) return 'done'
  if (idx === currentIdx.value) return 'cur'
  return ''
}
</script>

<template>
  <div class="card mb10" style="margin-bottom: 14px">
    <div class="h3">Tiến trình</div>
    <!-- desktop: ngang -->
    <div v-if="!isMobile" class="tl">
      <div v-for="(m, i) in milestones" :key="m.key" class="st" :class="stepClass(m, i)">
        <div class="dot">{{ m.done ? '✓' : i + 1 }}</div>
        <div class="lb">{{ m.label }}</div>
      </div>
    </div>
    <!-- mobile: dọc -->
    <div v-else class="vtl">
      <div v-for="(m, i) in milestones" :key="m.key" class="vst" :class="stepClass(m, i)">
        <div class="vdot">{{ m.done ? '✓' : i + 1 }}</div>
        <div class="vlb"><b>{{ m.label }}</b>{{ m.done ? 'Hoàn thành' : (i === currentIdx ? 'Đang thực hiện' : 'Chưa thực hiện') }}</div>
      </div>
    </div>
  </div>
</template>
