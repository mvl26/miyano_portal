"""Spec 2026-08-15 §3.6 — PDF báo giá.

Ba thứ được bảo vệ ở đây, theo thứ tự quan trọng: KHÔNG lộ đơn của khách
khác; KHÔNG lộ giá sales chưa gửi; và bản báo giá phải ĐỦ — thiếu dòng đặt
ngoài đã khớp mã là khách nhận báo giá thiếu đúng món họ lo nhất.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, TRANG_THAI_CHO_KHACH
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, PXN, RETAIL_CO_GIA, USER_BVBM, USER_PXN, VT_HDNT, _rid, _seed_mua_le,
)

PRINT_FORMAT = "Miyano - Báo giá"
NOTI_BAO_GIA = "Portal - Báo giá sẵn sàng"


class TestBaoGiaPdf(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _don_cho_khach_dong_y(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 3}]),
            dat_ngoai=json.dumps([
                {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
            ]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        so.items[0].rate = 25000
        # Khớp mã cho dòng đặt ngoài — đúng thao tác sales làm khi báo giá.
        so.custom_dat_ngoai[0].item_khop = RETAIL_CO_GIA
        so.workflow_state = TRANG_THAI_CHO_KHACH
        so.save(ignore_permissions=True)
        frappe.set_user(USER_BVBM)
        return so.name

    def test_print_format_da_duoc_cai(self):
        self.assertTrue(frappe.db.exists("Print Format", PRINT_FORMAT))
        self.assertEqual(
            frappe.db.get_value("Print Format", PRINT_FORMAT, "doc_type"), "Sales Order"
        )

    def test_pdf_chua_dong_dat_ngoai_da_khop_ma(self):
        ten = self._don_cho_khach_dong_y()
        html = frappe.get_print(
            "Sales Order", ten, print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertIn("Găng tay nitrile size M", html)

    def test_pdf_dung_dau_cham_phan_nhom_khong_dau_phay(self):
        """review Minor — quy ước dự án là `1.234.567 ₫` (dấu CHẤM phân
        nhóm), không phải `1,234,567 ₫` (dấu phẩy, mặc định của
        "{:,.0f}".format() chưa xử lý).

        CON SỐ ĐỔI ở Task 13 (QĐ-G13, bẫy 2), hành vi được kiểm thì KHÔNG:
        fixture đặt 3 `RETAIL_CO_GIA` trong `items` và một dòng gõ tay 5
        đơn vị mà sales khớp về CHÍNH mã đó. Trước Task 13, dòng gõ tay
        không bao giờ thành hàng thật nên báo giá chỉ tính 3 × 25.000 =
        75.000 ₫ — tức khách nhận báo giá THIẾU đúng món họ gõ tay, đúng
        lỗi Task 13 sinh ra để sửa. Giờ 5 đơn vị đó được GỘP vào dòng sẵn
        có (không thêm dòng thứ hai cùng mã): 8 × 25.000 = 200.000 ₫, và
        câu "đã khớp mã và tính vào bảng báo giá phía trên" in ở cuối mẫu
        lần đầu tiên nói đúng sự thật."""
        ten = self._don_cho_khach_dong_y()
        html = frappe.get_print(
            "Sales Order", ten, print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertIn("200.000 ₫", html)
        self.assertNotIn("200,000", html)

    def test_pdf_khong_chua_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps([{"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20}]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        html = frappe.get_print(
            "Sales Order", res["sales_order"], print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertNotIn(ITEM_GIU_CHO, html)

    def test_khach_khac_khong_tai_duoc(self):
        ten = self._don_cho_khach_dong_y()
        frappe.set_user(USER_PXN)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_bao_gia_pdf(order=ten)

    def test_don_chua_gui_khach_thi_khong_tai_duoc(self):
        """Đơn còn ở "Chờ xác nhận" = sales chưa chốt giá. Cho tải là lộ
        giá nháp và biến một con số đang sửa thành cam kết với khách."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            request_id=_rid(),
            mode="ban_le",
        )
        with self.assertRaises(frappe.ValidationError):
            portal.portal_bao_gia_pdf(order=res["sales_order"])

    def test_don_hdnt_o_cho_khach_dong_y_khong_tai_duoc_pdf(self):
        """review I-2 — "hiệu lực báo giá" là khái niệm CHỈ của Mua lẻ
        (`portal_order_track` trả `han_hieu_luc: None` cho đơn khác;
        `quet_bao_gia_het_han` lọc riêng `custom_loai_don: "Mua lẻ"`). Một
        đơn Theo hợp đồng khung (luồng E2 gốc) cũng có thể ở "Chờ khách đồng
        ý" — endpoint phải từ chối tải PDF báo giá cho nhánh này, không chỉ
        dựa vào workflow_state."""
        bo = portal.portal_contracts()[0]["name"]
        res = portal.portal_order_place(
            bo, json.dumps([{"item_code": VT_HDNT, "qty": 1}]),
            mode="hdnt", request_id=_rid(),
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.custom_loai_don, "Theo HĐNT")
        so.workflow_state = TRANG_THAI_CHO_KHACH
        so.save(ignore_permissions=True)
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_bao_gia_pdf(order=so.name)

    def test_notification_bao_gia_chi_gui_cho_mua_le(self):
        """review I-2 — `condition` của Notification "Portal - Báo giá sẵn
        sàng" phải lọc theo `custom_loai_don == 'Mua lẻ'`, nếu không mọi đơn
        hợp đồng khung vào "Chờ khách đồng ý" cũng gửi kèm PDF đề "Hiệu lực
        đến..." mà không job nào thi hành. Đánh giá THẬT điều kiện bằng đúng
        cơ chế Notification dùng (`frappe.safe_eval`), không chỉ soát chuỗi."""
        cond = frappe.db.get_value("Notification", NOTI_BAO_GIA, "condition")
        doc_hdnt = frappe._dict(
            custom_nguon_don="Client Portal",
            custom_loai_don="Theo HĐNT",
            workflow_state="Chờ khách đồng ý",
        )
        doc_mua_le = frappe._dict(
            custom_nguon_don="Client Portal",
            custom_loai_don="Mua lẻ",
            workflow_state="Chờ khách đồng ý",
        )
        self.assertFalse(frappe.safe_eval(cond, None, {"doc": doc_hdnt}))
        self.assertTrue(frappe.safe_eval(cond, None, {"doc": doc_mua_le}))

    def test_cai_notification_khi_print_format_chua_ton_tai(self):
        """review I-1 — dựng LẠI đúng tình huống lỗi trên site đi sau một
        phiên bản: site chạy `v1_14.install_bao_gia_san_sang_notification`
        (gọi `install_portal_notifications()`) TRƯỚC KHI mẫu in "Miyano -
        Báo giá" tồn tại (mẫu đó chỉ tạo sau, ở `v1_15.install_print_format_
        bao_gia`). `Document.insert()` chạy `_validate_links()` VÔ ĐIỀU
        KIỆN — nếu DEF còn gán `print_format` cho một Link tới bản ghi chưa
        tồn tại, insert ném `LinkValidationError` và `bench migrate` chết
        giữa chừng. Xoá cả hai bản ghi rồi cài lại đúng thứ tự đó để kiểm.

        Khôi phục lại đúng trạng thái cuối cùng của một `bench migrate` XONG
        (gọi tiếp hai patch v1_15 y hệt thứ tự thật trong `patches.txt`) ở
        cuối test — hai bản ghi này là fixture site DÙNG CHUNG cho các test
        khác trong CÙNG class/tiến trình chạy (rollback của FrappeTestCase
        chỉ đảm bảo ở biên test-case, không đảm bảo cô lập giữa các bước bên
        trong MỘT test); để trống chúng lại sẽ làm hỏng
        `test_print_format_da_duoc_cai`/`test_pdf_khong_chua_dong_giu_cho`
        chạy SAU trong cùng lượt."""
        from miyano_portal.patches.v1_15.install_print_format_bao_gia import (
            execute as cai_lai_print_format_va_gan,
        )
        from miyano_portal.setup.install_notifications import install_portal_notifications

        if frappe.db.exists("Notification", NOTI_BAO_GIA):
            frappe.delete_doc("Notification", NOTI_BAO_GIA, ignore_permissions=True, force=True)
        if frappe.db.exists("Print Format", PRINT_FORMAT):
            frappe.delete_doc(
                "Print Format", PRINT_FORMAT, ignore_permissions=True, force=True
            )
        self.assertFalse(frappe.db.exists("Print Format", PRINT_FORMAT))

        try:
            # Không được ném lỗi dù mẫu in CHƯA tồn tại — đây chính là thứ
            # tự patch chạy thật trên một site đi sau (v1_14 trước v1_15).
            install_portal_notifications()
            self.assertTrue(frappe.db.exists("Notification", NOTI_BAO_GIA))
            self.assertFalse(
                frappe.db.get_value("Notification", NOTI_BAO_GIA, "print_format"),
                "print_format phải BỎ TRỐNG ở lần cài này — chỉ "
                "v1_15.install_print_format_bao_gia mới được ghi field đó",
            )
        finally:
            # v1_15.install_print_format_bao_gia (đã chạy thật trong
            # `patches.txt`) — tạo lại mẫu in rồi gán attach_print/
            # print_format qua `frappe.db.set_value`, bỏ qua `_validate_
            # links`. Khôi phục về ĐÚNG trạng thái sau một `bench migrate`
            # đầy đủ.
            cai_lai_print_format_va_gan()

    def test_patch_cap_nhat_condition_cua_ban_ghi_da_cai(self):
        """review I-2/I-1 — patch `v1_15.gioi_han_bao_gia_pdf_mua_le` phải tự
        SỬA `condition` của bản ghi Notification ĐÃ CÀI trên site (site đã
        chạy `v1_14.install_bao_gia_san_sang_notification` từ trước): hàm cài
        đặt gốc `install_portal_notifications()` bỏ qua (không ghi đè) bản
        ghi đã tồn tại, nên chỉ sửa DEFS không đủ — dựng lại đúng tình huống
        đó bằng cách đặt `condition` về bản CŨ (thiếu lọc `custom_loai_don`)
        rồi chạy lại `execute()` của patch, xác nhận nó tự sửa lại."""
        from miyano_portal.patches.v1_15 import gioi_han_bao_gia_pdf_mua_le as patch

        condition_cu = (
            "doc.custom_nguon_don == 'Client Portal' and "
            "doc.workflow_state == 'Chờ khách đồng ý'"
        )
        frappe.db.set_value("Notification", NOTI_BAO_GIA, "condition", condition_cu)
        self.assertEqual(
            frappe.db.get_value("Notification", NOTI_BAO_GIA, "condition"), condition_cu
        )
        patch.execute()
        cond = frappe.db.get_value("Notification", NOTI_BAO_GIA, "condition")
        self.assertIn("custom_loai_don", cond)
        self.assertIn("Mua lẻ", cond)
        self.assertNotEqual(cond, condition_cu)
