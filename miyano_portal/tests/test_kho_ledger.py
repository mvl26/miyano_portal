import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_kho_demo import seed_kho_demo
from miyano_portal.kho import ledger


class TestKhoWarehouse(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def test_seed_creates_one_warehouse_per_customer(self):
        # "per customer" nghĩa là CẢ HAI khách trong seed, không chỉ Bạch Mai:
        # bản trước chỉ assert kho_bm nên một seed quên hẳn PXN vẫn pass (minor
        # đã ghi nhận ở progress.md, Task 1).
        for kho_key, customer in (
            ("kho_bm", "Bệnh viện Bạch Mai"),
            ("kho_pxn", "PXN ABC"),
        ):
            with self.subTest(customer=customer):
                self.assertTrue(frappe.db.exists("Customer Warehouse", self.kho[kho_key]))
                self.assertEqual(
                    frappe.db.get_value(
                        "Customer Warehouse", self.kho[kho_key], "customer"
                    ),
                    customer,
                )
                self.assertEqual(
                    frappe.db.count("Customer Warehouse", {"customer": customer}), 1
                )

    def test_seed_is_idempotent(self):
        again = seed_kho_demo()
        self.assertEqual(again["kho_bm"], self.kho["kho_bm"])
        self.assertEqual(
            frappe.db.count("Customer Warehouse", {"customer": "Bệnh viện Bạch Mai"}), 1
        )

    def test_one_warehouse_per_customer_enforced(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse",
            "customer": "Bệnh viện Bạch Mai",
            "ten_kho": "Kho trùng",
            "ma_kho": "BM2",
            "ngay_bat_dau": "2026-01-01",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã có kho", str(ctx.exception))

    def _khach_chua_mo_kho(self) -> str:
        """Khách hàng dành riêng cho test, bảo đảm CHƯA có kho.

        Bản trước mượn khách thật "Himedic" và ngầm giả định khách đó chưa
        được mở kho. Ngày 2026-08-07 có người mở kho cho Himedic trên Desk,
        thế là test đổ: nó dừng ở luật "một khách một kho" trước khi kịp chạm
        tới phép kiểm mã kho mà nó muốn kiểm. Một khách mang tiền tố `_Test`
        không nằm trong luồng nghiệp vụ nên không ai mở kho cho nó, và bản
        ghi cũng bị rollback ở cuối class nên không tích tụ vào CSDL.
        """
        ten = "_Test Khách Chưa Mở Kho"
        if not frappe.db.exists("Customer", ten):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": ten,
                "customer_type": "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)
        return ten

    def test_ma_kho_unique_across_customers(self):
        khach = self._khach_chua_mo_kho()
        # Nêu thẳng tiền đề. Nếu ngày nào đó khách này có kho, test hỏng vì
        # lý do rõ ràng chứ không phải vì một thông điệp lỗi không liên quan.
        self.assertFalse(
            frappe.db.exists("Customer Warehouse", {"customer": khach}),
            f"Tiền đề sai: {khach} đã có kho — ca này cần một khách chưa mở kho.",
        )

        # "BM" là mã kho của Bạch Mai do seed dựng ở setUp.
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse",
            "customer": khach,
            "ten_kho": "Kho trùng mã",
            "ma_kho": "BM",
            "ngay_bat_dau": "2026-01-01",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        # Thông điệp này chỉ đến từ phép kiểm mã kho; luật "một khách một kho"
        # nói "đã có kho". Assert vào đúng câu là bằng chứng ta tới đúng chỗ.
        self.assertIn("đã được dùng", str(ctx.exception))


class TestKhoWarehouseItem(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def test_miyano_item_links_to_real_item(self):
        vt = frappe.get_doc("Customer Warehouse Item", self.kho["vt_bm"])
        self.assertEqual(vt.item_code, "MYN-GLOVE-M")
        self.assertEqual(vt.kho, self.kho["kho_bm"])

    def test_customer_private_code_has_no_item(self):
        vt = frappe.get_doc("Customer Warehouse Item", self.kho["vt_rieng_bm"])
        self.assertFalse(vt.item_code)
        self.assertFalse(frappe.db.exists("Item", "BM-GAC-01"))

    def test_duplicate_code_in_same_warehouse_blocked(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse Item",
            "kho": self.kho["kho_bm"],
            "ma_vat_tu": "BM-GAC-01",
            "ten_vat_tu": "Gạc trùng mã",
            "dvt": "Cái",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã tồn tại", str(ctx.exception))

    def test_same_code_allowed_in_different_warehouse(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse Item",
            "kho": self.kho["kho_pxn"],
            "ma_vat_tu": "BM-GAC-01",
            "ten_vat_tu": "Gạc của PXN",
            "dvt": "Cái",
        })
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)


class _FakeVoucher:
    """Đủ thuộc tính để post_lines dùng, không cần doctype thật ở task này."""

    def __init__(self, kho, ngay="2026-02-01", doctype="Customer Stock Receipt",
                 name="TEST-PN-001"):
        self.kho = kho
        self.ngay = ngay
        self.doctype = doctype
        self.name = name


class TestKhoLedger(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})

    def _nhap(self, so_luong, don_gia, so_lo="LO-A", han="2027-01-01", row="r1",
              name="TEST-PN-001"):
        v = _FakeVoucher(self.kho["kho_bm"], name=name)
        return ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "han_su_dung": han,
            "so_luong": so_luong, "don_gia": don_gia, "chung_tu_row": row,
        }])

    def test_receipt_creates_lot_balance(self):
        self._nhap(100, 50000)
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(bal["don_gia"], 50000)

    def test_issue_reduces_lot_balance(self):
        self._nhap(100, 50000)
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
            "so_luong": -30, "don_gia": 50000, "chung_tu_row": "r9",
        }])
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)
        # Xuất không đổi đơn giá của lô
        self.assertEqual(bal["don_gia"], 50000)

    def test_same_lot_twice_gives_weighted_average_price(self):
        self._nhap(100, 50000, row="r1", name="TEST-PN-001")
        self._nhap(100, 70000, row="r2", name="TEST-PN-002")
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 200)
        self.assertEqual(bal["don_gia"], 60000)

    def test_entry_records_signed_qty_and_value(self):
        self._nhap(100, 50000)
        entries = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"kho": self.kho["kho_bm"]},
            fields=["name", "so_luong", "gia_tri", "chung_tu"],
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["gia_tri"], 100 * 50000)

    def test_ledger_entry_cannot_be_edited(self):
        self._nhap(100, 50000)
        name = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}, "name"
        )
        doc = frappe.get_doc("Customer Stock Ledger Entry", name)
        doc.so_luong = 999
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.save(ignore_permissions=True)
        self.assertIn("Không được sửa", str(ctx.exception))
        # Không chỉ kiểm tra exception — phải chắc dữ liệu trong DB không bị
        # ghi đè trước khi guard ném lỗi (guard chạy ở before_save, trước
        # db_update()). Nếu guard tụt lại on_update thì dòng dưới sẽ fail vì
        # DB đã bị ghi 999 trước khi ValidationError được ném ra.
        self.assertEqual(
            frappe.db.get_value("Customer Stock Ledger Entry", name, "so_luong"), 100
        )

    def test_ledger_entry_cannot_be_deleted(self):
        self._nhap(100, 50000)
        name = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}, "name"
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            frappe.delete_doc("Customer Stock Ledger Entry", name, ignore_permissions=True)
        self.assertIn("Không được xoá", str(ctx.exception))

    def test_duplicate_row_is_not_posted_twice(self):
        self._nhap(100, 50000, row="r1")
        self._nhap(100, 50000, row="r1")
        self.assertEqual(
            frappe.db.count(
                "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}
            ),
            1,
        )

    def test_over_issue_is_rejected_and_not_posted(self):
        self._nhap(100, 50000)
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        with self.assertRaises(frappe.ValidationError) as ctx:
            ledger.post_lines(v, [{
                "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                "han_su_dung": "2027-01-01", "so_luong": -150, "don_gia": 50000,
                "chung_tu_row": "r9",
            }])
        self.assertIn("Không đủ tồn", str(ctx.exception))
        # Sổ append-only không xoá được: dòng xuất vượt tồn không được phép
        # tồn tại dù chỉ một khoảnh khắc, nên phải chặn TRƯỚC insert. Nếu guard
        # tụt sau insert, dòng này đã có mặt trong sổ tại đây.
        self.assertFalse(
            frappe.db.exists(
                "Customer Stock Ledger Entry",
                {"kho": self.kho["kho_bm"], "chung_tu": "TEST-PX-001"},
            )
        )
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)

    def test_mark_reversed_flags_entries(self):
        self._nhap(100, 50000)
        ledger.mark_reversed("Customer Stock Receipt", "TEST-PN-001")
        flags = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": "TEST-PN-001"}, pluck="da_dao",
        )
        self.assertTrue(flags)  # assertTrue(all([])) là True một cách vô nghĩa
        self.assertTrue(all(flags))

    def test_rebuild_recreates_one_row_per_lot_with_ledger_quantities(self):
        """FINDING I1 (review cuối) — tên cũ là `..._matches_ledger`, hứa nhiều
        hơn thân hàm.

        Test này KHÔNG so cache với sổ: nó chỉ kiểm rằng rebuild dựng lại đúng
        MỘT dòng cho mỗi lô có trong sổ, với đúng số lượng đã ghi. Bất biến
        giá trị thật sự (tổng `gia_tri` của sổ == `gia_tri` của cache) là hợp
        đồng của `TestKhoBatBienGiaTri` ở cuối file, nơi nó được khẳng định
        trên chứng từ thật ở từng bước vòng đời và cả sau rebuild — cố ý không
        nhân đôi ở đây.
        """
        self._nhap(100, 50000)
        self._nhap(50, 50000, so_lo="LO-B", han="2026-12-01", row="r2",
                   name="TEST-PN-002")
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        written = ledger.rebuild_lot_balance(self.kho["kho_bm"])
        self.assertEqual(written, 2)
        self.assertEqual(
            ledger.get_lot_balance(
                self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")["so_luong"], 100
        )
        self.assertEqual(
            ledger.get_lot_balance(
                self.kho["kho_bm"], self.kho["vt_bm"], "LO-B")["so_luong"], 50
        )

    def test_rebuild_reproduces_incremental_cache_with_mixed_price_and_issue(self):
        """FINDING I1 — tên cũ là `..._matches_ledger_with_...`, nhưng phép so
        ở đây là cache-tái-dựng vs cache-ghi-tuần-tự, KHÔNG phải cache vs sổ.

        Cái được chốt là tính XÁC ĐỊNH của rebuild: replay từ sổ phải cho ra
        đúng con số mà đường ghi tăng dần đã cho, kể cả don_gia bình quân gia
        quyền chứ không chỉ so_luong (hai lần nhập cùng lô khác giá cộng một
        lần xuất). Phép so cache-vs-sổ nằm ở `TestKhoBatBienGiaTri`.
        """
        self._nhap(100, 50000, row="r1", name="TEST-PN-001")
        self._nhap(100, 70000, row="r2", name="TEST-PN-002")
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
            "so_luong": -40, "don_gia": 60000, "chung_tu_row": "r9",
        }])
        incremental = ledger.get_lot_balance(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-A"
        )
        self.assertEqual(incremental["so_luong"], 160)
        self.assertEqual(incremental["don_gia"], 60000)

        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        ledger.rebuild_lot_balance(self.kho["kho_bm"])
        rebuilt = ledger.get_lot_balance(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-A"
        )
        self.assertEqual(rebuilt["so_luong"], incremental["so_luong"])
        self.assertEqual(rebuilt["don_gia"], incremental["don_gia"])

    def test_get_lot_balances_is_fefo_ordered(self):
        self._nhap(10, 1000, so_lo="LO-XA", han="2028-01-01", row="r1",
                   name="TEST-PN-001")
        self._nhap(10, 1000, so_lo="LO-GAN", han="2026-09-01", row="r2",
                   name="TEST-PN-002")
        self._nhap(10, 1000, so_lo=ledger.LOT_KHONG_CO, han=None, row="r3",
                   name="TEST-PN-003")
        lots = ledger.get_lot_balances(self.kho["kho_bm"], self.kho["vt_bm"])
        self.assertEqual([l["so_lo"] for l in lots],
                         ["LO-GAN", "LO-XA", ledger.LOT_KHONG_CO])

    def test_zero_balance_lot_excluded_from_fefo(self):
        self._nhap(10, 1000, so_lo="LO-HET", han="2026-09-01")
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-HET",
            "han_su_dung": "2026-09-01", "so_luong": -10, "don_gia": 1000,
            "chung_tu_row": "r9",
        }])
        lots = ledger.get_lot_balances(self.kho["kho_bm"], self.kho["vt_bm"])
        self.assertEqual(lots, [])


