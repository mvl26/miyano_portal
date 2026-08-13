"""US-E6.3/E6.4 — Yêu cầu hàng hoá (QT11). Xem
docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md và
BA §4.11 (BR-Y1…Y5, NL-11.x).

Doctype này KHÔNG dùng cơ chế Workflow của Frappe (trường `trang_thai` là một
Select thường, không phải `workflow_state`) — cố ý, vì BR-Y1 có một cạnh hai
chiều (`Cần thêm thông tin ⇄ Đang tìm nguồn`) và vài chốt chặn theo nội dung
(BR-Y2: bắt buộc lý do khi đóng "Không đáp ứng được") mà module Workflow
không biểu diễn gọn hơn một bảng chuyển trạng thái viết tay. Vì không dùng
Workflow, bẫy "gán workflow_state trước insert() ném WorkflowPermissionError"
của các epic trước KHÔNG áp dụng ở đây — không có Workflow document nào gắn
với "Portal Item Request" để framework so khớp trạng thái đầu.

Không DocPerm cho role `Customer` (xem JSON) — cổng chỉ vào qua
`api/portal.py::portal_yeu_cau_*`, suy khách từ phiên. `on_trash` chặn xoá
vô điều kiện (BR-Y4: "Yêu cầu không bị xoá").
"""

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

TRANG_THAI_KET_THUC = {
	"Đã chuyển thành đơn", "Không đáp ứng được", "Khách huỷ", "Hết hạn",
}

# BR-Y1 — cạnh cho phép của máy trạng thái. Chìa khoá là trạng thái NGUỒN;
# giá trị là tập trạng thái ĐÍCH được phép đi tới từ đó. Trạng thái kết thúc
# (TRANG_THAI_KET_THUC) cố ý KHÔNG xuất hiện làm chìa khoá — không có cạnh đi
# ra từ chúng, xem _kiem_chuyen_trang_thai().
CHUYEN_TRANG_THAI_HOP_LE = {
	"Mới": {"Đang tìm nguồn", "Đã có hàng", "Không đáp ứng được", "Khách huỷ"},
	"Đang tìm nguồn": {
		"Cần thêm thông tin", "Đã báo giá", "Đã có hàng",
		"Không đáp ứng được", "Khách huỷ",
	},
	"Cần thêm thông tin": {"Đang tìm nguồn", "Khách huỷ"},
	"Đã báo giá": {"Đã chuyển thành đơn", "Hết hạn", "Khách huỷ"},
	"Đã có hàng": {"Đã chuyển thành đơn", "Khách huỷ"},
}

DO_DAI_TOI_DA = {
	"ten_hang": 200,
	"quy_cach": 100,
	"hang_xuat_xu": 200,
	"ghi_chu": 1000,
}


class PortalItemRequest(Document):
	def validate(self):
		self._trim_va_kiem_do_dai()
		self._kiem_so_luong()
		self._kiem_tan_suat()
		self._kiem_ngay_can()
		self._kiem_chuyen_trang_thai()
		self._kiem_ly_do_khong_dap_ung()

	def _trim_va_kiem_do_dai(self):
		self.ten_hang = (self.ten_hang or "").strip() or None
		self.dvt = (self.dvt or "").strip() or None
		if not self.ten_hang:
			frappe.throw("Thiếu Tên hàng hoá.", frappe.ValidationError)
		if not self.dvt:
			frappe.throw("Thiếu ĐVT.", frappe.ValidationError)
		if not self.loai:
			frappe.throw("Thiếu Loại yêu cầu.", frappe.ValidationError)
		for fieldname, gioi_han in DO_DAI_TOI_DA.items():
			gia_tri = (self.get(fieldname) or "").strip()
			self.set(fieldname, gia_tri or None)
			if gia_tri and len(gia_tri) > gioi_han:
				label = self.meta.get_label(fieldname)
				frappe.throw(
					f"{label} không được quá {gioi_han} ký tự.",
					frappe.ValidationError,
				)

	def _kiem_so_luong(self):
		if not self.so_luong_du_kien or self.so_luong_du_kien <= 0:
			frappe.throw(
				"Số lượng dự kiến phải lớn hơn 0.", frappe.ValidationError
			)

	def _kiem_tan_suat(self):
		if self.tan_suat == "Định kỳ":
			if not self.chu_ky_thang or self.chu_ky_thang < 1:
				frappe.throw(
					"Yêu cầu định kỳ phải khai Chu kỳ (tháng) ≥ 1.",
					frappe.ValidationError,
				)
		else:
			self.chu_ky_thang = None

	def _kiem_ngay_can(self):
		if self.ngay_can and getdate(self.ngay_can) < getdate(nowdate()):
			frappe.throw(
				"Ngày cần hàng không được ở trong quá khứ.",
				frappe.ValidationError,
			)

	def _kiem_chuyen_trang_thai(self):
		"""BR-Y1. Chỉ kiểm khi `trang_thai` thực sự đổi so với bản ghi trước
		đó — cho phép save() không đổi trạng thái (sửa các trường khác) ở bất
		kỳ trạng thái nào, kể cả trạng thái kết thúc (BR-Y4 chỉ cấm XOÁ, không
		cấm nhân viên sửa ghi chú sau khi đóng)."""
		if self.is_new():
			if self.trang_thai and self.trang_thai != "Mới":
				frappe.throw(
					"Yêu cầu mới phải bắt đầu ở trạng thái Mới.",
					frappe.ValidationError,
				)
			self.trang_thai = "Mới"
			return

		before = self.get_doc_before_save()
		if not before or before.trang_thai == self.trang_thai:
			return

		if before.trang_thai in TRANG_THAI_KET_THUC:
			frappe.throw(
				f"Yêu cầu đã kết thúc ở trạng thái \"{before.trang_thai}\", "
				"không chuyển trạng thái được nữa.",
				frappe.ValidationError,
			)
		cho_phep = CHUYEN_TRANG_THAI_HOP_LE.get(before.trang_thai, set())
		if self.trang_thai not in cho_phep:
			frappe.throw(
				f"Không thể chuyển từ \"{before.trang_thai}\" sang "
				f"\"{self.trang_thai}\".",
				frappe.ValidationError,
			)

	def _kiem_ly_do_khong_dap_ung(self):
		"""BR-Y2."""
		if self.trang_thai == "Không đáp ứng được" and not (
			self.ly_do_khong_dap_ung or ""
		).strip():
			frappe.throw(
				"Chuyển sang \"Không đáp ứng được\" phải kèm lý do.",
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(
			"Không được xoá yêu cầu hàng hoá — mọi trạng thái, kể cả trạng "
			"thái kết thúc, đều phải lưu lại (BR-Y4).",
			frappe.ValidationError,
		)
