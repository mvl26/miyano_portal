import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import YeuCauList from './views/YeuCauList.vue'
import OrderDetail from './views/OrderDetail.vue'
import DeXuatDetail from './views/DeXuatDetail.vue'
import LapPhieu from './views/LapPhieu.vue'
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
import BaoCaoThietBi from './views/BaoCaoThietBi.vue'
import NccList from './views/NccList.vue'
import KhoaPhongList from './views/KhoaPhongList.vue'
import ThietBiList from './views/ThietBiList.vue'
import NhatKy from './views/NhatKy.vue'
import Profile from './views/Profile.vue'
import ThongBao from './views/ThongBao.vue'
import KiemHang from './views/KiemHang.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: Dashboard, meta: { title: 'Tổng quan' } },
  // Task 10 (gộp "Đặt hàng" và "Lập phiếu", 21/08/2026) — MỘT cửa đi mua đồ.
  // `:ten` tuỳ chọn: mở lại một phiếu Nháp để sửa tiếp (xem `LapPhieu.vue`).
  { path: '/dat-hang/:ten?', name: 'dat-hang', component: LapPhieu, meta: { title: 'Đặt hàng' } },
  // QĐ-G7 — ba đường CŨ CHUYỂN HƯỚNG, KHÔNG xoá. Chúng nằm trong bookmark
  // của khách và trong tài liệu đã gửi bệnh viện; trả 404 cho một đường
  // đang chạy là hồi quy, không phải dọn dẹp. `/cart` từng là ĐÍCH của
  // "Đặt lại đơn cũ" (OrderDetail.vue) — đường đó nay đi thẳng tới một
  // phiếu Nháp, xem `datLai()` ở màn đó.
  { path: '/catalog', redirect: { name: 'dat-hang' } },
  { path: '/cart', redirect: { name: 'dat-hang' } },
  // Task 11 (QĐ-G11, 21/08/2026) — MỘT danh sách, MỘT dòng đời. Nuốt hai
  // màn cũ `/orders` (Sales Order) và `/de-xuat` (phiếu đề xuất): một yêu
  // cầu nằm ở màn này khi còn là phiếu rồi NHẢY sang màn kia sau khi
  // duyệt, bắt nhân viên phải biết trước giai đoạn nội bộ mới tìm lại
  // được yêu cầu của chính mình.
  { path: '/yeu-cau', name: 'yeu-cau', component: YeuCauList, meta: { title: 'Danh sách đơn hàng' } },
  { path: '/yeu-cau/don/:name', name: 'order-detail', component: OrderDetail, meta: { title: 'Chi tiết đơn hàng' } },
  { path: '/yeu-cau/phieu/:ten', name: 'de-xuat-detail', component: DeXuatDetail, meta: { title: 'Chi tiết đơn hàng' } },
  // QĐ-G11 — bốn đường CŨ CHUYỂN HƯỚNG, KHÔNG xoá. Chúng nằm trong bookmark
  // của khách VÀ trong link của các thông báo tự động ĐÃ GỬI ĐI; trả 404
  // cho một đường đang chạy là hồi quy, không phải dọn dẹp. Hai đường có
  // tham số GIỮ NGUYÊN tham số — link trong email trỏ tới MỘT chứng từ cụ
  // thể, chuyển hướng về danh sách suông là đánh mất đúng thứ người nhận
  // đang tìm.
  { path: '/orders', redirect: { name: 'yeu-cau' } },
  {
    path: '/orders/:name',
    redirect: (to) => ({ name: 'order-detail', params: { name: to.params.name } }),
  },
  { path: '/de-xuat', redirect: { name: 'yeu-cau' } },
  // `/de-xuat/lap/:ten?` là màn Lập phiếu cũ — nay CHÍNH LÀ `/dat-hang`
  // (Task 10). Giữ nguyên tham số `:ten` khi chuyển hướng: đường này nằm
  // trong nút "Sửa nháp" của mọi phiếu đã gửi đi trước bản này. PHẢI đứng
  // TRƯỚC `/de-xuat/:ten` — nếu không, "lap" bị nuốt làm giá trị `:ten`.
  {
    path: '/de-xuat/lap/:ten?',
    redirect: (to) => ({ name: 'dat-hang', params: { ten: to.params.ten } }),
  },
  {
    path: '/de-xuat/:ten',
    redirect: (to) => ({ name: 'de-xuat-detail', params: { ten: to.params.ten } }),
  },
  // Chủ đầu tư chốt 03/09/2026 — màn duyệt riêng NGHỈ. Việc duyệt vốn đã
  // nằm ở màn CHI TIẾT đơn (`DeXuatDetail.vue` có đủ Duyệt/Từ chối/Huỷ và
  // cả ô sửa số lượng trước khi duyệt); `/duyet` chỉ là một DANH SÁCH THỨ
  // HAI của cùng bộ dữ liệu, và nó bắt quản lý học thêm một cửa để tìm
  // đúng thứ đã nằm sẵn trong "Danh sách đơn hàng".
  //
  // Đường CŨ CHUYỂN HƯỚNG, KHÔNG xoá — cùng luật QĐ-G7/QĐ-G11 ngay trên.
  // Đích mang theo `?chip=cho_duyet`: chip đó gom ĐÚNG hai trạng thái mà
  // màn cũ gộp ("Chờ duyệt" + "Chờ duyệt sửa", xem `_sql_giai_doan()` ở
  // api/portal.py), nên quản lý mở bookmark cũ vẫn rơi vào đúng hàng chờ
  // của mình chứ không phải một danh sách suông.
  {
    path: '/duyet',
    redirect: { name: 'yeu-cau', query: { chip: 'cho_duyet' } },
  },
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
  // Task 14 — báo cáo "vật tư · máy · khoa phòng" (câu hỏi trung tâm của
  // epic thiết bị/vật tư khoa phòng). Màn RIÊNG, không phải một tab của
  // BaoCaoNXT.vue (bộ lọc/bảng khác hẳn: có Máy, có bảng con theo máy).
  {
    path: '/kho/bao-cao-thiet-bi', name: 'kho-bao-cao-thiet-bi', component: BaoCaoThietBi,
    meta: { title: 'Báo cáo vật tư · máy · khoa phòng' },
  },
  { path: '/kho/ncc', name: 'kho-ncc', component: NccList, meta: { title: 'NCC của tôi' } },
  { path: '/kho/khoa-phong', name: 'kho-khoa-phong', component: KhoaPhongList, meta: { title: 'Danh mục khoa phòng' } },
  // Task 12 — màn danh mục Thiết bị (SPA đầu tiên của epic thiết bị/vật tư
  // khoa phòng). Đặt cạnh /kho/khoa-phong, cùng khuôn route/nav.
  { path: '/kho/thiet-bi', name: 'kho-thiet-bi', component: ThietBiList, meta: { title: 'Danh mục thiết bị' } },
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
