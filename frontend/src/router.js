import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import Catalog from './views/Catalog.vue'
import Cart from './views/Cart.vue'
import Orders from './views/Orders.vue'
import OrderDetail from './views/OrderDetail.vue'
import Invoices from './views/Invoices.vue'
import Kho from './views/Kho.vue'
import ImportTonDau from './views/ImportTonDau.vue'
import DanhMucVatTu from './views/DanhMucVatTu.vue'
import ImportDanhMuc from './views/ImportDanhMuc.vue'
import PhieuNhap from './views/PhieuNhap.vue'
import PhieuNhapDetail from './views/PhieuNhapDetail.vue'
import PhieuXuat from './views/PhieuXuat.vue'
import PhieuXuatDetail from './views/PhieuXuatDetail.vue'
import BaoCaoNXT from './views/BaoCaoNXT.vue'
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
  { path: '/kho/vat-tu', name: 'kho-vat-tu', component: DanhMucVatTu, meta: { title: 'Danh mục vật tư' } },
  { path: '/kho/vat-tu/import', name: 'kho-vat-tu-import', component: ImportDanhMuc, meta: { title: 'Nhập danh mục vật tư' } },
  { path: '/kho/nhap', name: 'kho-nhap', component: PhieuNhap, meta: { title: 'Phiếu nhập kho' } },
  { path: '/kho/nhap/:name', name: 'kho-nhap-detail', component: PhieuNhapDetail, meta: { title: 'Chi tiết phiếu nhập' } },
  { path: '/kho/xuat', name: 'kho-xuat', component: PhieuXuat, meta: { title: 'Phiếu xuất kho' } },
  { path: '/kho/xuat/:name', name: 'kho-xuat-detail', component: PhieuXuatDetail, meta: { title: 'Chi tiết phiếu xuất' } },
  { path: '/kho/bao-cao', name: 'kho-bao-cao', component: BaoCaoNXT, meta: { title: 'Báo cáo kho' } },
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
