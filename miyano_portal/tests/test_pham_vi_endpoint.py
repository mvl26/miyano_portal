"""Mọi endpoint whitelist phải KHAI BÁO lập trường về phạm vi khoa phòng.

Đây không phải test một hành vi — nó là một cái chốt. Cổng có 27 endpoint ở
`api/portal.py` và 42 ở `api/kho.py`; nếu mỗi cái tự viết điều kiện lọc thì
việc MỘT cái quên lọc là chắc chắn xảy ra. App đã dính đúng kiểu đó hai lần
trong tuần 17–18/08 (phiếu trả hàng lọt vào danh sách đợt giao; phiếu giao
nháp lọt ra cổng khách).

Thêm endpoint mới mà không thêm tên nó vào một trong các tập bên dưới
(theo module) thì test này ĐỎ. Đó là toàn bộ mục đích của nó.

VÒNG SỬA 1 (review độc lập, I3) — bản trước CHỈ soi `api/portal.py`. Ba
module khác cũng có `@frappe.whitelist()` mà một tài khoản cổng gọi tới
được (trực tiếp hoặc qua đường Frappe generic) nằm ngoài tầm nhìn cũ:
`search_guard.py` (7 hàm — CHÍNH đường `frappe.client.get_list`/`get_value`
mà C2 vừa vá), `portal_kiem_hang.py` (4 hàm — vai NHÂN VIÊN, chốt role),
`portal_hen_giao.py` (1 hàm — cùng khuôn). Mở rộng phép liệt kê sang cả ba.
"""

import inspect

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import portal_hen_giao, portal_kiem_hang, search_guard
from miyano_portal.api import de_xuat as de_xuat_api
from miyano_portal.api import kho as kho_api
from miyano_portal.api import nhan_su as nhan_su_api
from miyano_portal.api import portal as portal_api

