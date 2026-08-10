<script setup>
// Danh sách dòng lỗi của một lần xem trước import — dùng chung cho mọi màn
// import Excel theo khung ba bước (ImportTonDau.vue, ImportDanhMuc.vue).
// Mỗi dòng backend trả về { line, ma_vat_tu, errors: [...] }.
defineProps({
  rows: { type: Array, default: () => [] },
})
</script>

<template>
  <div v-if="rows.length" class="mt10" style="margin-top: 14px">
    <p class="warn">Sửa các dòng sau trong tệp rồi tải lại — chưa có dữ liệu nào được ghi:</p>
    <div v-for="row in rows" :key="row.line" class="rowline">
      <span><b>Dòng {{ row.line }}</b> ({{ row.ma_vat_tu }})</span>
      <span style="color: var(--red)">{{ row.errors.join('; ') }}</span>
    </div>
  </div>
</template>
