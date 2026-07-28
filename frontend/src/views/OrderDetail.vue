<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="stub">
    <h2>Chi tiết đơn {{ route.params.name }}</h2>
    <p class="sub">TODO Pass 2 — màn hình này sẽ được hoàn thiện ở lượt 2.</p>
    <router-link to="/orders"><button class="btn-o">← Quay lại</button></router-link>
  </div>
</template>