# Endpoint ĐÃ đi qua `pham_vi_don()` hoặc `dam_bao_xem_duoc()`.
#
# Task 5 (19/08/2026) thêm 6 endpoint của `api/de_xuat.py` vào ĐÂY — module
# mới không tự động bị `_endpoints()` soi tới, phải khai báo thủ công. Cả
# sáu đều đi qua `get_portal_member()` (trục khách hàng) + `pham_vi_don()`
# (trục khoa) trong chính `api/de_xuat.py::_phieu_cua_toi()`/
# `de_xuat_tao_nhap()`/`de_xuat_danh_sach()` — không cái nào miễn.
DA_AP_PHAM_VI: set[str] = {
	# Task 11 (21/08/2026, QĐ-G11) — danh sách hợp nhất phiếu + đơn. SQL
	# THÔ (union), nên `permission_query_conditions` KHÔNG tự áp: nó tự hỏi
	# `get_portal_member()` (trục khách) + `pham_vi_don()` (trục khoa) cho
	# CẢ HAI nhánh, cộng lưới `_cot_khoa_phong_ton_tai()` fail-closed cho
	# nhánh đơn — xem docstring endpoint.
	"portal_yeu_cau_cua_toi",
	"portal_order_history", "portal_order_track", "portal_dashboard_kpi",
	"portal_deliveries", "portal_invoices", "portal_reorder",
	"portal_order_accept", "portal_order_sua_so_luong", "portal_order_huy",
	"portal_request_cancel", "portal_bao_gia_pdf", "portal_document_download",
	"portal_kiem_hang_get", "portal_kiem_hang_luu", "portal_kiem_hang_gui",
	"portal_einvoice_download", "portal_einvoice_nhap",
	# CR-03 (05/09/2026) — ảnh cho dòng "hàng chưa có trong hệ thống". CẢ BA
	# đi qua `_phieu_cua_toi()`, đúng chốt hai trục mà mọi endpoint phiếu
	# khác dùng; không endpoint nào tự chế bộ lọc. `xem_anh` còn kiểm thêm
	# `File.attached_to_name == phiếu` mỗi lần xem: `file_url` KHÔNG phải
	# khoá bí mật (Frappe gộp tệp trùng nội dung theo hash), nên chỉ kiểm
	# quyền trên phiếu là chưa đủ.
	"portal_dat_ngoai_tai_anh", "portal_dat_ngoai_xoa_anh",
	"portal_dat_ngoai_xem_anh",
	"portal_einvoice_nhap_pdf", "portal_einvoice_ho_tro",
	"portal_thong_bao_list", "portal_thong_bao_doc",
	"de_xuat_tao_nhap", "de_xuat_luu_nhap", "de_xuat_xoa_nhap",
	"de_xuat_gui_duyet", "de_xuat_danh_sach", "de_xuat_chi_tiet",
	# Task 6 (19/08/2026) — cả ba đều mở đầu bằng `_phieu_cua_toi(...,
	# cho_quan_ly=True)` (trục khách hàng + khoa) CỘNG một chốt `la_quan_ly()`
	# riêng (chỉ quản lý được gọi) — đúng khuôn đã lọc, không miễn.
	"de_xuat_duyet_phieu", "de_xuat_tu_choi", "de_xuat_huy",
	# Task 9 (19/08/2026, §12 Q4) — vòng sửa số lượng SAU khi đã duyệt.
	# `de_xuat_xin_sua` mở đầu bằng `_phieu_cua_toi(..., cho_quan_ly=True)`
	# (trục khách hàng + khoa). `de_xuat_duyet_sua`/`de_xuat_tu_choi_sua`
	# cùng khuôn Task 6: `la_quan_ly()` riêng CỘNG `_phieu_cua_toi(...,
	# cho_quan_ly=True)` — không cái nào miễn phạm vi.
	"de_xuat_xin_sua", "de_xuat_duyet_sua", "de_xuat_tu_choi_sua",
	# 03/09/2026 — thu hồi phiếu Chờ duyệt về Nháp để sửa. Mở đầu bằng
	# `_phieu_cua_toi(ten)` (trục khách hàng + khoa, VÀ vòng kiểm chủ sở
	# hữu mặc định) CỘNG một chốt owner-only riêng — chặt hơn cả ba nhóm
	# trên, không cái nào miễn phạm vi.
	"de_xuat_thu_hoi",
	# Task 5 (nhật ký thao tác, 03/09/2026) — đọc sổ nhật ký của một yêu
	# cầu. Nhánh `de_xuat` gọi `_phieu_cua_toi(de_xuat, cho_quan_ly=True)`
	# (trục khách hàng + khoa, KHÔNG kiểm chủ sở hữu — đồng nghiệp cùng
	# khoa cũng đọc được). Nhánh `order` gọi `dam_bao_xem_duoc("Sales
	# Order", order)` (trục khoa) CỘNG `so.check_permission("read")` (trục
	# khách hàng qua hook `sales_has_permission`) — đúng khuôn
	# `portal_order_track` đã dùng. Không nhánh nào tự chế bộ lọc riêng.
	"portal_nhat_ky_yeu_cau",
}

