"""Spec 2026-08-15 §3.4 — yêu cầu TOÀN hàng chưa có mã.

ERPNext không lưu nổi chứng từ bán với `items` rỗng (đã kiểm thực nghiệm, ghi
ở api/portal.py:655). Item giữ chỗ `HANG-DAT-NGOAI` là lối ra — nhưng CHỈ khi
giỏ không còn mặt hàng thật nào: `resolve_ban_le_company()` GIAO tập company
của mọi mặt hàng trong giỏ, nên chèn vô điều kiện có thể làm RỖNG phép giao
và hỏng một giỏ hỗn hợp vốn đang hợp lệ.

Từ patch v1_44 dòng giữ chỗ chỉ còn sinh trên Quotation; Sales Order cũ còn
mang nó thì vẫn không xác nhận được, không lộ ra cổng, không lên mẫu in.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests import don_mua_le_cu
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, RETAIL_CO_GIA, USER_BVBM, _rid, _seed_mua_le,
)

DAT_NGOAI_MAU = [
    {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
    {"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20},
]


class TestDatNgoaiGiuCho(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)
        frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_don_toan_hang_chua_co_ma_van_dat_duoc(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        # Spec 2026-10-12 §5 — giỏ toàn dòng gõ tay sinh Quotation, không
        # sinh Sales Order; dòng giữ chỗ nay nằm trên Quotation.
        self.assertIsNone(res["sales_order"])
        frappe.set_user("Administrator")
        bg = frappe.get_doc("Quotation", res["bao_gia"])
        self.assertEqual(bg.workflow_state, "Chờ Miyano báo giá")
        self.assertEqual(
            frappe.db.get_value("Portal De Xuat Mua", res["de_xuat"], "bao_gia"), bg.name
        )
        self.assertEqual(
            [i.item_code for i in bg.items], [ITEM_GIU_CHO],
            "yêu cầu toàn hàng lạ phải có đúng MỘT dòng giữ chỗ",
        )
        self.assertEqual(len(bg.custom_dat_ngoai), 2)

    def test_gio_hon_hop_KHONG_chen_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        # Spec 2026-10-12 §5 — giỏ có dòng gõ tay sinh Quotation.
        self.assertIsNone(res["sales_order"])
        frappe.set_user("Administrator")
        bg = frappe.get_doc("Quotation", res["bao_gia"])
        self.assertEqual(bg.workflow_state, "Chờ Miyano báo giá")
        self.assertEqual(
            frappe.db.get_value("Portal De Xuat Mua", res["de_xuat"], "bao_gia"), bg.name
        )
        ma = [i.item_code for i in bg.items]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "chèn giữ chỗ vào giỏ hỗn hợp sẽ thu hẹp resolve_ban_le_company()",
        )
        self.assertEqual(ma, [RETAIL_CO_GIA])

    def test_gio_rong_hoan_toan_van_bi_tu_choi(self):
        """Không hàng có mã, KHÔNG cả dòng đặt ngoài — không có nhu cầu nào
        để phục vụ, đơn rỗng là lỗi client chứ không phải tình huống nghiệp vụ."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([]),
                dat_ngoai=json.dumps([]),
                request_id=_rid(),
                mode="ban_le",
            )

    def _don_con_dong_giu_cho(self):
        """Đơn cũ toàn hàng chưa có mã còn dòng giữ chỗ trong `items` — hình
        dạng patch v1_44 để lại (dòng gõ tay đã chuyển thành Comment). Đường
        đặt hàng không còn sinh ra đơn như vậy, nên dựng bằng một đơn thường
        rồi thêm tay dòng giữ chỗ trên Desk."""
        res = don_mua_le_cu.dat_truc_tiep(
            BVBM,
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        so.append("items", {
            "item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0, "price_list_rate": 0,
            "warehouse": so.items[0].warehouse,
            "delivery_date": so.delivery_date,
        })
        so.save(ignore_permissions=True)
        so.reload()
        self.assertIn(ITEM_GIU_CHO, [i.item_code for i in so.items])
        return so

    def test_khong_submit_duoc_khi_con_dong_giu_cho(self):
        """`kiem_khong_con_dong_giu_cho` (`before_submit` của Sales Order) —
        khách sẽ nhận PDF "Xác nhận đơn hàng" với một dòng kỹ thuật nội bộ
        nếu đơn còn dòng giữ chỗ mà vẫn xác nhận được."""
        so = self._don_con_dong_giu_cho()
        with self.assertRaises(frappe.ValidationError) as ctx:
            so.submit()
        self.assertIn("còn dòng giữ chỗ kỹ thuật", str(ctx.exception))
        so.reload()
        self.assertEqual(so.docstatus, 0, "chốt phải chặn TRƯỚC khi ghi nhận submit")

    def test_cong_khong_bao_gio_thay_dong_giu_cho(self):
        so = self._don_con_dong_giu_cho()
        frappe.set_user(USER_BVBM)
        track = portal.portal_order_track(order=so.name)
        ma = [i["item_code"] for i in track["items"]]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "dòng giữ chỗ là chi tiết kỹ thuật nội bộ, không được lọt ra cổng",
        )
        self.assertEqual(ma, [RETAIL_CO_GIA])

    def test_danh_muc_ban_le_khong_chua_item_giu_cho(self):
        """review C-1(a) — `ITEM_GIU_CHO` có `disabled=0`, `is_sales_item=1`
        (bắt buộc để đơn toàn hàng chưa có mã lưu được, §3.4) nên nếu danh
        mục không loại nó tường minh, nó lọt vào như một sản phẩm khách duyệt
        được — đã kiểm trên site thật, từ khoá "đặt ngoài" khớp ngay chính
        tên item giữ chỗ.

        Bài này từng hỏi `portal_catalog_ban_le`; endpoint đó đã gỡ (spec
        2026-10-09 §7) và chốt sống tiếp ở danh mục gộp `portal_catalog_gop`
        — danh mục DUY NHẤT khách còn nhìn thấy."""
        res = portal.portal_catalog_gop(tu_khoa="đặt ngoài")
        ma = [r["item_code"] for r in res["rows"]]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "item giữ chỗ là chi tiết kỹ thuật nội bộ, không phải sản phẩm",
        )
        # Tìm thẳng bằng CHÍNH mã giữ chỗ cũng không được ra nó — từ khoá
        # khớp cả cột mã lẫn cột tên, nên đây là phép hỏi trực diện nhất.
        res_toan_bo = portal.portal_catalog_gop(tu_khoa=ITEM_GIU_CHO, limit=1000)
        self.assertNotIn(ITEM_GIU_CHO, [r["item_code"] for r in res_toan_bo["rows"]])

    def test_payload_gui_thang_item_giu_cho_bi_tu_choi(self):
        """review C-1(b) — đường ghi phải tự chốt lại, không tin danh mục đã
        lọc: khách (hoặc client bị sửa) gửi thẳng `item_code=ITEM_GIU_CHO`
        trong payload `items` như bất kỳ mã nào khác."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": ITEM_GIU_CHO, "qty": 1}]),
                dat_ngoai=json.dumps([]),
                request_id=_rid(),
                mode="ban_le",
            )
        # Đơn không được tạo ra — chốt phải chặn TRƯỚC khi ghi, không phải
        # sau (không có Sales Order rác nào ứng với request_id vừa gửi).

    def test_mau_xac_nhan_don_hang_khong_in_dong_giu_cho(self):
        """Việc thêm (controller, ngoài Task 9), lớp phòng thủ THỨ HAI — nếu
        chốt `kiem_khong_con_dong_giu_cho` (ở `before_submit`) đúng thì dòng
        giữ chỗ không bao giờ tới được một đơn ĐÃ SUBMIT, nên test này dựng
        thẳng đơn ở docstatus=0 (chưa submit, không cần đi qua chốt) để kiểm
        RIÊNG mẫu in — độc lập với chốt ở (a), không phụ thuộc chốt đó luôn
        đúng ở mọi đường ghi trong tương lai."""
        so = self._don_con_dong_giu_cho()
        html = frappe.get_print(
            "Sales Order", so.name,
            print_format="Miyano - Xác nhận đơn hàng", no_letterhead=1,
        )
        self.assertNotIn(ITEM_GIU_CHO, html)
