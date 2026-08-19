// Hàng chờ duyệt của quản lý — MỘT nguồn sự thật cho cả ba nơi cần nó:
// shell `App.vue` (badge trên mục nav), màn `/duyet` (bảng), và
// `DeXuatDetail.vue` (nạp lại badge sau khi duyệt/từ chối xong).
//
// Gộp ở đây thay vì chép ba lần: `de_xuat_danh_sach` chỉ nhận MỘT
// `trang_thai` mỗi lần gọi (truyền mảng vào tham số đó vướng đúng cái bẫy
// filter Frappe coi list 2 phần tử là `(operator, value)` thay vì `in`), nên
// "hàng chờ" luôn là HAI lời gọi song song. Ba bản sao của cùng một quy ước
// hai-lời-gọi-cộng-lại là ba chỗ để trôi khỏi nhau — và chúng ĐÃ trôi: cả
// ba đều cứng `limit: 200` mà không nơi nào nói gì khi bị cắt.
//
// File CỐ Ý là JS thuần (không import Vue) — cùng khuôn de-xuat-actions.js.
// `tests/test_de_xuat_action_registry.py` quét MỌI file .vue/.js dưới
// `frontend/src` nên tên endpoint viết ở đây vẫn được canh.
import api from './api'

// Trần một lời gọi. `de_xuat_danh_sach` cắt ở `limit_page_length` và KHÔNG
// trả về tổng số — nên "số dòng trả về CHẠM trần" là tín hiệu duy nhất có
// thể đọc được rằng danh sách còn nữa. Nó có thể báo nhầm khi tổng đúng
// bằng 200 (hiếm, và chỉ tốn một dòng nhắc), nhưng chiều ngược lại — im
// lặng cắt mất phiếu của một khoa — là chiều làm phiếu nằm đó không ai duyệt.
export const GIOI_HAN_CHO_DUYET = 200

export const TRANG_THAI_CHO_DUYET = ['Chờ duyệt', 'Chờ duyệt sửa']

// Trả về `{ rows, biCat }`. `biCat = true` nghĩa danh sách CÓ THỂ còn phiếu
// chưa hiện — người gọi phải nói ra, không được nuốt.
export async function napHangChoDuyet() {
  const ketQua = await Promise.all(
    TRANG_THAI_CHO_DUYET.map((tt) =>
      api.callDeXuat('de_xuat_danh_sach', { trang_thai: tt, limit: GIOI_HAN_CHO_DUYET })
    )
  )
  const biCat = ketQua.some((r) => (r || []).length >= GIOI_HAN_CHO_DUYET)
  const rows = ketQua.flat().sort((a, b) =>
    (b.thoi_diem_gui || '').localeCompare(a.thoi_diem_gui || '')
  )
  return { rows, biCat }
}

// Nạp lại con số cho badge nav và ghi thẳng vào store. Dùng ở shell lúc
// mount VÀ sau mỗi lần duyệt/từ chối thành công — badge nói dối một con số
// cũ là cách nhanh nhất để quản lý tin rằng còn phiếu (hoặc hết phiếu) sai
// sự thật.
export async function capNhatChoDuyetCount(store) {
  if (!store.me?.la_quan_ly) return
  const { rows, biCat } = await napHangChoDuyet()
  store.setChoDuyetCount(rows.length, biCat)
}
