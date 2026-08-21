"""Spec 2026-08-15 §3.5 — Mua lẻ mặc định BẬT. ĐẢO NGƯỢC 21/08.

Chủ đầu tư chốt 19/08: "nghiệp vụ đó áp dụng cho toàn bộ khách hàng" — BR-R1
bỏ hẳn (Task 1), không còn field `Customer.custom_cho_phep_mua_le` nào để
"mặc định bật" nữa (field bị xoá bằng patch `patches/v1_25/xoa_co_mua_le.py`).
Ba ca dưới đây từng chốt hành vi CỦA CÁI CỜ (default=1, backfill khách cũ) —
giờ chốt hành vi SAU KHI CỜ BIẾN MẤT: field không còn tồn tại, và KHÔNG
khách nào — mới hay cũ, cờ cũ đang 0 hay 1 — còn bị BR-R1 chặn.

KHÔNG đụng `patches/v1_15/bat_mua_le_mac_dinh.py` (đã chạy trên site đã
migrate, không bao giờ chạy lại) — chỉ đổi test đang xác nhận hành vi của
field mà bản thân field sắp bị xoá.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang

TEN_KHACH_MOI = "Khách Test Mặc Định Mua Lẻ"
KHACH_CU = "Bệnh viện Bạch Mai"
ITEM = "MYN-GLOVE-M"


class TestMuaLeMacDinhBat(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")

    def test_custom_field_da_bi_xoa(self):
        """Không còn field nào để "mặc định bật" — nó bị xoá hẳn (a), không
        phải chỉ hết tác dụng. Giữ field trông như một chốt kiểm soát mà
        không còn gác gì là phiên bản schema của "bình luận nói sai về
        code" (task-1-brief.md)."""
        ten = frappe.db.get_value(
            "Custom Field",
            {"dt": "Customer", "fieldname": "custom_cho_phep_mua_le"},
            "name",
        )
        self.assertIsNone(ten, "Custom Field phải bị xoá bằng patch xoa_co_mua_le")

    def test_khach_moi_mua_le_duoc_ma_khong_can_co(self):
        """Khách mới tinh, CHƯA TỪNG có field này (đã xoá) — vẫn đặt được
        đơn mua lẻ ngay, không cần "bật sẵn" gì cả vì không còn gì để bật."""
        if frappe.db.exists("Customer", TEN_KHACH_MOI):
            frappe.delete_doc("Customer", TEN_KHACH_MOI, force=True, ignore_permissions=True)
        kh = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": TEN_KHACH_MOI,
            "customer_type": "Company",
        }).insert(ignore_permissions=True)
        # Field cũ còn tồn tại vật lý (chưa chạy patch xoá) mang `default=1`
        # — ép về 0 tường minh để phép thử này không ăn may nhờ default, mà
        # thật sự chứng minh đường ghi không còn đọc field này nữa.
        if "custom_cho_phep_mua_le" in kh.as_dict():
            frappe.db.set_value("Customer", kh.name, "custom_cho_phep_mua_le", 0)

        frappe.set_user("Administrator")
        ket_qua = dat_hang.tao_sales_order(
            kh.name,
            mode="ban_le",
            items=[{"item_code": ITEM, "qty": 1}],
            request_id=frappe.generate_hash(length=20),
        )
        self.assertEqual(
            frappe.db.get_value("Sales Order", ket_qua["sales_order"], "customer"),
            kh.name,
            "khách mới phải mua lẻ được ngay, không cần cờ nào bật sẵn",
        )

    def test_khach_hien_huu_dang_tat_co_van_mua_le_duoc(self):
        """Đảo ngược `test_patch_bat_co_cho_khach_dang_tat` cũ: bản trước
        kiểm patch BACKFILL cờ 0→1 cho khách hiện hữu trước khi khách đó
        mua lẻ được. Giờ khách hiện hữu KHÔNG CẦN backfill gì — đặt được
        ngay cả khi field cũ (còn tồn tại vật lý tới khi patch chạy) đang
        mang giá trị 0 tường minh."""
        cu = frappe.db.get_value("Customer", KHACH_CU, "custom_cho_phep_mua_le")
        frappe.db.set_value("Customer", KHACH_CU, "custom_cho_phep_mua_le", 0)
        try:
            frappe.set_user("Administrator")
            ket_qua = dat_hang.tao_sales_order(
                KHACH_CU,
                mode="ban_le",
                items=[{"item_code": ITEM, "qty": 1}],
                request_id=frappe.generate_hash(length=20),
            )
            self.assertEqual(
                frappe.db.get_value("Sales Order", ket_qua["sales_order"], "customer"),
                KHACH_CU,
                "khách hiện hữu với cờ cũ = 0 vẫn phải mua lẻ được, không cần backfill",
            )
        finally:
            frappe.db.set_value("Customer", KHACH_CU, "custom_cho_phep_mua_le", cu)