# Endpoint CỐ Ý không lọc theo khoa — mỗi cái kèm lý do bằng chữ. Sửa tập
# này là một quyết định phân quyền, không phải một thao tác dọn dẹp.
MIEN_PHAM_VI: dict[str, str] = {
	"portal_me": (
		"outstanding là công nợ GL cấp KHÁCH HÀNG/công ty (Vòng sửa 1, I1: "
		"lý do cũ 'không có dữ liệu đơn hàng' SAI — _get_outstanding() trả "
		"tổng công nợ GL của CẢ bệnh viện). Không truy được về khoa qua GL "
		"Entry (thanh toán/bút toán không mang custom_khoa_phong), và nhất "
		"quán với các field khác CÙNG endpoint (customer_name/tax_id/"
		"addresses) — đều cấp bệnh viện. KHÁC hoa_don_chua_thanh_toan trên "
		"portal_dashboard_kpi: đó là ĐẾM HOÁ ĐƠN cụ thể, quy được về khoa "
		"qua Sales Invoice Item.sales_order, đứng cạnh hai con số khác đã "
		"lọc khoa trên cùng màn — để nó unscoped sẽ phá ngữ cảnh 'đây là "
		"số liệu khoa tôi' của khối KPI đó. "
		"Review Task 5 — bốn khoá MỚI `vai_tro`/`khoa_phong`/`la_quan_ly`/"
		"`user` (Task 1) KHÔNG nằm trong lý do miễn ở trên: chúng KHÔNG "
		"phải dữ liệu cấp bệnh viện, mà là HỒ SƠ CỦA CHÍNH PHIÊN gọi — "
		"`get_portal_member()` đã tự scope người gọi trước khi các khoá "
		"này được đọc ra, nên không có gì để 'lọc theo khoa' thêm nữa. "
		"Đừng đọc bốn khoá này là bằng chứng 'cấp bệnh viện' như phần còn "
		"lại của endpoint — đó là hai lý do miễn khác nhau đứng cạnh nhau."
	),
	"portal_contracts": "hợp đồng khung ký ở cấp bệnh viện, không thuộc khoa nào",
	"portal_catalog": "danh mục hàng theo hợp đồng — cấp bệnh viện",
	"portal_catalog_ban_le": "danh mục hàng bán lẻ — cấp bệnh viện",
	"portal_catalog_gop": (
		"Task 3 (21/08/2026) — cùng khuôn portal_catalog/portal_catalog_"
		"ban_le: danh mục hàng tìm kiếm gộp là dữ liệu CẤP BỆNH VIỆN (Item/"
		"Blanket Order không có trục khoa phòng), không phải dữ liệu của "
		"một PHIẾU/ĐƠN cụ thể. `get_portal_customer()` đã tự scope theo "
		"khách hàng (trục bệnh viện) — không có khoa nào để lọc thêm."
	),
	"portal_order_place": (
		"đường GHI; phạm vi ĐỌC (pham_vi_don/dam_bao_xem_duoc) không áp lên "
		"đường ghi này — Task 7 (§5.5): khoa đóng dấu lên đơn đi qua "
		"portal_context.khoa_phong_cho_don(), phép kiểm khoa ↔ NGƯỜI GỌI "
		"(khác dat_hang.tao_sales_order, chỉ kiểm khoa ↔ KHÁCH HÀNG). Nhân "
		"viên khoa gọi thẳng endpoint này bị TỪ CHỐI hẳn (phải đi "
		"de_xuat_gui_duyet → quản lý duyệt); quản lý ĐƯỢC chọn khoa qua "
		"tham số khoa_phong nhưng khoa_phong_cho_don() đã tự kiểm khoa đó "
		"thuộc đúng bệnh viện của họ và đang active — không phải một lỗ hở "
		"phạm vi bị bỏ sót."
	),
	"portal_provision": "chỉ nhân viên Miyano gọi, không phải endpoint của khách",
}

