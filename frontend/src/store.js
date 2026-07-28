import { reactive } from 'vue'

// Store phản ứng tối giản (không cần Pinia) cho auth + giỏ hàng.
// Pass 2 sẽ dùng cart cho luồng Catalog/Cart.
export const store = reactive({
  me: null, // { customer, customer_name, tax_id, outstanding, addresses }
  cart: {}, // { [item_code]: { item_code, item_name, uom, rate, qty } }

  setMe(me) {
    this.me = me
  },

  get cartCount() {
    return Object.values(this.cart).reduce((a, l) => a + (l.qty || 0), 0)
  },

  addToCart(item, qty) {
    const c = this.cart[item.item_code]
    if (c) c.qty += qty
    else this.cart[item.item_code] = { ...item, qty }
  },

  clearCart() {
    this.cart = {}
  },
})

export default store
