<script setup>
// Dải hai tab của màn "Danh sách đơn hàng" (spec 2026-10-12 §6.1): Đơn hàng
// và Yêu cầu báo giá là HAI danh sách, mỗi tab một route. Số trên tab báo giá
// là số báo giá đang chờ khách đồng ý.
import { ref, onMounted } from 'vue'
import api from '../api'

defineProps({ dang: { type: String, required: true } }) // 'don' | 'bao-gia'

const choDongY = ref(0)

onMounted(async () => {
  try {
    const res = await api.call('portal_bao_gia_dem')
    choDongY.value = res?.cho_dong_y || 0
  } catch (e) {
    // Số đếm là tiện ích: không tải được thì tab vẫn dùng được, chỉ thiếu số.
    console.warn('[TabDonBaoGia] không tải được số báo giá chờ đồng ý:', e)
  }
})
</script>

<template>
  <div class="tabs mb10">
    <router-link :to="{ name: 'yeu-cau' }" custom v-slot="{ navigate }">
      <button :class="{ on: dang === 'don' }" @click="navigate">Đơn hàng</button>
    </router-link>
    <router-link :to="{ name: 'bao-gia' }" custom v-slot="{ navigate }">
      <button :class="{ on: dang === 'bao-gia' }" @click="navigate">
        Yêu cầu báo giá
        <span v-if="choDongY" class="cartn">{{ choDongY }}</span>
      </button>
    </router-link>
  </div>
</template>
