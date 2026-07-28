import { reactive } from 'vue'

// Store phản ứng tối giản (không cần Pinia) cho auth + giỏ hàng.
// Giỏ hàng: item_code → { item_code, item_name, uom, rate, vat_pct, remaining, qty }
export const store = reactive({
  me: null, // { customer, customer_name, tax_id, outstanding, addresses }
  cart: {},
  contract: null, // HĐNT đang chọn ở Catalog (dùng lại ở Cart)

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
})

export default store
