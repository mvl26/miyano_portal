"""BR-O3 gom lỗi MỘT LẦN + phong bì lỗi máy đọc được (`30_API_Spec` §1.1, §5).

`portal_order_place` không chỉ ném văn xuôi (`"<br>".join(...)`): nó trả mảng
`loi[]` có mã `ly_do` như API Spec §1.1 quy định, và gom MỌI lỗi của giỏ vào
một lần gửi — khách không phải sửa một lỗi, gửi lại, rồi mới thấy lỗi kế.

Từ spec 2026-10-09 (giá theo Price List, §4.2) việc dựng đơn KHÔNG còn sinh
ba mã `vuot_han_muc` / `het_han_muc` / `thieu_gia`: hạn mức hợp đồng không
còn được kiểm, và mặt hàng chưa có giá thành dòng chờ báo giá chứ không phải
lỗi. Các bài riêng về ba mã đó đã xoá cùng hành vi; những bài chỉ MƯỢN
`vuot_han_muc` làm lỗi mẫu để kiểm phong bì thì chuyển sang `sai_boi_so`.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

USER_BVBM = "bvbm@demo.miyano"
VT = "VT0005"
HC = "HC0009"


def _rid() -> str:
    return frappe.generate_hash(length=12)


class TestPhongBiLoiCoCauTruc(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]
        # `FrappeTestCase` rollback một lần mỗi CLASS: ca nào khai bội số thì
        # ca sau vẫn thấy nó. Đặt lại về trạng thái XÁC ĐỊNH — VT không ràng
        # buộc, HC đặt theo bội số 10 (lỗi mẫu của file này).
        frappe.db.set_value("Item", VT, "custom_boi_so_dat", 0)
        frappe.db.set_value("Item", HC, "custom_boi_so_dat", 10)

    def _dat(self, dong, **kw):
        """Gọi order_place, trả về (mảng `loi`, văn xuôi). Xoá khoá `loi` cũ
        trước khi gọi: `frappe.local.response` sống qua nhiều lời gọi trong
        cùng một test, đọc phải rác của lần trước là kiểu dương tính giả tệ
        nhất — test xanh trong khi code không hề đặt gì."""
        frappe.local.response.pop("loi", None)
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(self.bo, json.dumps(dong), request_id=_rid(), **kw)
        return frappe.local.response.get("loi"), str(ctx.exception)

    # ---------- mã lý do ----------
    def test_sai_boi_so_kem_boi_so_va_goi_y(self):
        """TC-E1-03 — "417 `sai_boi_so`, gợi ý 20"."""
        loi, _ = self._dat([{"item_code": HC, "qty": 15}])
        self.assertEqual(loi[0]["ly_do"], "sai_boi_so")
        self.assertEqual(loi[0]["boi_so"], 10)
        self.assertEqual(loi[0]["goi_y"], 20)

    def test_ngay_giao_qua_khu_co_ma_rieng_khong_kem_item(self):
        """TC-E1-04 — mã `ngay_giao_khong_hop_le`. Lỗi của cả đơn nên không
        gắn `item_code`."""
        loi, _ = self._dat(
            [{"item_code": HC, "qty": 10}], delivery_date="2020-01-01"
        )
        ngay = [d for d in loi if d["ly_do"] == "ngay_giao_khong_hop_le"]
        self.assertEqual(len(ngay), 1)
        self.assertIsNone(ngay[0].get("item_code"))

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_loi_ngay_giao_va_loi_mat_hang_bao_cung_luc(self):
        """BR-O3 — lỗi của cả đơn và lỗi của một mặt hàng phải về CÙNG một
        lần gửi. (Lỗi mặt hàng mẫu trước đây là `vuot_han_muc`.)"""
        loi, _ = self._dat(
            [{"item_code": HC, "qty": 15}], delivery_date="2020-01-01"
        )
        self.assertEqual(
            {d["ly_do"] for d in loi}, {"ngay_giao_khong_hop_le", "sai_boi_so"}
        )

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_nhieu_mat_hang_loi_deu_duoc_liet_ke(self):
        """BR-O3 — ném ở mặt hàng lỗi đầu tiên là bắt khách đi từng vòng một.
        (Trước đây kiểm bằng hai mặt hàng `thieu_gia`.)"""
        frappe.db.set_value("Item", VT, "custom_boi_so_dat", 10)
        loi, _ = self._dat([
            {"item_code": VT, "qty": 15},
            {"item_code": HC, "qty": 15},
        ])
        self.assertEqual({d["item_code"] for d in loi}, {VT, HC})
        self.assertEqual({d["ly_do"] for d in loi}, {"sai_boi_so"})

    # ---------- không được đánh mất cái đang có ----------
    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_van_giu_thong_diep_trong_van_xuoi(self):
        """Thêm phong bì máy đọc KHÔNG được lấy đi câu chữ: `frappe.throw`
        vẫn phải mang đúng `thong_diep` của từng mục cho mọi nơi gọi không
        phải SPA (desk, script, integration cũ). (Trước đây kiểm bằng hai
        câu của `vuot_han_muc` và `thieu_gia`.)"""
        loi, van_xuoi = self._dat(
            [{"item_code": HC, "qty": 15}], delivery_date="2020-01-01"
        )
        self.assertEqual(len(loi), 2)
        for d in loi:
            self.assertIn(d["thong_diep"], van_xuoi)

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_moi_muc_loi_deu_co_thong_diep_rieng(self):
        """Client dịch từ `ly_do`, nhưng payload vẫn kèm `thong_diep` để chỗ
        nào chưa kịp cập nhật bảng dịch thì hiện chữ đúng thay vì mã trần."""
        loi, _ = self._dat([{"item_code": HC, "qty": 15}])
        self.assertTrue(loi[0]["thong_diep"])

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_don_hop_le_khong_de_lai_khoa_loi(self):
        """Đặt thành công mà `loi` còn sót lại từ lần trước thì giao diện sẽ
        báo lỗi trên một đơn vừa tạo xong."""
        self._dat([{"item_code": HC, "qty": 15}])
        self.assertTrue(frappe.local.response.get("loi"), "tiền đề: lần trước có để lại `loi`")
        kq = portal.portal_order_place(
            self.bo, json.dumps([{"item_code": HC, "qty": 20}]), request_id=_rid()
        )
        self.assertTrue(kq["sales_order"])
        self.assertIsNone(frappe.local.response.get("loi"))

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_vuot_so_luong_hop_dong_va_chua_co_gia_khong_con_la_loi(self):
        """Vế ngược của ba mã đã gỡ (§4.2): giỏ vừa đặt QUÁ số lượng còn lại
        trên hợp đồng, vừa có mặt hàng CHƯA có giá ở đâu cả — trước đây ra
        `vuot_han_muc` + `thieu_gia`, giờ đặt được, không có `loi`, và dòng
        chưa có giá là dòng chờ báo giá."""
        frappe.db.set_value(
            "Blanket Order Item", {"parent": self.bo, "item_code": VT},
            {"qty": 200, "ordered_qty": 195},  # hợp đồng chỉ còn 5
        )
        frappe.db.set_value(
            "Blanket Order Item", {"parent": self.bo, "item_code": HC}, "rate", 0
        )
        # Giá `<= 0` là "chưa có giá". Hạ về 0 chứ KHÔNG xoá dòng: HC0009 là
        # dữ liệu demo của site, và `seed_demo` chỉ tạo `Item Price` khi thiếu.
        for ten in frappe.get_all(
            "Item Price", filters={"item_code": HC, "selling": 1}, pluck="name"
        ):
            frappe.db.set_value("Item Price", ten, "price_list_rate", 0)
        frappe.local.response.pop("loi", None)
        kq = portal.portal_order_place(
            self.bo,
            json.dumps([{"item_code": VT, "qty": 10}, {"item_code": HC, "qty": 10}]),
            request_id=_rid(),
        )
        self.assertIsNone(frappe.local.response.get("loi"))
        # Đảo theo spec 2026-10-09 (giá theo Price List). §4.1 — giỏ trộn ra
        # HAI đơn: dòng có giá ở đơn đầu, dòng chờ báo giá ở đơn thứ hai.
        self.assertEqual(len(kq["don"]), 2)
        theo_ma = {
            d.item_code: d
            for don in kq["don"]
            for d in frappe.get_doc("Sales Order", don["sales_order"]).items
        }
        don_dau = frappe.get_doc("Sales Order", kq["sales_order"])
        self.assertEqual([d.item_code for d in don_dau.items], [VT])
        self.assertEqual(float(theo_ma[VT].qty), 10.0)
        self.assertEqual(theo_ma[HC].custom_nguon_gia, "Báo giá")
        self.assertEqual(float(theo_ma[HC].rate), 0.0)
