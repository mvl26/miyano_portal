<script setup>
// Danh sách dòng lỗi của một lần xem trước import — dùng chung cho mọi màn
// import Excel theo khung ba bước (ImportTonDau.vue, ImportDanhMuc.vue).
// Mỗi dòng backend trả về { line, ma_vat_tu, errors: [...] }.
import Icon from './Icon.vue'

defineProps({
  rows: { type: Array, default: () => [] },
})
</script>

<template>
  <div v-if="rows.length" class="note note-loi note-ic mt10 mt14">
    <Icon name="alert-circle" :size="18" />
    <div class="grow">
      <p class="warn fs13">Sửa các dòng sau trong tệp rồi tải lại — chưa có dữ liệu nào được ghi:</p>
      <div v-for="row in rows" :key="row.line" class="rowline dong-loi-tep">
        <span class="nowrap"><b>Dòng {{ row.line }}</b> (<span class="mono">{{ row.ma_vat_tu }}</span>)</span>
        <span class="text-red loi-ds">{{ row.errors.join('; ') }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Dòng lỗi trong banner đỏ: vạch ngăn theo tông đỏ nhạt, lý do lỗi căn phải
   và được xuống dòng trên màn hẹp. */
.dong-loi-tep { border-bottom-color: #efc4c4; align-items: flex-start; }
.loi-ds { text-align: right; overflow-wrap: anywhere; }
@media (max-width: 900px) {
  .dong-loi-tep { flex-direction: column; gap: 2px; }
  .loi-ds { text-align: left; }
}
</style>