# api/kho.py — Bước 8 (spec §7.1c) CHƯA phân loại từng cái trong số 38
# endpoint có TỪ TRƯỚC nhánh `feat/thiet-bi-vat-tu` (`KHO_CON_SO_CU` bên
# dưới) — chốt cho phần đó tạm thời chỉ còn là một con số, xem test
# `test_module_kho_chua_ap_pham_vi_la_no_biet_dieu_do`.
#
# Bốn endpoint MỚI của module thiết bị (Task 7, commit `de582d1`) thì ĐÃ
# được xem xét và khai báo ở đây — tập này đóng vai trò của `DA_AP_PHAM_VI`
# (module portal.py) nhưng riêng cho `api/kho.py`, và sẽ là nơi khai báo cho
# mọi endpoint kho mới về sau, không chỉ bốn cái của Task 7. `b48f54a` (Task
# 8) chỉ SỬA `kho_phieu_xuat_save` (endpoint có sẵn, đã nằm trong
# `KHO_CON_SO_CU`) chứ không thêm endpoint mới, nên không có gì phải khai
# thêm ở đây cho commit đó.
#
# Giá trị mỗi mục KHÔNG đồng nghĩa "đã lọc theo khoa" — ba cái đầu đi qua
# `pham_vi_don()` (có trục khoa thật, xem chi tiết từng dòng), còn
# `kho_vat_tu_gan_thiet_bi` KHÔNG có trục khoa để lọc (đọc lý do của nó:
# `Customer Warehouse Item` không có field khoa phòng) — nó chỉ khai lập
# trường TENANT (kho + khách hàng), không phải KHOA. Ghi rõ sự khác biệt
# này trong từng chuỗi lý do, đừng để cả bốn trông như cùng một khuôn.
KHO_DA_AP_PHAM_VI: dict[str, str] = {
	# Cả bốn đều suy `customer` từ phiên qua `get_portal_customer()` — không
	# nhận từ client. `_thiet_bi_action` (dùng chung `_action()`) CHỈ dịch lỗi
	# sang tiếng Việt, không tự lọc gì — phạm vi khoa nằm ở logic bên trong
	# từng hàm, không phải ở decorator.
	"kho_thiet_bi_list": (
		"lọc trục khoa qua thiet_bi_mod.list_rows() -> "
		"portal_context.pham_vi_don(): Nhân viên khoa chỉ thấy máy của khoa "
		"mình CỘNG máy dùng chung (pham_vi_don() trả khoa cụ thể), Quản lý "
		"thấy xuyên khoa (pham_vi_don() trả {} = không giới hạn). Tham số "
		"`khoa_phong` do client gửi (endpoint chỉ ép str(), KHÔNG kiểm sở "
		"hữu) là lọc THÊM AND vào danh sách đã bị pham_vi_don() thu hẹp "
		"trước đó trong list_rows() — không phải một filter độc lập chạy "
		"lại từ đầu, nên không thể WIDEN ra ngoài khoa của phiên."
	),
	"kho_thiet_bi_save": (
		"khoa_phong ÉP theo phiên qua _khoa_ep_theo_phien()/pham_vi_don() "
		"trong thiet_bi_mod.save() — fail-closed bằng PermissionError khi "
		"Nhân viên khoa thiếu khoa_phong trên hồ sơ. `name`/`khoa_phong` do "
		"client gửi còn bị guard sở hữu qua _thiet_bi_cua_khach()/"
		"_khoa_cua_khach() TRƯỚC khi chạm doc (Vòng sửa 1, Important #1)."
	),
	"kho_thiet_bi_tao_nhanh": (
		"cùng cơ chế kho_thiet_bi_save: thiet_bi_mod.tao_nhanh() luôn TẠO "
		"MỚI nên khoa_phong luôn tính qua _khoa_ep_theo_phien()/"
		"pham_vi_don() (cùng fail-closed); không có `name` client gửi nên "
		"không cần guard sở hữu thêm ở tầng endpoint."
	),
	# Task 12b (28/08/2026) — endpoint MỚI, không phải một trong bốn của
	# Task 7. Decorator thật trên `kho_khoa_phong_list_khach` là
	# `_khoa_action`, không phải `_thiet_bi_action` (sửa Task 15 hạng mục
	# 12b) — cùng dùng chung `_action()` nên cũng CHỈ dịch lỗi sang tiếng
	# Việt, không tự lọc gì; phạm vi khoa nằm ở
	# `khoa_phong_mod.list_rows_theo_khach()` -> `pham_vi_don()`, đúng khuôn
	# `kho_thiet_bi_list` ngay trên.
	"kho_khoa_phong_list_khach": (
		"lọc trục khoa qua khoa_phong_mod.list_rows_theo_khach() -> "
		"portal_context.pham_vi_don(): Nhân viên khoa chỉ thấy khoa của "
		"chính mình (pham_vi_don() trả khoa cụ thể -> lọc filters['name']), "
		"Quản lý thấy mọi khoa của bệnh viện (pham_vi_don() trả {} = không "
		"giới hạn). `customer` suy từ phiên qua get_portal_customer(), "
		"KHÔNG qua get_portal_kho() — đây chính là lý do endpoint này tồn "
		"tại (spec §4.1: bệnh viện chưa mở kho vẫn khai được máy, nhưng "
		"kho_khoa_phong_list cũ đòi kho)."
	),
	"kho_vat_tu_gan_thiet_bi": (
		"Trục khoa: KHÔNG áp — `Customer Warehouse Item` (vật tư) không có "
		"field khoa phòng, không có trục khoa để lọc; một Nhân viên khoa A "
		"gắn được máy của khoa B CÙNG bệnh viện vào vật tư dùng chung — đó "
		"là chủ ý (danh mục vật tư là cấp KHO, không phải cấp khoa), không "
		"phải một lỗ hở bị bỏ sót. Trục khách hàng/kho (TENANT): guard CẢ "
		"HAI định danh (vat_tu qua _vat_tu_cua_kho(), thiet_bi qua "
		"_thiet_bi_cua_khach()) về đúng kho/khách của PHIÊN gọi TRƯỚC khi "
		"gọi xuống gan_vao_vat_tu() — hàm đó chỉ tự kiểm hai đầu KHỚP NHAU "
		"với nhau, không so với người gọi, nên một cặp thật+khớp nhưng "
		"thuộc bệnh viện KHÁC vẫn lọt nếu thiếu guard này."
	),
	# Task 14 (28/08/2026, vòng sửa 1 — chốt test này ĐỎ khi endpoint mới ra
	# đời mà không ai khai báo). `kho_bao_cao_thiet_bi` bọc
	# `reports.bao_cao_thiet_bi_rows()` cho màn BaoCaoThietBi.vue. Đã đọc lại
	# `reports.py` (grep `pham_vi_don` trên `miyano_portal/kho/*.py`): hàm đó
	# CHỈ được gọi trong `thiet_bi.py`/`khoa_phong.py` — `reports.py` sạch,
	# không đâu trong đó tự lọc theo khoa.
	"kho_bao_cao_thiet_bi": (
		"Trục khoa: KHÔNG áp — KHÁC `kho_vat_tu_gan_thiet_bi` ngay trên: ở "
		"đó trục khoa KHÔNG TỒN TẠI trong dữ liệu; ở ĐÂY trục khoa TỒN TẠI "
		"thật (mỗi dòng `theo_may` mang `khoa_phong` của máy) nhưng KHÔNG "
		"được lọc theo NGƯỜI GỌI — hàm không gọi `pham_vi_don()` ở đâu cả, "
		"và `reports.bao_cao_thiet_bi_rows()` mà nó bọc cũng không (đã đọc "
		"lại, không đoán — pham_vi_don() chỉ được gọi trong thiet_bi.py/"
		"khoa_phong.py, reports.py sạch). Một Nhân viên khoa A gọi endpoint "
		"này (kho suy từ get_portal_kho(), không lọc theo vai trò) THẤY ĐƯỢC "
		"dữ liệu cấp phát của khoa B cùng bệnh viện — cả năm cột ngoài (tồn "
		"đầu/nhập/cấp phát/xuất khác/tồn cuối, vốn là số CẤP KHO, không tách "
		"được theo khoa) lẫn bảng con theo_may của MỌI khoa. Tham số "
		"khoa_phong/thiet_bi do client gửi CHỈ thu hẹp HIỂN THỊ trên "
		"theo_may của một request (kiểm sở hữu qua _khoa_cua_kho()/"
		"_thiet_bi_cua_khach() nên không nới ra ngoài bệnh viện của phiên) — "
		"KHÔNG phải một biên an toàn: bỏ tham số đó đi là thấy lại hết. "
		"CỐ Ý KHÔNG thêm pham_vi_don() ở vòng sửa này (đã hỏi cố vấn độc lập "
		"trước khi quyết định) vì ba lý do: (1) kho_bao_cao_cap_phat — CHÍNH "
		"báo cáo 'cấp phát theo khoa', vẫn nằm trong KHO_CON_SO_CU — cũng "
		"không lọc người gọi; chỉ khoá riêng màn MỚI này tạo ra một nghịch "
		"lý MỚI (cùng một câu hỏi 'khoa B tiêu gì', hai màn cho hai câu trả "
		"lời khác nhau) thay vì sửa nghịch lý cũ. (2) pham_vi_don() trả một "
		"filter hình dạng Sales Order ({'custom_khoa_phong': ...}) — "
		"Customer Stock Ledger Entry/Customer Equipment không có field đó, "
		"gắn vào đây là bịa ngữ nghĩa map mới giữa hai mô hình dữ liệu không "
		"tương thích, không phải nối một cơ chế sẵn có. (3) Năm cột ngoài "
		"KHÔNG có trục khoa để mà thu hẹp (tồn kho/nhập kho là số CẤP KHO) — "
		"một dòng 'đã lọc một nửa' (bảng con thu hẹp, cột ngoài thì không) "
		"là một lời NÓI DỐI MỚI, không phải một bản vá. ĐÂY LÀ HIỆN TRẠNG "
		"CHUNG của cả họ kho_bao_cao_* (nxt/the_kho/canh_bao/dot/cap_phat/"
		"cap_phat_thang — sáu endpoint, tất cả còn nằm trong KHO_CON_SO_CU, "
		"không cái nào gọi pham_vi_don()) — kho_bao_cao_thiet_bi kế thừa "
		"ĐÚNG quy ước hiện có của module báo cáo kho, không phải một lỗ hổng "
		"MỚI phát sinh riêng ở Task 14. Đây là một CÂU HỎI SẢN PHẨM CHƯA "
		"CHỐT (có nên hạn chế Nhân viên khoa khỏi mọi báo cáo kho không?), "
		"không phải một quyết định bảo mật đã được duyệt — cờ cho Bước 8 "
		"(spec §7.1c) khi phân loại cả họ kho_bao_cao_*, xem "
		"task-14-report.md mục 'Vòng sửa 1'. Trục khách hàng/kho (TENANT) "
		"CÓ áp: kho/customer suy từ phiên qua get_portal_kho()/"
		"get_portal_customer() (không nhận từ client); thiet_bi qua "
		"_thiet_bi_cua_khach(), khoa_phong qua _khoa_cua_kho() — cả hai "
		"TRƯỚC khi chạm reports.bao_cao_thiet_bi_rows()."
	)
}

