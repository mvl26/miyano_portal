import { reactive } from 'vue'

// Store phản ứng tối giản (không cần Pinia) cho auth + giỏ hàng.
// Giỏ hàng: item_code → { item_code, item_name, uom, rate, vat_pct, remaining, qty }
export const store = reactive({
  me: null, // { customer, customer_name, tax_id, outstanding, addresses }
  cart: {},
  contract: null, // HĐNT đang chọn ở Catalog (dùng lại ở Cart)
  // Mã chống tạo đơn trùng (BR-O12). Sinh MỘT lần khi mở modal xác nhận và
  // giữ nguyên cho tới khi đơn được tạo xong — đó chính là cơ chế: bấm lại
  // phải gửi CÙNG một mã thì server mới nhận ra và trả về đơn cũ.
  requestId: null,

  setMe(me) {
    this.me = me
  },

  setContract(name) {
    this.contract = name
  },

  get cartCount() {
    return Object.values(this.cart).reduce((a, l) => a + (l.qty || 0), 0)
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

  // --- Chống tạo đơn trùng (BR-O12) ---
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
