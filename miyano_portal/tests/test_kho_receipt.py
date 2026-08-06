import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import ledger, voucher
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestPhieuNhap(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})

    def _phieu(self, so_luong=100, don_gia=50000, so_lo="LO-A", ngay="2026-02-01",
               vat_tu=None, items=None):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"],
            "ngay": ngay,
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": items or [{
                "vat_tu": vat_tu or self.kho["vt_bm"],
                "so_lo": so_lo,
                "han_su_dung": "2027-01-01",
                "so_luong": so_luong,
                "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        return doc

    def _xuat(self, so_luong, so_lo="LO-A", chung_tu_row="r9", chung_tu="TEST-PX-001"):
        """Giả lập một phiếu xuất bằng cách ghi thẳng vào sổ qua ledger.post_lines.

        Customer Stock Issue (Task 5) chưa tồn tại trong app tại thời điểm viết
        test này; dùng frappe._dict làm "voucher" giả, cùng cách test_kho_ledger.py
        đã làm với _FakeVoucher.
        """
        v = frappe._dict(
            kho=self.kho["kho_bm"], ngay="2026-02-05",
            doctype="Customer Stock Issue", name=chung_tu,
        )
        return ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "han_su_dung": "2027-01-01",
            "so_luong": -so_luong, "don_gia": 50000, "chung_tu_row": chung_tu_row,
        }])

    def test_naming_uses_warehouse_code_and_year(self):
        doc = self._phieu()
        self.assertTrue(doc.name.startswith("PN-BM-2026-"), doc.name)

    def test_draft_does_not_touch_ledger(self):
        self._phieu()
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 0
        )

    def test_submit_posts_ledger_and_balance(self):
        doc = self._phieu()
        doc.submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(doc.tong_tien, 100 * 50000)

    def test_totals_computed_on_validate(self):
        doc = self._phieu(so_luong=3, don_gia=1500)
        self.assertEqual(doc.items[0].thanh_tien, 4500)
        self.assertEqual(doc.tong_tien, 4500)
        self.assertEqual(doc.items[0].ten_vat_tu, "Găng tay y tế size M")

    def test_zero_qty_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(so_luong=0)
        self.assertIn("lớn hơn 0", str(ctx.exception))

    def test_negative_price_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(don_gia=-1)
        self.assertIn("không được âm", str(ctx.exception))

    def test_date_before_warehouse_start_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(ngay="2025-12-31")
        self.assertIn("Ngày bắt đầu quản lý", str(ctx.exception))

    def test_item_from_other_warehouse_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(vat_tu=self.kho["vt_pxn"])
        self.assertIn("không thuộc kho", str(ctx.exception))

    # -- FINDING 1: chặn tự tạo phiếu loại "Phiếu đảo" -----------------------

    def test_manual_phieu_dao_creation_blocked(self):
        """Người dùng không được tự chọn "Phiếu đảo" từ dropdown loai_nhap.

        Nếu lọt qua: _he_so_dau() ghi số lượng ÂM vào sổ (rút kho), và
        block_cancel_of_reversal khiến phiếu không bao giờ huỷ được nữa.
        """
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"],
            "ngay": "2026-02-01",
            "loai_nhap": voucher.LOAI_DAO,
            "items": [{
                "vat_tu": self.kho["vt_bm"],
                "so_lo": "LO-A",
                "han_su_dung": "2027-01-01",
                "so_luong": 100,
                "don_gia": 50000,
            }],
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("Phiếu đảo", str(ctx.exception))
        # Không được ghi gì vào sổ dù có lỡ lọt qua validate theo cách khác
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 0
        )

    def test_manual_phieu_dao_with_forged_phieu_goc_blocked(self):
        """Bản trước của guard chấp nhận `or self.phieu_goc`, và phieu_goc là
        Data thường (finding 2) nên ai cũng ghi được chuỗi bất kỳ vào đó.
        Đây chính là bypass mà round review đã tái hiện: seed 100 đơn vị LO-A
        rồi tạo tay một "Phiếu đảo" với phieu_goc giả để lách guard, kéo tồn
        về 0 mà không hề huỷ phiếu gốc nào — và phiếu tạo ra lại vĩnh viễn
        không huỷ được. Guard đúng chỉ dựa vào self.flags.dang_tao_dao, không
        bao giờ dựa vào giá trị của một field ghi được từ bên ngoài.
        """
        self._phieu(so_luong=100, so_lo="LO-A").submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)

        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"],
            "ngay": "2026-02-01",
            "loai_nhap": voucher.LOAI_DAO,
            "phieu_goc": "FAKE-DOES-NOT-EXIST",
            "items": [{
                "vat_tu": self.kho["vt_bm"],
                "so_lo": "LO-A",
                "han_su_dung": "2027-01-01",
                "so_luong": 100,
                "don_gia": 50000,
            }],
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("Phiếu đảo", str(ctx.exception))
        # Tồn không được đụng tới: nếu bypass lọt qua, dòng dưới sẽ thấy 0
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)

    def test_cancel_creates_reversal_and_keeps_ledger(self):
        doc = self._phieu()
        doc.submit()
        doc.cancel()

        dao = frappe.get_all(
            "Customer Stock Receipt",
            filters={"phieu_goc": doc.name, "loai_nhap": "Phiếu đảo"},
            fields=["name", "docstatus"],
        )
        self.assertEqual(len(dao), 1)
        self.assertEqual(dao[0]["docstatus"], 1)

        # Sổ giữ nguyên dòng gốc, cộng thêm dòng đảo -> tồn về 0
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 2
        )
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 0)

        # FINDING 6: assertTrue(all(...)) trên danh sách rỗng là True một cách
        # vô nghĩa — phải khẳng định danh sách không rỗng TRƯỚC, và lọc đúng
        # chung_tu_type để không vô tình khớp một chứng từ khác trùng tên.
        da_dao_flags = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": doc.name, "chung_tu_type": doc.doctype},
            pluck="da_dao",
        )
        self.assertTrue(da_dao_flags)
        self.assertTrue(all(da_dao_flags))

    def test_reversal_voucher_cannot_be_cancelled(self):
        doc = self._phieu()
        doc.submit()
        doc.cancel()
        dao_name = frappe.db.get_value(
            "Customer Stock Receipt", {"phieu_goc": doc.name}, "name"
        )
        dao = frappe.get_doc("Customer Stock Receipt", dao_name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            dao.cancel()
        self.assertIn("phiếu đảo", str(ctx.exception).lower())
        # FINDING 5: trước khi guard chuyển sang before_cancel, assertion này
        # FAIL — guard nằm ở on_cancel, chạy sau db_update(), nên dòng vẫn bị
        # ghi docstatus=2 trong DB dù exception đã ném ra. Sau khi guard
        # chuyển sang before_cancel (chạy trước db_update()), assertion này
        # PASS. Sự tương phản đó chính là bằng chứng cho fix của Finding 4.
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", dao_name, "docstatus"), 1
        )

    # -- FINDING 3: cộng dồn theo lô trước khi so với tồn ---------------------

    def test_cancel_blocked_when_two_rows_same_lot_partially_issued(self):
        """Một phiếu có HAI dòng cùng lô (giá khác nhau); phần lô đó đã bị
        xuất một phần. Guard so từng dòng riêng lẻ với tồn sẽ cho cả hai dòng
        "đủ" (vì chưa dòng nào bị trừ lúc so sánh), rồi post_lines() ghi dòng
        đảo thứ nhất thành công, dòng thứ hai mới vỡ ở ledger — để lại một
        phiếu đảo ghi dở dang. Guard đúng phải cộng dồn theo lô trước khi so.
        """
        doc = self._phieu(items=[
            {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
             "so_luong": 60, "don_gia": 50000},
            {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
             "so_luong": 60, "don_gia": 60000},
        ])
        doc.submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 120)

        self._xuat(50)  # tồn còn 70, ít hơn 120 đã nhập trên phiếu này
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)

        so_dong_truoc = frappe.db.count(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}
        )

        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.cancel()
        self.assertIn("Không thể huỷ", str(ctx.exception))

        # Không ghi nửa chừng: không có dòng sổ đảo nào (dù chỉ một) được thêm
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}),
            so_dong_truoc,
        )
        # Và phiếu KHÔNG thật sự bị huỷ trong DB — guard chạy ở before_cancel
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", doc.name, "docstatus"), 1
        )
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)


class TestNextVoucherName(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Receipt", {"kho": self.kho["kho_bm"]})

    def _phieu(self, so_lo):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"],
            "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "items": [{
                "vat_tu": self.kho["vt_bm"],
                "so_lo": so_lo,
                "han_su_dung": "2027-01-01",
                "so_luong": 10,
                "don_gia": 1000,
            }],
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_rejects_doctype_outside_whitelist(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            voucher.next_voucher_name(
                "PN", "Sales Invoice", self.kho["kho_bm"], "2026-02-01"
            )
        self.assertIn("không hợp lệ", str(ctx.exception))

    def test_counter_increments_within_same_warehouse_and_year(self):
        first = self._phieu("LO-A")
        second = self._phieu("LO-B")
        self.assertTrue(first.name.endswith("-00001"), first.name)
        self.assertTrue(second.name.endswith("-00002"), second.name)