# Dung sai khi so tổng `gia_tri` của sổ với `gia_tri` của cache. Cả hai cột đều
# là Currency, lưu trong `decimal(21,9)`, nên sai lệch duy nhất có thể xảy ra là
# rác dấu phẩy động ở hàng phần tỷ khi đơn giá bình quân là số vô hạn tuần hoàn
# (ví dụ 10.500.000 / 170 = 61764,705882...). Một xu là quá đủ để nuốt sai số đó
# mà vẫn nhỏ hơn 8 bậc so với mức lệch 1.000.000 mà FINDING C1 gây ra.
DUNG_SAI = 0.01


class TestKhoBatBienGiaTri(FrappeTestCase):
    """BẤT BIẾN GIÁ TRỊ — thiết kế mục 3 bắt buộc phải có test này.

    Với mọi lô: tổng `gia_tri` của các dòng `Customer Stock Ledger Entry` luôn
    bằng `gia_tri` của `Customer Stock Lot Balance`, kể cả sau khi huỷ phiếu và
    sau khi rebuild.

    Vì sao nó phải chạy trên CHỨNG TỪ THẬT chứ không phải `_FakeVoucher`: hai
    bước cuối là huỷ phiếu, và cái làm cho phép thử có ý nghĩa chính là
    `_tao_phieu_dao()` copy `don_gia` từ dòng gốc cộng với cờ `dang_tao_dao`
    chặn việc đọc lại giá từ lô. Tự tay post một dòng âm giá 50.000 qua
    `post_lines()` là mô phỏng kết quả, không chứng minh được controller làm
    đúng.

    GIỚI HẠN ĐÃ BIẾT của bất biến này: xem
    test_lo_ve_khong_khong_giu_duoc_gia_tri_du.
    """

    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        self.VT = self.kho["vt_bm"]
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})

    def _tong_so(self, so_lo):
        """Tổng `gia_tri` ĐÃ LƯU của các dòng sổ cho một lô.

        Cố ý đọc cột đã ghi xuống DB chứ không tính lại trong Python: cache là
        thứ `api/kho.py` cộng ra để trả cho khách, nên phép so sánh phải là
        giữa hai giá trị THẬT đang nằm trong database.
        """
        rows = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"kho": self.K, "vat_tu": self.VT, "so_lo": so_lo},
            pluck="gia_tri",
        )
        return sum(float(r or 0) for r in rows)

    def _cache(self, so_lo):
        return frappe.db.get_value(
            "Customer Stock Lot Balance",
            {"kho": self.K, "vat_tu": self.VT, "so_lo": so_lo},
            ["so_luong", "don_gia", "gia_tri"],
            as_dict=True,
        )

    def _assert_bat_bien(self, buoc, so_lo="LO-A", so_luong=None, don_gia=None):
        so = self._tong_so(so_lo)
        cache = self._cache(so_lo)
        self.assertIsNotNone(cache, f"{buoc}: không có dòng tồn theo lô cho {so_lo}")
        # Không rẽ nhánh, không bỏ qua: bất biến được khẳng định vô điều kiện ở
        # mọi bước. Kịch bản dưới đây không bao giờ đưa tồn về 0 nên nhánh
        # so_luong == 0 (xem giới hạn đã biết) không đụng tới ở đây.
        self.assertAlmostEqual(
            float(cache.gia_tri), so, delta=DUNG_SAI,
            msg=(f"{buoc}: cache gia_tri={cache.gia_tri!r} "
                 f"(so_luong={cache.so_luong!r} x don_gia={cache.don_gia!r}) "
                 f"nhưng tổng sổ={so!r}"),
        )
        if so_luong is not None:
            self.assertAlmostEqual(float(cache.so_luong), so_luong, delta=DUNG_SAI,
                                   msg=f"{buoc}: số lượng")
        if don_gia is not None:
            self.assertAlmostEqual(float(cache.don_gia), don_gia, delta=DUNG_SAI,
                                   msg=f"{buoc}: đơn giá")

    def _nhap(self, so_luong, don_gia, so_lo="LO-A", han="2027-01-01"):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.K, "ngay": "2026-02-01", "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": [{"vat_tu": self.VT, "so_lo": so_lo, "han_su_dung": han,
                       "so_luong": so_luong, "don_gia": don_gia}],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _xuat(self, so_luong, so_lo="LO-A"):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.K, "ngay": "2026-03-01", "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa test", "nguoi_nhan": "Nhân viên test",
            "items": [{"vat_tu": self.VT, "so_lo": so_lo, "so_luong": so_luong}],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def test_vong_doi_lo_tron_gia_giu_nguyen_bat_bien_gia_tri(self):
        """FINDING C1. Vòng đời năm bước trên một lô có hai mức giá.

        Trước khi sửa, bước 5 (huỷ phiếu nhập giá thấp) để cache đứng ở
        100 x 60.000 = 6.000.000 trong khi sổ đã về 7.000.000 — lệch 1.000.000
        vĩnh viễn, và rebuild lặp lại y nguyên phép tính sai nên không cứu được.
        """
        pn1 = self._nhap(100, 50000)
        self._assert_bat_bien("B1 nhập 100@50k", so_luong=100, don_gia=50000)

        px = self._xuat(30)
        self._assert_bat_bien("B2 xuất 30", so_luong=70, don_gia=50000)

        pn2 = self._nhap(100, 70000)
        self._assert_bat_bien("B3 nhập 100@70k", so_luong=170,
                              don_gia=10500000 / 170)

        px.cancel()
        self._assert_bat_bien("B4 huỷ phiếu xuất", so_luong=200, don_gia=60000)

        # Bước quyết định: dòng đảo mang đơn giá GỐC 50.000, khác hẳn bình quân
        # hiện hành 60.000. Đây là trường hợp duy nhất mà việc tính lại bình
        # quân trên delta âm có tác dụng thật.
        pn1.reload()
        pn1.cancel()
        self._assert_bat_bien("B5 huỷ phiếu nhập 100@50k",
                              so_luong=100, don_gia=70000)
        self.assertAlmostEqual(self._tong_so("LO-A"), 7000000, delta=DUNG_SAI)

        # rebuild replay thẳng từ sổ: bất biến phải vẫn đúng, và phải cho ra
        # đúng con số của đường ghi tuần tự.
        ledger.rebuild_lot_balance(self.K)
        self._assert_bat_bien("sau rebuild", so_luong=100, don_gia=70000)
        self.assertEqual(pn2.docstatus, 1)

    def test_xuat_thuong_khong_lam_doi_don_gia_lo(self):
        """Tính lại bình quân trên delta ÂM phải là no-op với phiếu xuất thường.

        Phiếu xuất luôn mang đúng đơn giá bình quân hiện hành của lô
        (`_lay_gia_va_han_tu_lo`), nên (Q·P − q·P)/(Q−q) = P. Chứng minh bằng
        số trên một lô đã có bình quân LẺ, không phải bằng lập luận: nếu ai đó
        sau này "đơn giản hoá" nhánh delta < 0 đi, test C1 ở trên đỏ; nếu ai đó
        làm nhánh đó tính sai, test này đỏ.
        """
        self._nhap(100, 50000)
        self._nhap(100, 70000)
        truoc = self._cache("LO-A")
        self.assertAlmostEqual(float(truoc.don_gia), 60000, delta=DUNG_SAI)

        self._xuat(37)
        sau = self._cache("LO-A")
        self.assertAlmostEqual(float(sau.so_luong), 163, delta=DUNG_SAI)
        self.assertAlmostEqual(float(sau.don_gia), float(truoc.don_gia),
                               delta=DUNG_SAI, msg="xuất thường đã đổi đơn giá lô")
        self._assert_bat_bien("sau xuất thường")

        # Lặp lại với bình quân là số vô hạn tuần hoàn, nơi một công thức sai
        # sẽ lộ ra ngay: 10.500.000 / 170 = 61764,705882...
        self._nhap(7, 90000, so_lo="LO-LE")
        self._nhap(6, 40000, so_lo="LO-LE")
        truoc_le = self._cache("LO-LE")
        self._xuat(5, so_lo="LO-LE")
        sau_le = self._cache("LO-LE")
        self.assertAlmostEqual(float(sau_le.don_gia), float(truoc_le.don_gia),
                               delta=DUNG_SAI)
        self._assert_bat_bien("lô lẻ sau xuất thường", so_lo="LO-LE")

    def test_lo_ve_khong_khong_giu_duoc_gia_tri_du(self):
        """GIỚI HẠN ĐÃ BIẾT, có chủ ý — không phải bất biến bị vi phạm ngầm.

        `gia_tri` của cache được lưu dưới dạng `so_luong x don_gia`, nên khi
        `so_luong` về 0 thì `gia_tri` buộc phải là 0, bất kể sổ cộng ra bao
        nhiêu. Tồn tại đúng một cách chạm tới: huỷ một phiếu nhập mà toàn bộ
        phần còn lại của lô vừa đúng bằng lượng đã nhập, trong khi lô đã bị
        pha giá bởi một lần nhập khác giá.

        Test này CHỐT hiện trạng đó lại thành văn bản thay vì để nó là một bất
        ngờ: cache về 0 (nên lô biến mất khỏi mọi báo cáo, `api/kho.py` lọc
        `so_luong > EPS`), còn sổ giữ phần chênh. Nếu sau này mô hình đổi sang
        lưu `gia_tri` độc lập với `so_luong x don_gia`, test này đỏ và đó là
        tín hiệu ĐÚNG để cập nhật lại nó.
        """
        pn1 = self._nhap(100, 50000)
        self._nhap(100, 70000)
        self._xuat(100)          # xuất theo bình quân 60.000
        self._assert_bat_bien("trước khi huỷ", so_luong=100, don_gia=60000)

        pn1.cancel()             # đảo -100 @ 50.000 -> tồn về đúng 0
        cache = self._cache("LO-A")
        self.assertAlmostEqual(float(cache.so_luong), 0, delta=DUNG_SAI)
        self.assertAlmostEqual(float(cache.gia_tri), 0, delta=DUNG_SAI)
        # Đơn giá GIỮ NGUYÊN giá trị trước đó (nhánh chống chia cho 0), không
        # bị đặt về 0 và không làm nổ ZeroDivisionError.
        self.assertAlmostEqual(float(cache.don_gia), 60000, delta=DUNG_SAI)
        # Phần chênh nằm lại ở sổ — ghi nhận tường minh, không giả vờ là 0.
        self.assertAlmostEqual(self._tong_so("LO-A"), 1000000, delta=DUNG_SAI)


