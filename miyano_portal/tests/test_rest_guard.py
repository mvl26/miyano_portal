"""NG-37c — chặn REST resource/document cho doctype con của chứng từ bán hàng.

Xem docstring dài ở đầu `miyano_portal/search_guard.py` (mục "Phạm vi CHƯA
đóng — hai trục khác") và `.superpowers/sdd/2026-08-12-dot-1-chan-mau-P0/
task-1c-brief.md` cho lý do NG-37b (`override_whitelisted_methods`) không
đóng được lỗ này: `/api/resource/<doctype>` (v1) và `/api/v2/document/
<doctype>` (v2) gọi thẳng `frappe.client.get_list`/`frappe.client.get` BẰNG
THAM CHIẾU HÀM Python (`frappe/api/v1.py::document_list`,
`frappe/api/v2.py::document_list`), không đi qua bảng tra tên
`frappe.override_whitelisted_method()` — nên wrapper `search_guard.
client_get_list`/`client_get` (đã whitelist bằng CHUỖI TÊN) không bao giờ
được gọi tới trên route này, bất kể doctype gì.

ĐIỂM KHÁC BIỆT QUAN TRỌNG so với `test_client_guard.py`: lỗ nằm ở TẦNG ĐỊNH
TUYẾN HTTP (`frappe/app.py::init_request()` → `frappe.api.handle()`), nên
gọi thẳng hàm Python trong tiến trình test (kiểu `client_get_list(...)`)
KHÔNG chạm tới nó và sẽ pass vô nghĩa. Các test dưới đây dùng HTTP THẬT
(`requests`) tới bench đang chạy trên bench này
(`http://127.0.0.1:8002`, xác nhận bằng `Procfile` + `sites/
common_site_config.json::webserver_port` + `ss -tlnp`, cùng cổng
`task-1b-report.md` đã dùng), với header `Host: erptest.local` (site name),
đăng nhập thật bằng `bvbm@demo.miyano` / `DEMO_PASSWORD` qua
`/api/method/login`, rồi GET cả ba prefix REST × cả hai dạng
(`?parent=`/`?filters=` không kèm `<name>`, và kèm `<name>`).

Dữ liệu dùng để probe là dữ liệu THẬT đã có sẵn trên `erptest.local` (đọc
bằng `frappe.get_all`, hàm luôn bỏ qua quyền, TRƯỚC khi gọi HTTP — không tạo
mới, không ghi gì) — không dùng đơn nháp tự tạo trong `setUp()`: những đơn đó
nằm trong transaction/savepoint riêng của `FrappeTestCase`
(`bench run-tests`), một tiến trình DB connection khác hẳn tiến trình
gunicorn đang phục vụ HTTP thật, nên dữ liệu CHƯA COMMIT sẽ vô hình với
server — dùng nó sẽ khiến test luôn thấy `[]` bất kể guard có hoạt động hay
không, che mất cả RED lẫn GREEN thật.

**Ca bắt buộc theo brief**: `Payment Schedule` với
`fields=["parent","parenttype","payment_amount","outstanding"]` — đây là
doctype đã lật tẩy bản vá fail-open liệt kê tên của Task 1b (round 1); nếu
chỉ probe ba doctype Item quen thuộc (SO/DN/SI Item) thì một bản vá theo
danh sách tên NG-37c mới (nếu ai đó lặp lại sai lầm round 1) vẫn có thể pass.

Hành vi ĐÚNG sau fix (Step 3 của brief, port từ `supplycore.utils.
permissions.portal_block_rest_child`): CHẶN THẲNG, không lọc theo hàng —
mọi GET REST (dạng list lẫn dạng `<name>` đơn lẻ) trên MỘT doctype con
(`frappe.is_table(doctype)` đúng) đều bị `before_request` ném
`frappe.PermissionError` (HTTP 403) cho Website User, KỂ CẢ khi hàng đó là
của chính khách gọi — cổng có API riêng cho nhu cầu đọc chính đáng, không
cần REST child. Vì vậy assertion GREEN là "403 + không có trường `data`
mang dòng nào", không phải "403 chỉ với dòng của khách khác".

Nếu bench không chạy ở cổng đã xác nhận, hoặc network loopback bị chặn
trong môi trường CI, mọi test ở đây `skipTest()` với lý do rõ ràng — nhưng
trên bench đang dùng (`erptest.local`, gunicorn cổng 8002), cả RED lẫn GREEN
đã được xác minh bằng curl thủ công, trích verbatim trong
`task-1c-report.md`.
"""

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from miyano_portal.setup.seed_demo import DEMO_PASSWORD, seed_demo
from miyano_portal.tests.test_search_guard import BVBM, USER_BVBM, USER_SALES

