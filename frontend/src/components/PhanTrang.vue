<script setup>
// Component phân trang DÙNG CHUNG cho toàn cổng (brief 2026-08-15). Chọn
// 10/20/50 dòng/trang, điều hướng trang, hiện "Hiện X–Y trong N bản ghi".
// KHÔNG màn nào được tự chế phân trang riêng — mọi màn danh sách dùng
// component này.
//
// Lựa chọn số dòng/trang được NHỚ giữa các màn qua localStorage (một khoá
// dùng chung `KHOA_LUU`): khách chọn 20 ở Đơn hàng thì mở sang Hoá đơn cũng
// thấy 20, không phải chọn lại. Component tự đọc/ghi khoá này — màn gọi nó
// không cần biết gì về localStorage.
//
// Props/v-model:
//   :tong="soBanGhi"        - tổng số bản ghi (từ endpoint, field `tong`)
//   v-model:trang="trang"   - trang hiện tại (1-based)
//   v-model:so-dong="soDong" - số dòng mỗi trang (10/20/50)
//
// Màn gọi tự chịu trách nhiệm gọi lại API khi `trang`/`soDong` đổi (thường
// qua `watch([trang, soDong], load)`) — component này KHÔNG tự gọi API, chỉ
// quản lý trạng thái trang + hiển thị.
import { computed, onMounted } from 'vue'

const props = defineProps({
  tong: { type: Number, default: 0 },
})

const trang = defineModel('trang', { type: Number, default: 1 })
const soDong = defineModel('soDong', { type: Number, default: 20 })

const TUY_CHON = [10, 20, 50]
const KHOA_LUU = 'miyano_portal:so_dong_moi_trang'

onMounted(() => {
  // Nạp lựa chọn đã lưu từ MÀN KHÁC — chỉ ghi đè nếu khác giá trị mặc định
  // hiện tại, và chỉ khi giá trị lưu hợp lệ (tránh localStorage bị sửa tay
  // hoặc hỏng biến limit thành NaN trên dây).
  let daLuu
  try {
    daLuu = Number(localStorage.getItem(KHOA_LUU))
  } catch (e) {
    daLuu = NaN
  }
  if (TUY_CHON.includes(daLuu) && daLuu !== soDong.value) {
    soDong.value = daLuu
  }
})

function chonSoDong(n) {
  n = Number(n)
  if (!TUY_CHON.includes(n)) return
  soDong.value = n
  trang.value = 1 // đổi số dòng/trang thì về lại trang 1 — trang cũ có thể không còn tồn tại
  try {
    localStorage.setItem(KHOA_LUU, String(n))
  } catch (e) {
    // localStorage có thể bị chặn (chế độ ẩn danh) — không phải lỗi đáng chặn UI.
  }
}

const tongTrang = computed(() => Math.max(1, Math.ceil(props.tong / soDong.value)))
const batDau = computed(() => (props.tong === 0 ? 0 : (trang.value - 1) * soDong.value + 1))
const ketThuc = computed(() => Math.min(trang.value * soDong.value, props.tong))

function trangTruoc() {
  if (trang.value > 1) trang.value -= 1
}
function trangSau() {
  if (trang.value < tongTrang.value) trang.value += 1
}
</script>

<template>
  <div class="phan-trang" v-if="tong > 0">
    <div class="tag">Hiện {{ batDau }}–{{ ketThuc }} trong {{ tong }} bản ghi</div>
    <div class="phan-trang-dieu-khien">
      <select :value="soDong" @change="chonSoDong($event.target.value)" aria-label="Số dòng mỗi trang">
        <option v-for="n in TUY_CHON" :key="n" :value="n">{{ n }} / trang</option>
      </select>
      <button class="btn-o btn-sm" :disabled="trang <= 1" @click="trangTruoc">‹ Trước</button>
      <span class="tag" style="white-space: nowrap">Trang {{ trang }}/{{ tongTrang }}</span>
      <button class="btn-o btn-sm" :disabled="trang >= tongTrang" @click="trangSau">Sau ›</button>
    </div>
  </div>
</template>

<style scoped>
.phan-trang {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 4px;
}
.phan-trang-dieu-khien {
  display: flex;
  align-items: center;
  gap: 8px;
}
.phan-trang-dieu-khien select {
  padding: 6px 8px;
  font-size: 13px;
}
</style>
