"""BR-O3 gom lỗi MỘT LẦN + phong bì lỗi máy đọc được (`30_API_Spec` §1.1, §5).

Hai khiếm khuyết được chốt lại ở đây:

1. `portal_order_place` ném văn xuôi (`"<br>".join(...)`) chứ không trả mảng
   `loi[]` có mã `ly_do` như API Spec §1.1 quy định. TC-E1-03 và TC-E1-07 chấm
   theo mã, không theo câu chữ. Chính `portal_reorder` trong cùng file đã trả
   mã (`ngoai_hdnt`/`het_han_muc`/`thieu_gia`) và `OrderDetail.vue` đã có bảng
   dịch — hai endpoint anh em làm hai kiểu là lệch của ta, không phải tài liệu
   mơ hồ.

2. Nặng hơn: `thieu_gia` ném ngay tại mặt hàng đầu tiên, **trong vòng dựng
   đơn**, tức là SAU vòng gom hạn mức/bội số. Giỏ vừa vượt hạn mức vừa thiếu
   giá bắt khách đi hai vòng: sửa hạn mức, gửi lại, mới lòi ra lỗi giá. Đó là
   đúng thứ BR-O3 sinh ra để cấm.

Ca cũ chỉ đặt MỘT mặt hàng nên không thể thấy cả hai khiếm khuyết — khoảng hở
giữa phép kiểm và yêu cầu thật.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"
PRICE_LIST = "HĐNT-BVBM-2026"
VT = "VT0005"
HC = "HC0009"
# Giá gốc theo `seed_demo.ITEMS`. Cần để `setUp` khôi phục: `seed_demo` chỉ tạo
# `Item Price` khi CHƯA có, nên nó không hoàn tác được giá do ca trước bẻ về 0.
GIA_GOC = {VT: 1200, HC: 350000}


def _rid() -> str:
    return frappe.generate_hash(length=12)


def _dat_gia(item_code: str, rate) -> None:
    frappe.db.set_value(
        "Item Price",
        {"item_code": item_code, "price_list": PRICE_LIST},
        "price_list_rate",
        rate,
    )


def _dong_hop_dong(item_code: str) -> list:
    """Mọi dòng `item_code` trên hợp đồng bán CÒN HIỆU LỰC của BVBM.

    Task 12 (QĐ-G12) — giá của một dòng hợp đồng lấy từ CHÍNH hợp đồng
    TRƯỚC, bảng giá chỉ là bước lui. Nên "chưa có giá" chỉ còn đúng khi CẢ
    HAI đều trống; bẻ mỗi `Item Price` về 0 như bản trước Task 12 không còn
    tái lập được tình huống nào cả (cổng sẽ định giá bằng `rate` hợp đồng và
    ĐI, đúng như bản vá muốn). Quét MỌI hợp đồng còn hiệu lực chứ không chỉ
    `self.bo`: chỉ cần một hợp đồng khác cũng khai mã đó là cổng lại có giá.
    """
    cha = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": BVBM, "blanket_order_type": "Selling", "docstatus": 1,
            "from_date": ["<=", frappe.utils.today()],
            "to_date": [">=", frappe.utils.today()],
        },
        pluck="name",
    )
    if not cha:
        return []
    return frappe.get_all(
        "Blanket Order Item",
        filters={"item_code": item_code, "parent": ["in", cha]},
        pluck="name",
    )


def _dat_gia_hop_dong(item_code: str, rate) -> None:
    for ten in _dong_hop_dong(item_code):
        frappe.db.set_value("Blanket Order Item", ten, "rate", rate)


def _xoa_gia(item_code: str) -> None:
    """CHƯA KHAI GIÁ Ở ĐÂU CẢ — bảng giá 0 VÀ hợp đồng 0 (xem QĐ-G12 ở
    `_dong_hop_dong`). Cả hai vế đều bắt buộc kể từ Task 12."""
    _dat_gia(item_code, 0)
    _dat_gia_hop_dong(item_code, 0)


class TestPhongBiLoiCoCauTruc(FrappeTestCase):
    def setUp(self):
        seed_demo()
        # Sales phụ trách phải có: nhánh thiếu giá gọi `bao_thieu_gia`, không
        # có người nhận thì hàm im lặng — vẫn chạy, nhưng ta mất một mắt xích.
        frappe.db.set_value("Customer", BVBM, "account_manager", "sales_user@demo.miyano")
        frappe.db.delete("Notification Log", {"subject": ("like", "Portal - Thiếu giá%")})
        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]
        # Hạn mức xác định: VT còn 5, HC rộng rãi.
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.bo, "item_code": VT},
            {"qty": 200, "ordered_qty": 195},
        )
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.bo, "item_code": HC},
            {"qty": 10000, "ordered_qty": 0},
        )
        frappe.db.set_value("Item", VT, "custom_boi_so_dat", 0)
        frappe.db.set_value("Item", HC, "custom_boi_so_dat", 0)
        # `FrappeTestCase` rollback một lần mỗi CLASS: ca nào bẻ giá về 0 thì
        # ca sau vẫn thấy 0 và báo `thieu_gia` thay vì lý do đang muốn kiểm.
        # Task 12 — khôi phục CẢ HAI nguồn giá, cùng lý do `_xoa_gia` bẻ cả
        # hai: `GIA_GOC` đúng bằng `rate` mà `seed_demo` khai trên hợp đồng.
        for ma, rate in GIA_GOC.items():
            _dat_gia(ma, rate)
            _dat_gia_hop_dong(ma, rate)
        for ma, rate in GIA_GOC.items():
            self.assertTrue(
                _dong_hop_dong(ma),
                f"Tiền đề hỏng: {ma} không nằm trên hợp đồng còn hiệu lực nào "
                "của khách — ca 'thiếu giá' sẽ xanh vì sai lý do.",
            )

    def _dat(self, dong, **kw):
        """Gọi order_place, trả về (mảng `loi`, văn xuôi). Xoá khoá `loi` cũ
        trước khi gọi: `frappe.local.response` sống qua nhiều lời gọi trong
        cùng một test, đọc phải rác của lần trước là kiểu dương tính giả tệ
        nhất — test xanh trong khi code không hề đặt gì."""
        frappe.local.response.pop("loi", None)
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(self.bo, json.dumps(dong), request_id=_rid(), **kw)
        return frappe.local.response.get("loi"), str(ctx.exception)

    @staticmethod
    def _theo_ma(loi):
        return {d["item_code"]: d for d in loi if d.get("item_code")}

    # ---------- khiếm khuyết 2: BR-O3 với thiếu giá ----------
    def test_vuot_han_muc_va_thieu_gia_bao_CUNG_MOT_LAN(self):
        """Đây là ca đã hụt: hai loại lỗi khác nhau trong một giỏ."""
        _xoa_gia(HC)
        loi, _ = self._dat([
            {"item_code": VT, "qty": 10},   # còn 5
            {"item_code": HC, "qty": 1},    # chưa có giá
        ])
        self.assertIsNotNone(loi, "phải có mảng `loi` trong phản hồi")
        theo_ma = self._theo_ma(loi)
        self.assertEqual(
            set(theo_ma), {VT, HC},
            "khách phải thấy CẢ HAI vấn đề trong một lần gửi, không phải "
            "sửa hạn mức xong gửi lại mới biết còn thiếu giá",
        )
        self.assertEqual(theo_ma[VT]["ly_do"], "vuot_han_muc")
        self.assertEqual(theo_ma[HC]["ly_do"], "thieu_gia")

    def test_nhieu_mat_hang_thieu_gia_deu_duoc_liet_ke(self):
        _xoa_gia(VT)
        _xoa_gia(HC)
        loi, _ = self._dat([
            {"item_code": VT, "qty": 1},
            {"item_code": HC, "qty": 1},
        ])
        self.assertEqual(
            {d["item_code"] for d in loi}, {VT, HC},
            "ném ở mặt hàng thiếu giá đầu tiên là bắt khách đi từng vòng một",
        )

    def test_thieu_gia_van_bao_sales_cho_MOI_mat_hang(self):
        _xoa_gia(VT)
        _xoa_gia(HC)
        self._dat([{"item_code": VT, "qty": 1}, {"item_code": HC, "qty": 1}])
        frappe.set_user("Administrator")
        for ma in (VT, HC):
            with self.subTest(item=ma):
                self.assertTrue(
                    frappe.db.exists(
                        "Notification Log",
                        {"for_user": "sales_user@demo.miyano", "subject": ("like", f"%{ma}%")},
                    ),
                    "gom lỗi lại không được làm mất thông báo cho sales",
                )

    # ---------- khiếm khuyết 1: mã lý do ----------
    def test_vuot_han_muc_kem_con_lai(self):
        """TC-E1-07 — `con_lai=5` phải là SỐ trong payload, không phải chữ
        nhúng trong câu."""
        loi, _ = self._dat([{"item_code": VT, "qty": 10}])
        self.assertEqual(loi[0]["ly_do"], "vuot_han_muc")
        self.assertEqual(loi[0]["con_lai"], 5.0)

    def test_het_han_muc_khac_ma_voi_vuot_han_muc(self):
        """Còn 0 là "hết", còn 5 mà đòi 10 là "vượt" — §5 tách hai mã, và
        `portal_reorder` đã dùng `het_han_muc` đúng nghĩa đó."""
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.bo, "item_code": VT},
            "ordered_qty",
            200,
        )
        loi, _ = self._dat([{"item_code": VT, "qty": 1}])
        self.assertEqual(loi[0]["ly_do"], "het_han_muc")
        self.assertEqual(loi[0]["con_lai"], 0.0)

    def test_sai_boi_so_kem_boi_so_va_goi_y(self):
        """TC-E1-03 — "417 `sai_boi_so`, gợi ý 20"."""
        frappe.db.set_value("Item", HC, "custom_boi_so_dat", 10)
        loi, _ = self._dat([{"item_code": HC, "qty": 15}])
        self.assertEqual(loi[0]["ly_do"], "sai_boi_so")
        self.assertEqual(loi[0]["boi_so"], 10)
        self.assertEqual(loi[0]["goi_y"], 20)

    def test_ngay_giao_qua_khu_co_ma_rieng_khong_kem_item(self):
        """TC-E1-04 — mã `ngay_giao_khong_hop_le`. Lỗi của cả đơn nên không
        gắn `item_code`."""
        loi, _ = self._dat(
            [{"item_code": HC, "qty": 1}], delivery_date="2020-01-01"
        )
        ngay = [d for d in loi if d["ly_do"] == "ngay_giao_khong_hop_le"]
        self.assertEqual(len(ngay), 1)
        self.assertIsNone(ngay[0].get("item_code"))

    def test_loi_ngay_giao_va_loi_mat_hang_bao_cung_luc(self):
        loi, _ = self._dat(
            [{"item_code": VT, "qty": 10}], delivery_date="2020-01-01"
        )
        self.assertEqual(
            {d["ly_do"] for d in loi}, {"ngay_giao_khong_hop_le", "vuot_han_muc"}
        )

    # ---------- không được đánh mất cái đang có ----------
    def test_van_giu_nguyen_van_FormSpec_trong_van_xuoi(self):
        """Thêm phong bì máy đọc KHÔNG được lấy đi câu chữ: `frappe.throw`
        vẫn phải mang thông điệp FormSpec §5 cho mọi nơi gọi không phải SPA
        (desk, script, integration cũ)."""
        _xoa_gia(HC)
        _, van_xuoi = self._dat([
            {"item_code": VT, "qty": 10},
            {"item_code": HC, "qty": 1},
        ])
        self.assertIn("chỉ còn 5 theo hạn mức hợp đồng khung", van_xuoi)
        self.assertIn("chưa có giá trong hợp đồng", van_xuoi)
        self.assertIn("Miyano đã nhận được thông báo", van_xuoi)

    def test_moi_muc_loi_deu_co_thong_diep_rieng(self):
        """Client dịch từ `ly_do`, nhưng payload vẫn kèm `thong_diep` để chỗ
        nào chưa kịp cập nhật bảng dịch thì hiện chữ đúng thay vì mã trần."""
        loi, _ = self._dat([{"item_code": VT, "qty": 10}])
        self.assertTrue(loi[0]["thong_diep"])

    def test_don_hop_le_khong_de_lai_khoa_loi(self):
        """Đặt thành công mà `loi` còn sót lại từ lần trước thì giao diện sẽ
        báo lỗi trên một đơn vừa tạo xong."""
        self._dat([{"item_code": VT, "qty": 10}])
        kq = portal.portal_order_place(
            self.bo, json.dumps([{"item_code": VT, "qty": 5}]), request_id=_rid()
        )
        self.assertTrue(kq["sales_order"])
        self.assertIsNone(frappe.local.response.get("loi"))
