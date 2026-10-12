"""BR-O15 / QĐ-8 / NL-1.11 — hạn mức khai 0 nghĩa là KHÔNG GIỚI HẠN.

TC-E1-06, 08, và tầng nghiệp vụ `han_muc_con`.

`remaining_qty` cũ trả `qty - ordered_qty`, nên một dòng khai 0 đã đặt 30 ra
**-30** — đúng ngược quy ước QĐ-8. `han_muc_con` trả `None` cho dòng đó.

Từ spec 2026-10-09 (giá theo Price List, §4.2) việc DỰNG ĐƠN không còn kiểm
hạn mức hay gắn `against_blanket_order` — ba bài về đường đặt hàng (TC-E1-05,
TC-E1-07 và bài "dòng có hạn mức vẫn gắn `against_blanket_order`") đã xoá
cùng hành vi đó; vế mới nằm ở `test_xay_don_bang_gia.py`. File này còn giữ
những gì VẪN đọc hạn mức: `portal_context.han_muc_con`, danh mục cũ
`portal_catalog` và `used_pct` của `portal_contracts`.

`setUp` đặt hạn mức thành giá trị XÁC ĐỊNH thay vì đọc trạng thái sẵn có của
site: một test dựa vào dữ liệu mà thao tác nghiệp vụ bình thường có thể đổi
thì sớm muộn cũng đỏ vì lý do không liên quan.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_context import han_muc_con
from miyano_portal.setup.seed_demo import seed_demo

VT_KGH = "HC0009"      # đặt qty = 0  -> KHÔNG GIỚI HẠN
VT_GIOI_HAN = "VT0005"  # đặt qty = 200, đã đặt 195 -> còn 5


class TestHanMucKhongGioiHan(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]

        for item_code, qty, da_dat in (
            (VT_KGH, 0, 30),
            (VT_GIOI_HAN, 200, 195),
        ):
            frappe.db.set_value(
                "Blanket Order Item",
                {"parent": self.bo, "item_code": item_code},
                {"qty": qty, "ordered_qty": da_dat},
            )

    # ---------- tầng nghiệp vụ ----------
    def test_han_muc_con_tra_none_khi_khai_0(self):
        con_lai, da_dat = han_muc_con(self.bo, VT_KGH)
        self.assertIsNone(con_lai, "hạn mức khai 0 phải là None = không giới hạn")
        self.assertEqual(da_dat, 30.0, "vẫn phải biết đã đặt luỹ kế bao nhiêu")

    def test_han_muc_con_van_tra_so_khi_khai_duong(self):
        con_lai, da_dat = han_muc_con(self.bo, VT_GIOI_HAN)
        self.assertEqual(con_lai, 5.0)
        self.assertEqual(da_dat, 195.0)

    def test_mat_hang_ngoai_hop_dong_khac_han_voi_khong_gioi_han(self):
        """`(0.0, 0.0)` = không đặt được, KHÔNG phải `None` = không giới hạn.
        Gộp hai thứ này là cách mở toang hạn mức cho mọi mặt hàng lạ."""
        con_lai, da_dat = han_muc_con(self.bo, "_TEST-NGOAI-HOP-DONG")
        self.assertEqual(con_lai, 0.0)
        self.assertEqual(da_dat, 0.0)

    # ---------- TC-E1-06: danh mục ----------
    def test_catalog_danh_dau_khong_gioi_han(self):
        rows = {r["item_code"]: r for r in portal.portal_catalog(self.bo)}

        kgh = rows[VT_KGH]
        self.assertTrue(kgh["khong_gioi_han"])
        self.assertIsNone(
            kgh["remaining"],
            "None chứ không phải 0 — giao diện phải phân biệt được "
            "'không giới hạn' với 'hết hạn mức' (NL-1.11 vs NL-1.2)",
        )
        self.assertEqual(kgh["used"], 30.0)

        gh = rows[VT_GIOI_HAN]
        self.assertFalse(gh["khong_gioi_han"])
        self.assertEqual(gh["remaining"], 5.0)

    # ---------- TC-E1-08 ----------
    def test_phan_tram_han_muc_bo_qua_dong_khong_gioi_han(self):
        """Mẫu số chỉ gồm dòng có hạn mức > 0: 195/200 = 97,5%.

        Nếu dòng khai 0 lọt vào mẫu số thì kết quả thành 225/200 — vô nghĩa,
        và cảnh báo "dùng ≥ 80%" sẽ báo động sai.
        """
        hd = {r["name"]: r for r in portal.portal_contracts()}[self.bo]
        self.assertEqual(hd["used_pct"], 97.5)
        self.assertEqual(
            hd["item_count"], 2, "vẫn đếm ĐỦ số mặt hàng, kể cả dòng không giới hạn"
        )