# Con số ĐÓNG BĂNG (baseline nợ kỹ thuật trước Task 7/commit `de582d1`, khi
# Bước 8 — spec §7.1c, phân loại từng cái — còn chưa làm). Chỉ được PHÉP
# GIẢM khi Bước 8 phân loại bớt một endpoint cũ ra khỏi con số này (và thêm
# nó vào KHO_DA_AP_PHAM_VI). KHÔNG BAO GIỜ tăng số này để dập lửa — endpoint
# kho MỚI luôn đi vào KHO_DA_AP_PHAM_VI ở trên, không vào đây.
KHO_CON_SO_CU = 38

# search_guard.py — Vòng sửa 1 (I3). Bảy hàm này là vỏ mỏng quanh
# `frappe.client.*`/`frappe.desk.search.*`, KHÔNG tự gọi `pham_vi_don()`/
# `dam_bao_xem_duoc()` — chúng thừa hưởng phạm vi khoa qua HAI cơ chế khác
# nhau tuỳ trục:
#   * Trục DOCTYPE CON (`frappe.is_table(doctype)` đúng): NG-37/NG-37b chặn
#     Website User HOÀN TOÀN trước khi chạm doctype cha — không có khái
#     niệm khoa phòng ở doctype con, không cần lọc thêm.
#   * Trục DOCTYPE CHA (Sales Order/Delivery Note/Sales Invoice — role
#     Customer có DocPerm read trực tiếp): rơi thẳng xuống
#     `frappe.client.get_list`/`get`/`get_value` thật, TỰ ĐỘNG đi qua
#     `permission_query_conditions`/`has_permission` mà C2 (Vòng sửa 1) vừa
#     thêm vế khoa — ĐÂY chính là kênh C2 nêu tên
#     ("frappe.client.get_value", "search_guard.client_get_list").
# Test `test_client_get_list_qua_search_guard_khong_lo_don_khoa_khac` +
# `test_client_get_value_qua_search_guard_khong_doc_duoc_don_khoa_khac`
# trong `test_cach_ly_khoa_phong.py` khẳng định trực tiếp hai hàm này.
SEARCH_GUARD_AP_QUA_HOOK: dict[str, str] = {
	"search_link": "vỏ mỏng quanh search_widget (cùng hàm dưới)",
	"search_widget": "chặn ignore_user_permissions=1 (NG-37); phần còn lại đi qua permission_query_conditions đã có khoa",
	"client_get_list": "gọi frappe.client.get_list thật cho doctype cha — permission_query_conditions (sales_query/delivery_query/invoice_query) đã có vế khoa, xem C2",
	"client_get": "cùng cơ chế client_get_list, qua frappe.client.get + has_permission (sales_has_permission/generic_has_permission đã có vế khoa)",
	"client_get_value": "gọi frappe.client.get_value -> get_list nội bộ, cùng permission_query_conditions",
	"client_validate_link": "chỉ chặn trục doctype con (frappe.is_table); doctype cha đi qua exists()+has_permission, đã có vế khoa",
	"client_has_permission": "gọi thẳng frappe.client.has_permission -> frappe.has_permission -> sales_has_permission/generic_has_permission, đã có vế khoa",
}

