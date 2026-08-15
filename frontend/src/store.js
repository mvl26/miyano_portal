import { reactive } from 'vue'

// Store phản ứng tối giản (không cần Pinia) cho auth + giỏ hàng.
//
// E6 (BR-R2) — giỏ HAI NGĂN: `cart` (Theo HĐNT, [Hiện có]) và `cartLe` (Mua
// lẻ, [MỚI]) là hai object ĐỘC LẬP, mỗi ngăn đặt thành MỘT Sales Order
// riêng (`mode: "hdnt" | "ban_le"` của `portal_order_place`). Cố ý KHÔNG gộp
// thành một cấu trúc `{hd: {}, le: {}}` lồng nhau: mọi màn hình đang chạy
// thật (Catalog.vue, Cart.vue) đã tham chiếu thẳng `store.cart`/`store.
// cartLines`/... cho ngăn HĐNT — đổi hình dạng đó là đổi API của store mà
// không có gì buộc phần C phải đổi theo, y hệt lý do `portal_order_place`
// giữ tên tham số `contract` (xem docstring của hàm đó).
// Mỗi dòng: item_code → { item_code, item_name, uom, rate, vat_pct, remaining, qty }
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
  cart: {}, // ngăn Theo HĐNT
  cartLe: {}, // ngăn Mua lẻ [MỚI]
  // Spec 2026-08-15 §3.4 — "hàng chưa có trong kho, cần đặt ngoài".
  //
  // MẢNG, không phải map theo `item_code` như hai ngăn kia: các dòng này
  // CHƯA CÓ MÃ. Hai dòng cùng tên hàng là hợp lệ (khách đặt hai quy cách
  // khác nhau mà chưa biết mã) — dùng map sẽ âm thầm nuốt mất dòng thứ hai.
  cartDatNgoai: [],
  contract: null, // HĐNT đang chọn ở Catalog (dùng lại ở Cart)
  // Mã chống tạo đơn trùng (BR-O12). Sinh MỘT lần khi mở modal xác nhận và
  // giữ nguyên cho tới khi đơn được tạo xong — đó chính là cơ chế: bấm lại
  // phải gửi CÙNG một mã thì server mới nhận ra và trả về đơn cũ.
  // Hai ngăn xác nhận RIÊNG (`30_API_Spec` §2 — "mỗi ngăn xác nhận riêng →
  // hai đơn riêng, mỗi cái một request_id riêng") nên có HAI mã độc lập —
  // dùng chung một mã sẽ khiến server coi lần xác nhận ngăn thứ hai là bấm
  // lại của ngăn thứ nhất và trả về CHÍNH đơn đầu tiên thay vì tạo đơn mới.
  requestId: null, // ngăn Theo HĐNT
  requestIdLe: null, // ngăn Mua lẻ [MỚI]

  setMe(me) {
    this.me = me
  },

  setContract(name) {
    this.contract = name
  },

  // Tổng SỐ DÒNG (không phải tổng số lượng) của CẢ HAI ngăn — đúng khuôn
  // badge tab giỏ trong prototype ("Theo HĐNT (2) / Mua lẻ (1)" → nav "3").
  // `30_API_Spec`/FormSpec F-04: "Badge giỏ trên nav = tổng dòng hai ngăn".
  get cartCount() {
    return (
      Object.keys(this.cart).length +
      Object.keys(this.cartLe).length +
      this.cartDatNgoai.length
    )
  },

  get cartLines() {
    return Object.values(this.cart)
  },

  get cartSubtotal() {
    return this.cartLines.reduce((a, l) => a + l.qty * l.rate, 0)
  },

  get cartVat() {
    return this.cartLines.reduce((a, l) => a + (l.qty * l.rate * (l.vat_pct || 0)) / 100, 0)
  },

  get cartTotal() {
    return this.cartSubtotal + this.cartVat
  },

  addToCart(item, qty) {
    const c = this.cart[item.item_code]
    if (c) c.qty += qty
    else this.cart[item.item_code] = { ...item, qty }
  },

  setQty(code, qty) {
    const c = this.cart[code]
    if (c) c.qty = Math.max(1, qty)
  },

  removeFromCart(code) {
    delete this.cart[code]
  },

  clearCart() {
    this.cart = {}
  },

  // --- Ngăn Mua lẻ [MỚI — BR-R2] — mirror nguyên vẹn các thao tác trên,
  // KHÔNG dùng chung state với ngăn HĐNT (BR-R4: không hạn mức, không
  // blanket_order; hai ngăn không được lẫn vào nhau dù chỉ một dòng). ---
  get cartLeLines() {
    return Object.values(this.cartLe)
  },

  // Spec 2026-08-15 §3.3 — ngăn Mua lẻ KHÔNG có tiền: `portal_catalog_ban_le`
  // không trả giá (mọi đơn mua lẻ đi qua báo giá của Miyano), nên không có gì
  // để cộng. Ba getter `cartLeSubtotal`/`cartLeVat`/`cartLeTotal` đã bị xoá —
  // đừng dựng lại: chúng chỉ cộng ra 0 ₫ và làm khách tưởng hàng miễn phí.
  // review Minor — `cartCount` (đếm DÒNG, không đếm tiền) tính CẢ BA phần:
  // hai ngăn giỏ (`cart`, `cartLe`) VÀ mảng đặt ngoài `cartDatNgoai` (§3.4,
  // chưa có mã nên không nằm trong `cartLe`) — không còn là "hai ngăn" kể
  // từ khi khối "hàng chưa có mã" ra đời, xem getter `cartCount` ở trên.

  addToCartLe(item, qty) {
    const c = this.cartLe[item.item_code]
    if (c) c.qty += qty
    // Dòng lẻ chỉ mang thông tin nhận dạng + số lượng. KHÔNG có `rate`.
    else this.cartLe[item.item_code] = {
      item_code: item.item_code,
      item_name: item.item_name,
      uom: item.uom,
      qty,
    }
  },

  setQtyLe(code, qty) {
    const c = this.cartLe[code]
    if (c) c.qty = Math.max(1, qty)
  },

  removeFromCartLe(code) {
    delete this.cartLe[code]
  },

  clearCartLe() {
    this.cartLe = {}
  },

  themDongDatNgoai(dong) {
    this.cartDatNgoai.push({
      ten_hang: dong?.ten_hang || '',
      dvt: dong?.dvt || '',
      so_luong: dong?.so_luong || 1,
      ghi_chu: dong?.ghi_chu || '',
    })
  },

  xoaDongDatNgoai(i) {
    this.cartDatNgoai.splice(i, 1)
  },

  // review Minor — KHÔNG xoá TOÀN BỘ `cartDatNgoai` sau khi đặt đơn: chỉ
  // đúng những dòng ĐÃ THẬT SỰ gửi đi (`daGui`, cùng khuôn `datNgoaiHopLe`
  // dùng để dựng payload) mới bị bỏ. Dòng đang gõ dở (chưa đủ tên hàng/ĐVT/
  // số lượng, `datNgoaiHopLe` đã lọc ra và KHÔNG gửi) phải được GIỮ LẠI —
  // xoá vô điều kiện là cùng loại lỗi commit `d0ab1df` đã sửa (mất phần
  // khách đang gõ không một lời báo), tái diễn qua một cửa khác.
  //
  // So sánh bằng REFERENCE: `datNgoaiHopLe` là `cartDatNgoai.filter(...)`,
  // filter trả về cùng object reference cho mỗi dòng khớp điều kiện, nên
  // `includes()` theo reference là đủ — không cần khoá định danh nào khác
  // cho các dòng vốn CHƯA CÓ MÃ (xem khai báo `cartDatNgoai`).
  xoaCacDongDaGui(daGui) {
    this.cartDatNgoai = this.cartDatNgoai.filter((d) => !daGui.includes(d))
  },

  // Dòng hợp lệ để gửi lên server — server vẫn validate lại (NL: client chỉ
  // báo lỗi sớm), nhưng không gửi dòng rỗng khách bỏ trống là phép lịch sự
  // tối thiểu với endpoint.
  get datNgoaiHopLe() {
    return this.cartDatNgoai.filter(
      (d) => d.ten_hang.trim() && d.dvt.trim() && Number(d.so_luong) > 0
    )
  },

  // --- Chống tạo đơn trùng (BR-O12) — ngăn Theo HĐNT ---
  moModalXacNhan() {
    // Sinh một lần. Sinh lại mỗi lần bấm sẽ vô hiệu hoá toàn bộ cơ chế.
    if (!this.requestId) {
      this.requestId =
        crypto.randomUUID?.() ||
        `${Date.now()}-${Math.random().toString(16).slice(2)}`
    }
  },
  ketThucDatHang() {
    // Chỉ xoá khi đơn đã tạo xong. Đóng modal giữa chừng thì GIỮ mã lại —
    // khách mở lại và bấm tiếp vẫn phải là cùng một lần đặt hàng.
    this.requestId = null
  },

  // --- Chống tạo đơn trùng — ngăn Mua lẻ [MỚI], cùng khuôn ở trên nhưng
  // mã ĐỘC LẬP (xem giải thích ở khai báo `requestIdLe`). ---
  moModalXacNhanLe() {
    if (!this.requestIdLe) {
      this.requestIdLe =
        crypto.randomUUID?.() ||
        `${Date.now()}-${Math.random().toString(16).slice(2)}`
    }
  },
  ketThucDatHangLe() {
    this.requestIdLe = null
  },

  // --- Đặt lại đơn cũ (UC-14) ---
  napGio(dongHang) {
    this.cart = {}
    dongHang.forEach((d) => {
      this.cart[d.item_code] = {
        item_code: d.item_code,
        item_name: d.item_name || d.item_code,
        uom: d.uom || '',
        rate: d.gia_hien_hanh,
        vat_pct: d.vat_pct || 0,
        remaining: d.remaining ?? null,
        qty: d.qty,
      }
    })
  },
})

export default store