class TestKhoReplayVouchersIntoLedger(FrappeTestCase):
    """`replay_vouchers_into_ledger()` — bổ sung cho `rebuild_lot_balance()`:
    dựng lại chính SỔ (không chỉ cache tồn) từ các phiếu đã submit, dùng khi
    sổ bị mất nhưng chứng từ nguồn còn nguyên vẹn. Xem docstring của hàm.

    Dùng một Customer/Warehouse RIÊNG cho lớp này, KHÔNG dùng kho_bm/kho_pxn
    của seed_kho_demo(): hai kho đó đã tích luỹ dữ liệu thật xuyên suốt nhiều
    lần chạy test trên site này (kho_bm có sẵn nhiều phiếu thật ngoài phạm vi
    test), nên đếm `len(created)` trên chúng sẽ lẫn cả dữ liệu không do chính
    test này tạo ra. Bài học rút ra từ chính sự cố mất sổ đã xảy ra khi viết
    file này — xem báo cáo p6-desk-report.md."""

    def setUp(self):
        customer = "Replay Ledger Test Co"
        if not frappe.db.exists("Customer", customer):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": customer,
                "customer_type": "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)

        self.K = frappe.db.get_value("Customer Warehouse", {"customer": customer}, "name")
        if not self.K:
            kho_doc = frappe.get_doc({
                "doctype": "Customer Warehouse",
                "customer": customer,
                "ten_kho": "Kho test replay",
                "ma_kho": "RPL",
                "ngay_bat_dau": "2026-01-01",
            })
            kho_doc.insert(ignore_permissions=True)
            self.K = kho_doc.name

        self.VT = frappe.db.get_value("Customer Warehouse Item", {"kho": self.K, "ma_vat_tu": "RPL-01"}, "name")
        if not self.VT:
            vt_doc = frappe.get_doc({
                "doctype": "Customer Warehouse Item",
                "kho": self.K, "ma_vat_tu": "RPL-01", "ten_vat_tu": "Vật tư test replay", "dvt": "Cái",
            })
            vt_doc.insert(ignore_permissions=True)
            self.VT = vt_doc.name

        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})

    def _nhap_doc(self, so_luong, don_gia, so_lo="LO-A", ngay="2026-02-01"):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.K, "ngay": ngay, "loai_nhap": "Nhập khác",
            "nguoi_giao": "Test",
            "items": [{
                "vat_tu": self.VT, "so_lo": so_lo, "han_su_dung": "2030-01-01",
                "so_luong": so_luong, "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _xuat_doc(self, so_luong, so_lo="LO-A", ngay="2026-03-01"):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.K, "ngay": ngay, "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Test", "nguoi_nhan": "Test",
            "items": [{"vat_tu": self.VT, "so_lo": so_lo, "so_luong": so_luong}],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def test_rebuilds_ledger_and_lot_balance_from_existing_vouchers(self):
        """Đếm theo `so_lo` RIÊNG của test này, không theo tổng `len(created)`
        toàn kho: FrappeTestCase chỉ rollback cuối CLASS, nên các phiếu do
        CÁC TEST KHÁC trong cùng lớp tạo ra vẫn còn nguyên khi test này chạy
        — `so_lo` riêng cách ly khỏi điều đó, đếm tổng thì không."""
        so_lo = "LO-REBUILD"
        self._nhap_doc(100, 50000, so_lo=so_lo)
        self._xuat_doc(30, so_lo=so_lo)

        # Mô phỏng đúng sự cố: sổ và cache bị xoá sạch nhưng PHIẾU vẫn còn.
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})
        self.assertEqual(frappe.db.count("Customer Stock Ledger Entry", {"kho": self.K}), 0)

        ledger.replay_vouchers_into_ledger(kho=self.K)

        entries = frappe.get_all(
            "Customer Stock Ledger Entry", filters={"kho": self.K, "so_lo": so_lo}, fields=["name"]
        )
        self.assertEqual(len(entries), 2, "phải ghi lại đúng 2 dòng của LÔ NÀY: 1 nhập + 1 xuất")

        bal = ledger.get_lot_balance(self.K, self.VT, so_lo)
        self.assertEqual(bal["so_luong"], 70)
        self.assertEqual(bal["don_gia"], 50000)

    def test_calling_twice_creates_nothing_new(self):
        so_lo = "LO-TWICE"
        self._nhap_doc(40, 20000, so_lo=so_lo)
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})

        ledger.replay_vouchers_into_ledger(kho=self.K)
        after_first = frappe.db.count("Customer Stock Ledger Entry", {"kho": self.K, "so_lo": so_lo})
        self.assertEqual(after_first, 1)

        ledger.replay_vouchers_into_ledger(kho=self.K)
        after_second = frappe.db.count("Customer Stock Ledger Entry", {"kho": self.K, "so_lo": so_lo})
        self.assertEqual(
            after_second, 1,
            "chung_tu_row đã có dòng sổ -> gọi lại không được ghi thêm cho lô này",
        )

    def test_cancelled_receipt_original_line_is_replayed_and_marked_reversed(self):
        """Phiếu bị huỷ vẫn phải có dòng GỐC trong sổ (chỉ đánh dấu da_dao=1),
        và phiếu đảo tự sinh khi huỷ cũng phải được replay — cả hai đều là
        Customer Stock Receipt thật trong DB, thứ tự tên đảm bảo dòng gốc
        được ghi trước dòng đảo."""
        pn = self._nhap_doc(20, 10000, so_lo="LO-HUY")
        pn.reload()
        pn.cancel()  # sinh phiếu đảo, tồn về 0

        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})

        ledger.replay_vouchers_into_ledger(kho=self.K)

        entries = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"kho": self.K, "so_lo": "LO-HUY"},
            fields=["so_luong", "da_dao", "chung_tu"],
            order_by="creation asc",
        )
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["so_luong"], 20)
        self.assertEqual(entries[0]["da_dao"], 1, "dòng gốc phải được đánh dấu đã đảo")
        self.assertEqual(entries[1]["so_luong"], -20)
        self.assertEqual(entries[1]["da_dao"], 0)

        bal = ledger.get_lot_balance(self.K, self.VT, "LO-HUY")
        self.assertAlmostEqual(float(bal["so_luong"]), 0, delta=ledger.EPS)