# Xác nhận bằng `cat Procfile` ("web: bench serve --port 8002"),
# `sites/common_site_config.json::webserver_port` (8002), và `ss -tlnp`
# (gunicorn đang LISTEN 127.0.0.1:8002) — cùng cổng `task-1b-report.md` đã
# dùng cho probe HTTP thật của Task 1b.
BASE_URL = "http://127.0.0.1:8002"
SITE = "erptest.local"

# Ba prefix REST phải phủ (v1 có hai submount cùng url_rules, xem
# frappe/api/__init__.py) — giữ đúng thứ tự/nội dung với
# `rest_guard._REST_CHILD_PREFIXES` để hai bên không lệch nhau.
_PREFIXES = ("/api/resource/", "/api/v1/resource/", "/api/v2/document/")


def _login_bvbm() -> requests.Session | None:
    """Đăng nhập thật qua HTTP, trả về session đã có cookie `sid`, hoặc
    None nếu bench không phản hồi (môi trường chặn loopback) — caller phải
    `skipTest()` khi None, không được coi None là "không rò rỉ".

    Vì sao thử hai lần với thời gian chờ nới dần: bản trước chỉ bắt
    `ConnectionError` và chờ 5 giây. Nhưng khi chạy TOÀN SUITE, bench đang bận
    xử lý chính các test khác nên lần đăng nhập này thường xuyên quá 5 giây, và
    `ReadTimeout` là nhánh anh em của `ConnectionError` chứ không phải lớp con
    — nên nó lọt qua `except`, `setUp` ném, và cả lớp test đỏ vì lý do không
    liên quan gì tới cái đang kiểm. Đã đỏ hai lần theo đúng kiểu đó.

    Thử lại một lần với hạn chờ dài hơn giữ được ĐỘ PHỦ trong trường hợp
    thường gặp (bench chỉ chậm, không chết). Chỉ khi cả hai lần đều hỏng mới
    trả None để caller `skipTest` — bỏ qua có ghi nhận, không phải xanh giả.
    """
    session = requests.Session()
    session.headers.update({"Host": SITE})
    for han_cho in (5, 30):
        try:
            resp = session.post(
                f"{BASE_URL}/api/method/login",
                json={"usr": USER_BVBM, "pwd": DEMO_PASSWORD},
                timeout=han_cho,
            )
        except requests.exceptions.RequestException:
            continue
        if resp.status_code == 200:
            return session
        return None
    return None


