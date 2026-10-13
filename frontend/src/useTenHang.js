// Kho tên mặt hàng dùng chung cho mọi bảng của cổng — xem `ten-hang.js`.
//
// Một kho cho cả phiên: mã đã hỏi rồi không hỏi lại khi đi từ Giỏ hàng sang
// Chi tiết đơn. Đăng xuất là tải lại trang (`App.vue`), nên kho không sống
// qua hai đơn vị khác nhau.

import { reactive } from 'vue'
import { callHangHoa } from './api'
import { maCanNap } from './ten-hang'

const kho = reactive({})
const dangCho = new Set() // mã chờ gom vào lời gọi kế tiếp
const dangHoi = new Set() // mã đã gửi đi, chưa có trả lời
let henGio = null

// Mỗi dòng của bảng tự xin tên cho mã của nó (`CotTenHang.vue`); gom mọi lời
// xin trong cùng một nhịp vẽ thành MỘT lời gọi — bảng 50 dòng là một request,
// không phải 50.
export function napTenHang(codes) {
  for (const m of maCanNap(codes, kho)) if (!dangHoi.has(m)) dangCho.add(m)
  if (dangCho.size && !henGio) henGio = setTimeout(guiDi, 0)
}

async function guiDi() {
  henGio = null
  const lo = [...dangCho]
  dangCho.clear()
  if (!lo.length) return
  lo.forEach((m) => dangHoi.add(m))
  try {
    const out = await callHangHoa('portal_ten_hang', { item_codes: JSON.stringify(lo) })
    for (const m of lo) kho[m] = out?.[m] || { item_name: '', ten_thuong_goi: [] }
  } catch (e) {
    // Lỗi mạng không được làm hỏng bảng: ô tên thường gọi hiện "—" và mã
    // được hỏi lại ở lần vẽ sau.
  } finally {
    lo.forEach((m) => dangHoi.delete(m))
  }
}

export function tenTrongKho(ma) {
  return kho[ma] || null
}
