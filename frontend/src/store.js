import { reactive } from 'vue'

// Store phản ứng tối giản (không cần Pinia) cho phiên đăng nhập + vài con số
// dùng chung ở tầng shell (badge nav).
//
// Task 10 (gộp "Đặt hàng" và "Lập phiếu", 21/08/2026) — GIỎ HÀNG TOÀN CỤC ĐÃ
// BỎ. Trước đây store giữ hai ngăn giỏ (`cart` theo HĐNT, `cartLe` mua lẻ) +
// mảng `cartDatNgoai`, phục vụ hai màn `Catalog.vue`/`Cart.vue` nay đã nghỉ.
// Màn Đặt hàng gộp giữ giỏ TRONG chính nó, và giỏ đó bền vững hơn hẳn: nó là
// một phiếu `Portal De Xuat Mua` ở trạng thái Nháp trên server, sống qua F5,
// qua đổi máy, và mang sẵn tầng giá/hợp đồng do server suy — khác một object
// trong bộ nhớ tab trình duyệt, mất trắng khi tải lại trang.
//
// Cái GIỮ LẠI từ khối cũ: `requestId` (BR-O12, chống tạo đơn trùng) — đường
// đặt thẳng của quản lý (`portal_order_place`) vẫn cần đúng cơ chế đó.
export const store = reactive({
  me: null, // { customer, customer_name, tax_id, outstanding, addresses }
  // Brief 2026-08-15 (trang thông báo) — số thông báo chưa đọc cho badge
  // trên nav. Nạp ở `App.vue` (mount, mọi trang) và ở chính trang Thông báo
  // (nguồn dữ liệu chính xác nhất); `ThongBao.vue` giảm số này TẠI CHỖ khi
  // khách bấm mở một thông báo, khỏi phải gọi lại danh sách chỉ để đổi một
  // con số.
  chuaDocThongBao: 0,
  setChuaDocThongBao(n) {
    this.chuaDocThongBao = n
  },
  // Badge số phiếu đang chờ quản lý duyệt (gộp "Chờ duyệt" + "Chờ duyệt
  // sửa") trên mục menu "Danh sách đơn hàng" — màn `/duyet` riêng đã nghỉ
  // 03/09/2026. Nạp ở App.vue (mọi trang, chỉ khi `la_quan_ly`) — cùng
  // khuôn `chuaDocThongBao` ở trên.
  choDuyetCount: 0,
  // Việc (e) — `de_xuat_danh_sach` cắt ở `limit` và KHÔNG trả tổng số. Khi
  // số dòng chạm trần, con số badge là SÀN chứ không phải sự thật; cờ này
  // cho badge hiện "200+" thay vì "200". Danh sách thật (`portal_yeu_cau_
  // cua_toi`) đếm `tong` chính xác trong SQL, không thừa hưởng trần này.
  choDuyetBiCat: false,
  setChoDuyetCount(n, biCat = false) {
    this.choDuyetCount = n
    this.choDuyetBiCat = !!biCat
  },
  requestId: null,

  setMe(me) {
    this.me = me
  },

  // --- Chống tạo đơn trùng (BR-O12) ---
  // Mã sinh MỘT LẦN khi bắt đầu một lần đặt hàng và giữ nguyên cho tới khi
  // đơn tạo xong — đó CHÍNH LÀ cơ chế: bấm lại phải gửi CÙNG một mã thì
  // server mới nhận ra và trả về đơn cũ thay vì tạo đơn thứ hai.
  batDauDatHang() {
    // Sinh một lần. Sinh lại mỗi lần bấm sẽ vô hiệu hoá toàn bộ cơ chế.
    if (!this.requestId) {
      this.requestId =
        crypto.randomUUID?.() ||
        `${Date.now()}-${Math.random().toString(16).slice(2)}`
    }
  },
  ketThucDatHang() {
    // Chỉ xoá khi đơn đã tạo XONG. Bỏ dở giữa chừng thì GIỮ mã lại — khách
    // quay lại bấm tiếp vẫn phải là cùng MỘT lần đặt hàng.
    this.requestId = null
  },
})

export default store
