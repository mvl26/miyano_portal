"""Mọi endpoint whitelist phải KHAI BÁO lập trường về phạm vi khoa phòng.

Đây không phải test một hành vi — nó là một cái chốt. Cổng có 27 endpoint ở
`api/portal.py` và 38 ở `api/kho.py`; nếu mỗi cái tự viết điều kiện lọc thì
việc MỘT cái quên lọc là chắc chắn xảy ra. App đã dính đúng kiểu đó hai lần
trong tuần 17–18/08 (phiếu trả hàng lọt vào danh sách đợt giao; phiếu giao
nháp lọt ra cổng khách).

Thêm endpoint mới mà không thêm tên nó vào một trong hai tập dưới đây thì
test này ĐỎ. Đó là toàn bộ mục đích của nó.
"""

import inspect

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.api import portal as portal_api

# Endpoint ĐÃ đi qua `pham_vi_don()` hoặc `dam_bao_xem_duoc()`.
DA_AP_PHAM_VI: set[str] = {
	"portal_order_history", "portal_order_track", "portal_dashboard_kpi",
	"portal_deliveries", "portal_invoices", "portal_reorder",
	"portal_order_accept", "portal_order_sua_so_luong", "portal_order_huy",
	"portal_request_cancel", "portal_bao_gia_pdf", "portal_document_download",
	"portal_kiem_hang_get", "portal_kiem_hang_luu", "portal_kiem_hang_gui",
	"portal_einvoice_download", "portal_einvoice_nhap",
	"portal_einvoice_nhap_pdf", "portal_einvoice_ho_tro",
	"portal_thong_bao_list", "portal_thong_bao_doc",
}

# Endpoint CỐ Ý không lọc theo khoa — mỗi cái kèm lý do bằng chữ. Sửa tập
# này là một quyết định phân quyền, không phải một thao tác dọn dẹp.
MIEN_PHAM_VI: dict[str, str] = {
	"portal_me": "hồ sơ của chính người đăng nhập, không có dữ liệu đơn hàng",
	"portal_contracts": "hợp đồng khung ký ở cấp bệnh viện, không thuộc khoa nào",
	"portal_catalog": "danh mục hàng theo hợp đồng — cấp bệnh viện",
	"portal_catalog_ban_le": "danh mục hàng bán lẻ — cấp bệnh viện",
	"portal_order_place": "đường GHI; phạm vi do dat_hang.tao_sales_order chốt",
	"portal_provision": "chỉ nhân viên Miyano gọi, không phải endpoint của khách",
}


class TestMoiEndpointKhaiBaoPhamVi(FrappeTestCase):
	def _endpoints(self, module) -> set[str]:
		# `frappe.whitelist()` trong bản Frappe của site này KHÔNG gắn thuộc
		# tính `.whitelisted` lên hàm (khác một số bản Frappe khác) — nó chỉ
		# ghi hàm gốc vào danh sách toàn cục `frappe.whitelisted`. Soát bằng
		# `fn in frappe.whitelisted` thay vì `getattr(fn, "whitelisted", ...)`
		# để đo đúng cơ chế THẬT của bản đang chạy, không phải cơ chế giả định.
		return {
			ten for ten, fn in inspect.getmembers(module, inspect.isfunction)
			if fn in frappe.whitelisted and fn.__module__ == module.__name__
		}

	def test_moi_endpoint_portal_deu_da_khai_bao(self):
		thuc_te = self._endpoints(portal_api)
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
		thuc_te = self._endpoints(portal_api)
		thua = (DA_AP_PHAM_VI | set(MIEN_PHAM_VI)) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")

	def test_module_kho_chua_ap_pham_vi_la_no_biet_dieu_do(self):
		"""Bước 8 của đề án mới cách ly module kho. Cho tới lúc đó, test này
		giữ CON SỐ để việc thêm endpoint kho mới không lặng lẽ trôi qua."""
		self.assertEqual(
			len(self._endpoints(kho_api)), 38,
			"Số endpoint api/kho.py đã đổi. Bước 8 phân loại 38 cái này thành "
			"13 phải lọc / 8 phải thu hẹp / 17 chặn theo vai trò — xem spec "
			"§7.1c. Cập nhật cả hai chỗ cùng lúc.",
		)
