import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import Catalog from './views/Catalog.vue'
import Cart from './views/Cart.vue'
import Orders from './views/Orders.vue'
import OrderDetail from './views/OrderDetail.vue'
import DeXuatList from './views/DeXuatList.vue'
import DeXuatDetail from './views/DeXuatDetail.vue'
import LapPhieu from './views/LapPhieu.vue'
import DuyetList from './views/DuyetList.vue'
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
import NccList from './views/NccList.vue'
import KhoaPhongList from './views/KhoaPhongList.vue'
import NhatKy from './views/NhatKy.vue'
import Profile from './views/Profile.vue'
import ThongBao from './views/ThongBao.vue'
import KiemHang from './views/KiemHang.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: Dashboard, meta: { title: 'Tổng quan' } },
  { path: '/catalog', name: 'catalog', component: Catalog, meta: { title: 'Đặt hàng' } },
  { path: '/cart', name: 'cart', component: Cart, meta: { title: 'Giỏ hàng' } },
  { path: '/orders', name: 'orders', component: Orders, meta: { title: 'Đơn hàng của tôi' } },
  { path: '/orders/:name', name: 'order-detail', component: OrderDetail, meta: { title: 'Chi tiết đơn' } },
  // Man luong duyet (Task 3) — danh sách phiếu đề xuất mua.
  { path: '/de-xuat', name: 'de-xuat', component: DeXuatList, meta: { title: 'Đề xuất mua' } },
  // Man luong duyet (Task 8) — LẬP/SỬA một phiếu đề xuất mua ở trạng thái
  // Nháp. Đường dẫn `/de-xuat/lap/:ten?` (`ten` TUỲ CHỌN) — ba đoạn "lap" +
  // tham số nên KHÔNG đụng `/de-xuat/:ten` ngay dưới (khác số đoạn đường
  // dẫn, không thể trùng dù xếp hạng route tĩnh/động thế nào).
  //
  // Vòng sửa 1 (review) — trước bản này route KHÔNG có `:ten`, nghĩa là một
  // phiếu Nháp đã Lưu rồi RỜI MÀN thì KHÔNG CÒN ĐƯỜNG NÀO SỬA LẠI được nữa
  // (DeXuatDetail.vue chỉ đọc `so_luong_de_xuat`, không có ô nhập). Có
  // `:ten` thì `/de-xuat/lap/:ten` mở lại ĐÚNG phiếu đó để sửa tiếp — xem
  // `LapPhieu.vue` (nạp qua `de_xuat_chi_tiet`, từ chối nếu phiếu không còn
  // ở trạng thái Nháp). Không tham số vẫn là LẬP MỚI (tạo lười).
  { path: '/de-xuat/lap/:ten?', name: 'de-xuat-lap', component: LapPhieu, meta: { title: 'Lập phiếu đề xuất' } },
  // Man luong duyet (Task 4) — chi tiết một phiếu đề xuất mua.
  { path: '/de-xuat/:ten', name: 'de-xuat-detail', component: DeXuatDetail, meta: { title: 'Chi tiết đề xuất' } },
  // Man luong duyet (Task 5) — hàng chờ của quản lý, gộp "Chờ duyệt" +
  // "Chờ duyệt sửa". Mục nav chỉ hiện cho `me.la_quan_ly` (App.vue), nhưng
  // route KHÔNG khoá cứng theo vai trò: backend (`de_xuat_danh_sach` +
  // `pham_vi_don()`) tự scope nếu một khách khác gõ thẳng URL.
  { path: '/duyet', name: 'duyet', component: DuyetList, meta: { title: 'Duyệt' } },
  { path: '/invoices', name: 'invoices', component: Invoices, meta: { title: 'Hoá đơn & công nợ' } },
  // Kiểm hàng (E9) — CỐ Ý không nằm dưới /kho: màn này chạy cho MỌI khách,
  // kể cả khách chưa mở kho. Khoá theo tên PHIẾU GIAO (không phải tên biên
  // bản) vì đó là thứ khách có trong tay khi mở màn lần đầu, lúc chưa có
  // biên bản nào tồn tại.
  { path: '/kiem-hang/:dn', name: 'kiem-hang', component: KiemHang, meta: { title: 'Kiểm hàng' } },
  { path: '/kho', name: 'kho', component: Kho, meta: { title: 'Kho của tôi' } },
  { path: '/kho/import', name: 'kho-import', component: ImportTonDau, meta: { title: 'Nhập tồn đầu kỳ' } },
  { path: '/kho/vat-tu', name: 'kho-vat-tu', component: DanhMucVatTu, meta: { title: 'Danh mục vật tư' } },
  { path: '/kho/vat-tu/import', name: 'kho-vat-tu-import', component: ImportDanhMuc, meta: { title: 'Nhập danh mục vật tư' } },
  { path: '/kho/nhap', name: 'kho-nhap', component: PhieuNhap, meta: { title: 'Phiếu nhập kho' } },
  { path: '/kho/nhap/:name', name: 'kho-nhap-detail', component: PhieuNhapDetail, meta: { title: 'Chi tiết phiếu nhập' } },
  { path: '/kho/xuat', name: 'kho-xuat', component: PhieuXuat, meta: { title: 'Phiếu xuất kho' } },
  { path: '/kho/xuat/:name', name: 'kho-xuat-detail', component: PhieuXuatDetail, meta: { title: 'Chi tiết phiếu xuất' } },
  { path: '/kho/bao-cao', name: 'kho-bao-cao', component: BaoCaoNXT, meta: { title: 'Báo cáo kho' } },
  { path: '/kho/ncc', name: 'kho-ncc', component: NccList, meta: { title: 'NCC của tôi' } },
  { path: '/kho/khoa-phong', name: 'kho-khoa-phong', component: KhoaPhongList, meta: { title: 'Danh mục khoa phòng' } },
  { path: '/kho/nhat-ky', name: 'kho-nhat-ky', component: NhatKy, meta: { title: 'Nhật ký vật tư' } },
  { path: '/profile', name: 'profile', component: Profile, meta: { title: 'Hồ sơ đơn vị' } },
  { path: '/thong-bao', name: 'thong-bao', component: ThongBao, meta: { title: 'Thông báo' } },
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
