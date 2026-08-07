import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import Catalog from './views/Catalog.vue'
import Cart from './views/Cart.vue'
import Orders from './views/Orders.vue'
import OrderDetail from './views/OrderDetail.vue'
import Invoices from './views/Invoices.vue'
import Kho from './views/Kho.vue'
import ImportTonDau from './views/ImportTonDau.vue'
import Profile from './views/Profile.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: Dashboard, meta: { title: 'Tổng quan' } },
  { path: '/catalog', name: 'catalog', component: Catalog, meta: { title: 'Đặt hàng' } },
  { path: '/cart', name: 'cart', component: Cart, meta: { title: 'Giỏ hàng' } },
  { path: '/orders', name: 'orders', component: Orders, meta: { title: 'Đơn hàng của tôi' } },
  { path: '/orders/:name', name: 'order-detail', component: OrderDetail, meta: { title: 'Chi tiết đơn' } },
  { path: '/invoices', name: 'invoices', component: Invoices, meta: { title: 'Hoá đơn & công nợ' } },
  { path: '/kho', name: 'kho', component: Kho, meta: { title: 'Kho của tôi' } },
  { path: '/kho/import', name: 'kho-import', component: ImportTonDau, meta: { title: 'Nhập tồn đầu kỳ' } },
  { path: '/profile', name: 'profile', component: Profile, meta: { title: 'Hồ sơ đơn vị' } },
]

// base '/portal' → URL dạng /portal/dashboard, /portal/orders, ...
const router = createRouter({
  history: createWebHistory('/portal'),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