# portal_kiem_hang.py / portal_hen_giao.py — Vòng sửa 1 (I3). Năm hàm này
# đều mở đầu bằng một chốt VAI TRÒ (`_kiem_role_duyet()`/`_kiem_role()`,
# yêu cầu Sales Manager/System Manager/Sales User) — một Website User
# (khách cổng) không bao giờ có các role đó, nên không bao giờ qua nổi
# dòng đầu hàm để đọc được dữ liệu của BẤT KỲ khoa nào, kể cả khoa của
# chính khách hàng mình. Cùng hạng miễn trừ với `portal_provision`.
STAFF_ONLY_MIEN_PHAM_VI: dict[str, str] = {
	"kiem_hang_duyet_tra": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"kiem_hang_tu_choi": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"kiem_hang_da_xu_ly": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"kiem_hang_hen_giao": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"hen_giao_lai": "chỉ System Manager/Sales Manager/Sales User gọi (_kiem_role), không phải endpoint của khách",
	# Task 15 (26/08/2026) — màn nhập nhân sự bằng Excel trong Desk của
	# Miyano. Cả ba mở đầu bằng `chan_neu_khong_phai_nhan_vien_miyano()`
	# (chính hàm `portal_provision` dùng, tách ra để chỉ còn MỘT phép so
	# role). Tham số `customer` do người NHÂN VIÊN chọn trên màn hình
	# (QĐ-G18) chứ không suy từ phiên — đó là chủ ý: đây là người cấp tài
	# khoản cho nhiều bệnh viện, không phải khách tự phục vụ. Một Website
	# User không bao giờ qua nổi dòng đầu để chạm tới `customer` nào.
	"nhan_su_import_template": "chỉ nhân viên Miyano gọi (chan_neu_khong_phai_nhan_vien_miyano), không phải endpoint của khách",
	"nhan_su_import_preview": "chỉ nhân viên Miyano gọi (chan_neu_khong_phai_nhan_vien_miyano), không phải endpoint của khách",
	"nhan_su_import_commit": "chỉ nhân viên Miyano gọi (chan_neu_khong_phai_nhan_vien_miyano), không phải endpoint của khách",
}