class TestRestGuardChanDoctypeCon(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.session = _login_bvbm()
        if self.session is None:
            self.skipTest(
                f"Không đăng nhập được qua HTTP thật tới {BASE_URL} (Host: "
                f"{SITE}) — kiểm bench có đang `bench serve --port 8002` "
                "không. Test này BẮT BUỘC đi qua HTTP thật vì lỗ nằm ở tầng "
                "định tuyến, gọi hàm Python trong tiến trình không chạm "
                "tới nó."
            )

        # Dữ liệu THẬT đã commit sẵn trên site — không tạo mới trong test.
        don_khach_khac = frappe.get_all(
            "Sales Order",
            filters={"customer": ["!=", BVBM]},
            limit=1,
            pluck="name",
        )
        if not don_khach_khac:
            self.skipTest(
                "Không có Sales Order thật của khách KHÁC Bệnh viện Bạch "
                "Mai trên site để probe cross-customer — cần dữ liệu demo "
                "rộng hơn (đã có nhiều khách khác trên erptest.local tại "
                "thời điểm viết test, xem task-1c-report.md)."
            )
        self.don_khach_khac = don_khach_khac[0]
        dong_khach_khac = frappe.get_all(
            "Sales Order Item",
            filters={"parent": self.don_khach_khac},
            limit=1,
            fields=["name", "parent"],
        )
        self.assertTrue(
            dong_khach_khac, "Sales Order thật lại không có dòng hàng nào?"
        )
        self.dong_khach_khac = dong_khach_khac[0]

        payment_rows = frappe.get_all(
            "Payment Schedule",
            fields=["name", "parent", "parenttype"],
            limit=1,
        )
        if not payment_rows:
            self.skipTest(
                "Không có Payment Schedule thật nào trên site để probe — "
                "cần Sales Invoice/Sales Order có lịch thanh toán."
            )
        self.payment_row = payment_rows[0]

    # ---------- dạng list (không <name>), cả ba prefix ----------
    def test_sales_order_item_list_khong_ro_ri_qua_ca_ba_prefix(self):
        """Ca cơ bản: Sales Order Item của khách KHÁC không được lộ qua bất
        kỳ prefix REST nào khi bvbm@demo.miyano GET dạng list."""
        for prefix in _PREFIXES:
            with self.subTest(prefix=prefix):
                resp = self.session.get(
                    f"{BASE_URL}{prefix}Sales Order Item",
                    params={
                        "parent": "Sales Order",
                        "filters": f'[["parent","in",["{self.don_khach_khac}"]]]',
                        "fields": '["parent","item_code","rate","amount"]',
                    },
                    timeout=5,
                )
                body = resp.text
                self.assertEqual(
                    resp.status_code,
                    403,
                    f"{prefix}Sales Order Item phải trả 403 cho khách cổng, "
                    f"thực tế {resp.status_code}: {body[:300]}",
                )
                self.assertNotIn(self.don_khach_khac, body)

    def test_payment_schedule_list_khong_ro_ri_qua_ca_ba_prefix(self):
        """Ca BẮT BUỘC theo brief — `Payment Schedule` mang `outstanding`/
        `payment_amount`, đúng doctype đã lật tẩy bản vá fail-open liệt kê
        tên của Task 1b round 1. `parent=` đổi giữa hai `parenttype` thật
        (`Sales Order`/`Sales Invoice`) để chứng minh gate không tin
        `parent` client gửi."""
        for prefix in _PREFIXES:
            for parent in ("Sales Order", "Sales Invoice"):
                with self.subTest(prefix=prefix, parent=parent):
                    resp = self.session.get(
                        f"{BASE_URL}{prefix}Payment Schedule",
                        params={
                            "parent": parent,
                            "fields": '["parent","parenttype","payment_amount","outstanding"]',
                            "limit_page_length": 0,
                        },
                        timeout=5,
                    )
                    body = resp.text
                    self.assertEqual(
                        resp.status_code,
                        403,
                        f"{prefix}Payment Schedule (parent={parent}) phải "
                        f"trả 403, thực tế {resp.status_code}: {body[:300]}",
                    )
                    self.assertNotIn("outstanding", body)
                    self.assertNotIn("payment_amount", body)

    # ---------- dạng đơn lẻ <name>, cả ba prefix ----------
    def test_sales_order_item_single_doc_khong_ro_ri_qua_ca_ba_prefix(self):
        """Dạng `/<doctype>/<name>` KHÔNG gọi `frappe.client.get` — nó gọi
        thẳng `frappe.get_doc()` rồi `doc.has_permission()`
        (`permissions.py::has_child_permission()` rẽ nhánh sang parent, xem
        docstring `search_guard.py`) — một đường lỗ khác hẳn, phải test
        riêng, không suy luận từ ca list ở trên."""
        name = self.dong_khach_khac["name"]
        for prefix in _PREFIXES:
            with self.subTest(prefix=prefix):
                resp = self.session.get(
                    f"{BASE_URL}{prefix}Sales Order Item/{name}",
                    params={"parent": "Sales Order"},
                    timeout=5,
                )
                body = resp.text
                self.assertEqual(
                    resp.status_code,
                    403,
                    f"{prefix}Sales Order Item/{name} phải trả 403, thực "
                    f"tế {resp.status_code}: {body[:300]}",
                )
                self.assertNotIn(self.don_khach_khac, body)

    def test_payment_schedule_single_doc_khong_ro_ri_qua_ca_ba_prefix(self):
        name = self.payment_row["name"]
        for prefix in _PREFIXES:
            with self.subTest(prefix=prefix):
                resp = self.session.get(
                    f"{BASE_URL}{prefix}Payment Schedule/{name}",
                    params={"parent": self.payment_row["parenttype"]},
                    timeout=5,
                )
                self.assertEqual(
                    resp.status_code,
                    403,
                    f"{prefix}Payment Schedule/{name} phải trả 403, thực "
                    f"tế {resp.status_code}: {resp.text[:300]}",
                )

    # ---------- không chặn nhầm doctype cha ----------
    def test_sales_order_cha_van_doc_duoc_qua_resource(self):
        """`Sales Order` (doctype CHA, không phải bảng con —
        `frappe.is_table("Sales Order")` là False) KHÔNG thuộc phạm vi hook
        này — đã có `permission_query_conditions::sales_query` lọc đúng từ
        trước (Task 1). Khách vẫn phải GET được danh sách đơn của CHÍNH
        mình qua `/api/resource/Sales Order`."""
        resp = self.session.get(
            f"{BASE_URL}/api/resource/Sales Order",
            params={"filters": f'[["customer","=","{BVBM}"]]'},
            timeout=5,
        )
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertNotIn(self.don_khach_khac, resp.text)


class TestRestGuardMoPhongHam(FrappeTestCase):
    """Gọi thẳng `chan_rest_doctype_con()` với `frappe.local.request` giả lập
    — KHÔNG đi qua HTTP thật.

    Lớp `TestRestGuardChanDoctypeCon` ở trên là bằng chứng CHÍNH (bắt buộc
    theo brief, vì lỗ nằm ở tầng định tuyến HTTP thật) nhưng nó `skipTest()`
    vô điều kiện nếu bench không đang chạy ở `BASE_URL` — trên một máy khác,
    hoặc nếu ai đó vô tình dừng gunicorn giữa chừng, `bench run-tests` báo
    "OK" trong khi KHÔNG kiểm tra được gì cả (skip không phải fail). Lớp
    này là lưới an toàn thứ hai: mô phỏng ĐÚNG những gì `frappe/app.py::
    init_request()` làm trước khi gọi `before_request` (gán `frappe.local.
    request`, đã có session từ `FrappeTestCase`), rồi gọi thẳng
    `chan_rest_doctype_con()` — không cần bench đang serve, không bao giờ
    skip, nhưng cũng KHÔNG thay thế được lớp HTTP thật ở trên (đây là mô
    phỏng, đúng như brief Step 1 cho phép làm phương án dự phòng — không
    chứng minh được override `frappe.api.handle()` có thật sự gọi tới hook
    theo đúng cách framework gọi hay không, chỉ chứng minh BẢN THÂN hàm xử
    lý đúng logic khi được gọi với input đúng hình dạng)."""

    def setUp(self):
        seed_demo()
        self.addCleanup(frappe.set_user, "Administrator")
        self.addCleanup(setattr, frappe.local, "request", None)

    def _goi_voi_path(self, path: str):
        frappe.local.request = frappe._dict(path=path)
        from miyano_portal.rest_guard import chan_rest_doctype_con

        chan_rest_doctype_con()

    def test_chan_doctype_con_ca_ba_prefix(self):
        frappe.set_user(USER_BVBM)
        for prefix in _PREFIXES:
            with self.subTest(prefix=prefix):
                with self.assertRaises(frappe.PermissionError):
                    self._goi_voi_path(f"{prefix}Payment Schedule")

    def test_khong_chan_doctype_cha(self):
        """`Sales Order` không phải bảng con — `is_table()` False — hàm
        phải return êm, không throw."""
        frappe.set_user(USER_BVBM)
        self._goi_voi_path("/api/resource/Sales Order")  # không raise

    def test_khong_chan_desk_user(self):
        frappe.set_user(USER_SALES)
        self._goi_voi_path("/api/resource/Payment Schedule")  # không raise

    def test_khong_chan_guest(self):
        frappe.set_user("Guest")
        self._goi_voi_path("/api/resource/Payment Schedule")  # không raise

    def test_khong_chan_path_tinh(self):
        """Path không chứa `/api/` (file tĩnh, trang SPA) — return sớm nhất,
        không chạm `frappe.is_table()`."""
        frappe.set_user(USER_BVBM)
        self._goi_voi_path("/assets/miyano_portal/css/app.css")  # không raise
        self._goi_voi_path("/portal/login")  # không raise

    def test_khong_chan_thieu_request(self):
        frappe.set_user(USER_BVBM)
        frappe.local.request = None
        from miyano_portal.rest_guard import chan_rest_doctype_con

        chan_rest_doctype_con()  # không raise — return sớm nhất
