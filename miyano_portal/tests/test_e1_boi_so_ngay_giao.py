"""BR-O11 (bội số quy cách) và BR-O13 (ngày giao) — phần nghiệp vụ thuần.

Hai quy tắc này kiểm được mà không cần phiên đăng nhập, Blanket Order hay
Sales Order nào — đó là lý do chúng nằm ở `portal_dat_hang.py` chứ không nằm
trong `api/portal.py`. Phần nối vào `portal_order_place` (TC-E1-03, TC-E1-04
gọi qua API) đi cùng task đổi chữ ký hàm đó, vì cả hai chạm cùng một chỗ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.portal_dat_hang import (
    kiem_boi_so,
    kiem_ngay_giao,
    ngay_giao_mac_dinh,
)

VT_BOI_SO = "_TEST-E1-BOISO"
VT_KHONG_BOI_SO = "_TEST-E1-TUDO"


def _tao_item(item_code: str, boi_so: int | None = None) -> str:
    if not frappe.db.exists("Item", item_code):
        frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code,
            "item_group": "All Item Groups",
            "stock_uom": "Nos",
            "is_stock_item": 0,
        }).insert(ignore_permissions=True)
    frappe.db.set_value("Item", item_code, "custom_boi_so_dat", boi_so or 0)
    return item_code


class TestBoiSoQuyCach(FrappeTestCase):
    def setUp(self):
        _tao_item(VT_BOI_SO, 10)
        _tao_item(VT_KHONG_BOI_SO, 0)

    def test_dung_boi_so_thi_khong_bao_loi(self):
        self.assertIsNone(kiem_boi_so(VT_BOI_SO, 20))
        self.assertIsNone(kiem_boi_so(VT_BOI_SO, 10))

    def test_sai_boi_so_bao_dung_nguyen_van_formspec(self):
        """Mã `ly_do` cho client dịch (`30_API_Spec` §5), kèm `thong_diep`
        nguyên văn ma trận FormSpec §5 dòng NL-1.6 cho nơi gọi không phải SPA."""
        self.assertEqual(
            kiem_boi_so(VT_BOI_SO, 15),
            {
                "item_code": VT_BOI_SO,
                "ly_do": "sai_boi_so",
                "boi_so": 10,
                "goi_y": 20,
                "thong_diep": "Số lượng phải là bội số của 10. Gần nhất: 20.",
            },
        )

    def test_goi_y_lam_tron_LEN_khong_phai_gan_nhat_theo_khoang_cach(self):
        """11 gần 10 hơn gần 20, nhưng gợi ý phải là 20.

        Khách gõ 11 nghĩa là họ cần ít nhất 11; đề nghị 10 là đề nghị thiếu
        hàng so với nhu cầu họ vừa nói ra.
        """
        loi = kiem_boi_so(VT_BOI_SO, 11)
        self.assertEqual(loi["goi_y"], 20)
        self.assertEqual(
            loi["thong_diep"], "Số lượng phải là bội số của 10. Gần nhất: 20."
        )

    def test_item_khong_khai_boi_so_thi_khong_rang_buoc(self):
        self.assertIsNone(kiem_boi_so(VT_KHONG_BOI_SO, 7))

    def test_item_khong_ton_tai_thi_khong_rang_buoc(self):
        """Không phải việc của hàm này: mặt hàng lạ đã bị chặn ở tầng hạn mức
        và tầng giá trước đó. Ném lỗi ở đây chỉ làm rối thông điệp."""
        self.assertIsNone(kiem_boi_so("_TEST-KHONG-TON-TAI", 3))


class TestNgayGiaoLamViec(FrappeTestCase):
    def test_cong_2_ngay_lam_viec_bo_qua_cuoi_tuan(self):
        # Thứ Năm 30/07/2026 -> T6 31/07 (1) -> T2 03/08 (2)
        self.assertEqual(str(ngay_giao_mac_dinh("2026-07-30")), "2026-08-03")
        # Thứ Hai 03/08 -> T3 04/08 (1) -> T4 05/08 (2), không vướng cuối tuần
        self.assertEqual(str(ngay_giao_mac_dinh("2026-08-03")), "2026-08-05")
        # Thứ Sáu 31/07 -> T2 03/08 (1) -> T3 04/08 (2)
        self.assertEqual(str(ngay_giao_mac_dinh("2026-07-31")), "2026-08-04")
        # Thứ Bảy 01/08 -> T2 03/08 (1) -> T3 04/08 (2)
        self.assertEqual(str(ngay_giao_mac_dinh("2026-08-01")), "2026-08-04")

    def test_ket_qua_khong_bao_gio_roi_vao_cuoi_tuan(self):
        from frappe.utils import add_days, getdate

        ngay = getdate("2026-08-01")
        for _ in range(30):
            kq = ngay_giao_mac_dinh(ngay)
            self.assertLess(
                getdate(kq).weekday(), 5, f"{ngay} -> {kq} rơi vào cuối tuần"
            )
            ngay = add_days(ngay, 1)

    def test_ngay_qua_khu_bi_tu_choi_kem_nguyen_van_formspec(self):
        hom_qua = frappe.utils.add_days(frappe.utils.today(), -1)
        loi = kiem_ngay_giao(hom_qua)
        self.assertIsNotNone(loi)
        self.assertEqual(loi["ly_do"], "ngay_giao_khong_hop_le")
        self.assertIsNone(
            loi.get("item_code"), "lỗi của cả đơn, không gắn vào dòng nào"
        )
        thong_diep = loi["thong_diep"]
        self.assertTrue(
            thong_diep.startswith("Ngày giao sớm nhất là "),
            f"thông điệp không khớp FormSpec §5 NL-1.7: {thong_diep!r}",
        )
        self.assertIn("(sau 2 ngày làm việc).", thong_diep)

    def test_hom_nay_va_tuong_lai_deu_di_qua(self):
        """Hôm nay KHÔNG bị chặn: quy tắc là 'không nhận ngày quá khứ'
        (BR-O13), còn +2 ngày làm việc chỉ là giá trị MẶC ĐỊNH. Khách chủ
        động chọn giao gấp trong ngày là việc của sales, không phải lỗi nhập
        liệu."""
        self.assertIsNone(kiem_ngay_giao(frappe.utils.today()))
        self.assertIsNone(
            kiem_ngay_giao(frappe.utils.add_days(frappe.utils.today(), 30))
        )