def _endpoints(module) -> set[str]:
	# `frappe.whitelist()` trong bản Frappe của site này KHÔNG gắn thuộc
	# tính `.whitelisted` lên hàm (khác một số bản Frappe khác) — nó chỉ
	# ghi hàm gốc vào danh sách toàn cục `frappe.whitelisted`. Soát bằng
	# `fn in frappe.whitelisted` thay vì `getattr(fn, "whitelisted", ...)`
	# để đo đúng cơ chế THẬT của bản đang chạy, không phải cơ chế giả định.
	return {
		ten for ten, fn in inspect.getmembers(module, inspect.isfunction)
		if fn in frappe.whitelisted and fn.__module__ == module.__name__
	}


class TestMoiEndpointKhaiBaoPhamVi(FrappeTestCase):
	def test_moi_endpoint_portal_deu_da_khai_bao(self):
		# Union với `de_xuat_api` (Task 5) — `api/de_xuat.py` là module MỚI,
		# `_endpoints(portal_api)` một mình không bao giờ thấy nó. Không
		# union thì test đếm ngược này vẫn xanh trong khi 6 endpoint mới
		# không ai canh (đúng bẫy brief Task 5 đã cảnh báo).
		thuc_te = _endpoints(portal_api) | _endpoints(de_xuat_api)
		da_khai = DA_AP_PHAM_VI | set(MIEN_PHAM_VI)
		chua_khai = thuc_te - da_khai
		self.assertFalse(
			chua_khai,
			"Endpoint chưa khai báo lập trường về phạm vi khoa phòng: "
			f"{sorted(chua_khai)}. Thêm vào DA_AP_PHAM_VI (đã lọc) hoặc "
			"MIEN_PHAM_VI (kèm lý do) trong test này.",
		)

	def test_khong_khai_bao_thua(self):
		"""Tên trong hai tập mà không còn là endpoint nữa → tập đã mục."""
		thuc_te = _endpoints(portal_api) | _endpoints(de_xuat_api)
		thua = (DA_AP_PHAM_VI | set(MIEN_PHAM_VI)) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")

	def test_module_kho_chua_ap_pham_vi_la_no_biet_dieu_do(self):
		"""Bước 8 (spec §7.1c) của đề án mới cách ly module kho CHƯA phân loại
		từng cái trong `KHO_CON_SO_CU` — chốt cho phần đó vẫn tạm là một con
		số, y như trước. Nhưng từ Task 7 trở đi, endpoint kho MỚI không còn
		được phép núp sau con số đó: phải khai vào `KHO_DA_AP_PHAM_VI` (kèm
		cơ chế lọc thật) thì test này mới xanh trở lại — đúng khuôn
		`DA_AP_PHAM_VI` của `api/portal.py`."""
		thuc_te = _endpoints(kho_api)
		khai_them = set(KHO_DA_AP_PHAM_VI)
		sai_ten = khai_them - thuc_te
		self.assertFalse(
			sai_ten,
			f"KHO_DA_AP_PHAM_VI có tên không khớp endpoint thật trong "
			f"api/kho.py (đổi tên/xoá mà quên sửa khai báo?): {sorted(sai_ten)}",
		)
		self.assertEqual(
			len(thuc_te), KHO_CON_SO_CU + len(khai_them),
			f"Số endpoint api/kho.py là {len(thuc_te)}, kỳ vọng "
			f"{KHO_CON_SO_CU} (cũ, chưa phân loại — Bước 8) + "
			f"{len(khai_them)} (đã khai trong KHO_DA_AP_PHAM_VI) = "
			f"{KHO_CON_SO_CU + len(khai_them)}. Nếu bạn vừa thêm endpoint kho "
			"mới: đọc code, xác định lập trường phạm vi khoa thật của nó, rồi "
			"thêm vào KHO_DA_AP_PHAM_VI kèm cơ chế lọc (không phải chỉ nâng "
			"con số cho hết đỏ).",
		)

	def test_moi_endpoint_search_guard_deu_da_khai_bao(self):
		thuc_te = _endpoints(search_guard)
		chua_khai = thuc_te - set(SEARCH_GUARD_AP_QUA_HOOK)
		self.assertFalse(
			chua_khai,
			f"Endpoint search_guard.py chưa khai báo: {sorted(chua_khai)}. "
			"Thêm vào SEARCH_GUARD_AP_QUA_HOOK kèm cơ chế bảo vệ thật.",
		)

	def test_khong_khai_bao_thua_search_guard(self):
		thuc_te = _endpoints(search_guard)
		thua = set(SEARCH_GUARD_AP_QUA_HOOK) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")

	def test_moi_endpoint_kiem_hang_va_hen_giao_deu_da_khai_bao(self):
		# Union với `nhan_su_api` (Task 15) — cùng cái bẫy mà Task 5 đã dính
		# một lần: module MỚI không tự lọt vào tầm nhìn của test đếm ngược
		# này, phải khai tên module ra thì ba endpoint mới có ai canh.
		thuc_te = _endpoints(portal_kiem_hang) | _endpoints(portal_hen_giao) | _endpoints(nhan_su_api)
		chua_khai = thuc_te - set(STAFF_ONLY_MIEN_PHAM_VI)
		self.assertFalse(
			chua_khai,
			f"Endpoint chưa khai báo: {sorted(chua_khai)}. Thêm vào "
			"STAFF_ONLY_MIEN_PHAM_VI (nếu role-gated) hoặc xử lý phạm vi "
			"khoa nếu khách cổng gọi được.",
		)

	def test_khong_khai_bao_thua_kiem_hang_va_hen_giao(self):
		thuc_te = _endpoints(portal_kiem_hang) | _endpoints(portal_hen_giao) | _endpoints(nhan_su_api)
		thua = set(STAFF_ONLY_MIEN_PHAM_VI) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")
