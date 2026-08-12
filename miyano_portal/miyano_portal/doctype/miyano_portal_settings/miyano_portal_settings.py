import frappe
from frappe import _
from frappe.model.document import Document


class MiyanoPortalSettings(Document):
    def validate(self):
        # Số ngày/giờ âm hoặc bằng 0 không có nghĩa nghiệp vụ nào và sẽ làm
        # mọi phép so sánh kỳ trượt ở E5 ra kết quả ngược (ADU chia cho 0
        # ngày, "quá hạn sau 0 giờ" báo động ngay lập tức...). Chặn tại một
        # chỗ thay vì để từng nơi đọc phải tự phòng thủ.
        #
        # `nguong_duyet_2_tang` CỐ Ý không nằm trong danh sách: để trống là
        # một giá trị hợp lệ, nghĩa là "một tầng duyệt" (VĐ-8 chưa chốt số).
        for fieldname, nhan in (
            ("sla_xu_ly_don_gio", "SLA xử lý đơn"),
            ("hieu_luc_bao_gia_ngay", "Hiệu lực báo giá"),
            ("sla_yeu_cau_gio", "SLA yêu cầu hàng hoá"),
            ("so_ngay_adu", "Kỳ tính ADU"),
            ("so_ngay_du_lieu_toi_thieu", "Số ngày dữ liệu tối thiểu"),
            ("nguong_cham_luan_chuyen_ngay", "Ngưỡng chậm luân chuyển"),
        ):
            if (self.get(fieldname) or 0) < 1:
                frappe.throw(_("{0} phải lớn hơn 0.").format(nhan))

        if (self.nguong_duyet_2_tang or 0) < 0:
            frappe.throw(_("Ngưỡng duyệt 2 tầng không được âm."))
