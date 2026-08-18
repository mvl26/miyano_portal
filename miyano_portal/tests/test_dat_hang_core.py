"""Lõi đặt hàng tách khỏi endpoint (bước 1 của kế hoạch nền phân quyền).

Điểm của bộ test này KHÔNG phải là "đặt hàng chạy được" — chuyện đó đã có
test_e6_*/test_e2_* lo. Nó chốt đúng một tính chất mới: lõi **nhận customer
làm tham số** thay vì suy từ phiên đăng nhập, để đường duyệt đề nghị sau này
gọi được cùng một lõi khi người bấm duyệt KHÁC người đặt.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang

KHACH_BM = "Bệnh viện Bạch Mai"


class TestLoiDatHangNhanCustomerLamThamSo(FrappeTestCase):
    def setUp(self):
        # RULING R3 — `dat_hang.tao_sales_order(mode="ban_le")` đi qua
        # `dam_bao_duoc_mua_le()` (BR-R1), đòi `Customer.custom_cho_phep_mua_le`
        # phải bật. Không bật thì test đỏ vì PermissionError của BR-R1 — SAI
        # LÝ DO, che mất tính chất thật sự đang kiểm ở đây (lõi nhận customer
        # làm tham số, không đọc phiên). Trả lại giá trị cũ ở tearDown để
        # không làm lệch trạng thái fixture cho các test khác.
        self._cho_phep_mua_le_cu = frappe.db.get_value(
            "Customer", KHACH_BM, "custom_cho_phep_mua_le"
        )
        frappe.db.set_value("Customer", KHACH_BM, "custom_cho_phep_mua_le", 1)

    def tearDown(self):
        frappe.db.set_value(
            "Customer", KHACH_BM, "custom_cho_phep_mua_le", self._cho_phep_mua_le_cu
        )
        frappe.set_user("Administrator")

    def test_tao_duoc_don_khi_chay_duoi_administrator(self):
        """Administrator KHÔNG có Contact nào trỏ tới khách hàng nào, nên nếu
        lõi còn gọi get_portal_customer() thì test này ném PermissionError."""
        frappe.set_user("Administrator")
        ket_qua = dat_hang.tao_sales_order(
            KHACH_BM,
            mode="ban_le",
            items=[{"item_code": "MYN-GLOVE-M", "qty": 2}],
            request_id=frappe.generate_hash(length=20),
        )
        self.assertTrue(ket_qua["sales_order"])
        self.assertEqual(
            frappe.db.get_value("Sales Order", ket_qua["sales_order"], "customer"),
            KHACH_BM,
        )
