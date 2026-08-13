"""Bốn mẫu in phiếu nhập/xuất kho khách hàng — TT107 (mặc định, hành chính sự
nghiệp) và TT200 (doanh nghiệp), theo đúng khuôn của
setup/install_print_formats.py (idempotent: bỏ qua nếu đã tồn tại).

Bố cục dựng theo cấu trúc chuẩn Mẫu 01-VT / 02-VT của hai Thông tư. CHƯA khớp
1-1 với mẫu thật mà BV Bạch Mai đang dùng — việc đó cần file mẫu thật của
khách, và kiến trúc (mau_phieu_nhap/mau_phieu_xuat theo từng kho) cho phép
chỉnh riêng cho một khách mà không đụng khách khác.

QUAN TRỌNG — bối cảnh Jinja mà template này PHẢI chạy được:
`miyano_portal.api.kho._render_phieu_html()` (cổng dành cho portal, tự render
qua frappe.render_template sau khi tự kiểm sở hữu, KHÔNG đi qua
frappe.www.printview — xem docstring của hàm đó) không phải là đường DUY NHẤT
render bốn mẫu này. Nhân viên Miyano (System Manager/Sales Manager, có
print=1 trên Customer Stock Receipt/Issue) vẫn bấm "In" từ desk như bình
thường, và đường đó đi qua frappe.www.printview.get_html_and_style() —
pipeline CHUẨN của Frappe, chỉ truyền đúng hai biến {"doc": ..., "frappe":
...} vào context (giống ba mẫu portal sẵn có ở install_print_formats.py:
"Miyano - Xác nhận đơn hàng" v.v., chỉ dùng doc/frappe). Template ban đầu của
bản này còn tham chiếu `kho` và `rows_html` — hai biến chỉ do
_render_phieu_html() tự bơm thêm — nên RENDER LỖI ("'kho' is undefined") khi
đi qua đường desk chuẩn. Đã đo bằng get_html_and_style() thật và sửa: mọi
thông tin kho và danh sách dòng giờ tự tra trong chính template bằng
frappe.db.get_value()/vòng lặp doc.items, để cả hai đường render đều dùng
đúng một context tối thiểu {"doc", "frappe"}.

F-4 (review E8, CHẶN) — HAI mẫu XUẤT (TT107/TT200) từng in "Khoa phòng nhận"
thành một dòng RIÊNG, TRÊN dòng "Nơi nhận" sẵn có (`doc.noi_nhan`, free text,
đã tồn tại từ trước E8 — xem test_kho_issue.test_noi_nhan_is_free_text). Kịch
bản đời thật bản sửa này chặn: kho CHƯA bật `bat_buoc_khoa_phong`, thủ kho gõ
`noi_nhan = "Khoa Hồi sức"` như đã làm nhiều tháng (không chọn khoa_phong có
cấu trúc) → phiếu GIẤY CÓ CHỮ KÝ ghi "Khoa Hồi sức" ở dòng Nơi nhận, trong khi
báo cáo cấp phát xếp phiếu đó vào "Chưa gắn khoa" (đúng theo BR-CP4, nhóm đó
KHÔNG được giấu) — hai dòng chọi nhau trên CÙNG một chứng từ kế toán, và vì
nhóm "Chưa gắn khoa" được PRD hợp thức hoá là dữ liệu thật nên không ai buộc
phải đi đối chiếu `noi_nhan` để phát hiện. US-E8.4 chỉ nói khoa phòng in "ở
phần người nhận của mẫu" — không nói thêm một dòng mới. Sửa: khi có
`khoa_phong`, tên khoa THAY THẾ giá trị của chính ô "Nơi nhận" (không thêm
dòng); không có thì `noi_nhan` tự do vẫn hiện y như trước E8 — không có gì để
chọi nhau vì chỉ còn một phát biểu duy nhất về nơi nhận trên phiếu.
"""

import frappe

NAME_NHAP_TT107 = "Miyano - Phiếu nhập kho (TT107)"
NAME_XUAT_TT107 = "Miyano - Phiếu xuất kho (TT107)"
NAME_NHAP_TT200 = "Miyano - Phiếu nhập kho (TT200)"
NAME_XUAT_TT200 = "Miyano - Phiếu xuất kho (TT200)"

_STYLE = """
<style>
  .phieu-kho { font-family: 'Times New Roman', serif; font-size: 13px; color: #111; }
  /* display:table/table-cell thay vì flex: engine xuất PDF (weasyprint) chỉ
     hỗ trợ CSS 2.1, không hiểu flexbox — dùng flex khiến cột "hdr"/"ky" xẹp
     về một hàng dọc trong file PDF thật dù nhìn bình thường trên trình duyệt. */
  .phieu-kho .hdr { display: table; width: 100%; margin-bottom: 4px; table-layout: fixed; }
  .phieu-kho .hdr > div { display: table-cell; vertical-align: top; }
  .phieu-kho .hdr .mau { text-align: right; font-style: italic; font-size: 12px; }
  .phieu-kho h2 { text-align: center; margin: 10px 0 2px; letter-spacing: 1px; }
  .phieu-kho .sub { text-align: center; margin: 0 0 12px; font-size: 12px; }
  .phieu-kho table.chung-tu { width: 100%; border-collapse: collapse; margin-top: 8px; }
  .phieu-kho th, .phieu-kho td { border: 1px solid #333; padding: 4px 6px; }
  .phieu-kho th { text-align: center; background: #f2f2f2; }
  .phieu-kho td.num { text-align: right; }
  .phieu-kho .ky { display: table; width: 100%; margin-top: 40px; text-align: center; table-layout: fixed; }
  .phieu-kho .ky > div { display: table-cell; }
  .phieu-kho .ky b { display: block; margin-bottom: 50px; }
</style>
"""

# Đặt ở đầu mỗi template: tự tra thông tin kho từ doc.kho bằng frappe.db.get_value,
# KHÔNG trông cậy vào một biến `kho` được bơm sẵn từ bên ngoài — đó chính là
# lỗi bản trước (xem docstring module). `frappe` luôn có mặt trong context của
# CẢ HAI đường render (printview chuẩn và _render_phieu_html của portal).
_HDR_SETUP = (
    '{% set kho = frappe.db.get_value("Customer Warehouse", doc.kho, '
    '["ten_kho", "ten_don_vi_in", "bo_phan_in", "thu_kho", "dia_chi_kho"], as_dict=True) %}'
)

# Một dòng chứng từ: tra mã vật tư (không lưu trực tiếp trên dòng phiếu) rồi
# in đủ 8 cột. Lặp trực tiếp `doc.items` trong Jinja thay vì dựng sẵn HTML
# bằng Python — không còn biến `rows_html` phải bơm từ ngoài vào nữa.
_ROWS_LOOP = """
    {% for i in doc.items %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ i.ten_vat_tu or '' }}</td>
      <td>{{ frappe.db.get_value("Customer Warehouse Item", i.vat_tu, "ma_vat_tu") or '' }}</td>
      <td>{{ i.dvt or '' }}</td>
      <td class="num">{{ "{:g}".format(i.so_luong or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.so_luong or 0) }}</td>
      <td class="num">{{ "{:,.0f}".format(i.don_gia or 0) }}</td>
      <td class="num">{{ "{:,.0f}".format(i.thanh_tien or 0) }}</td>
    </tr>
    {% endfor %}
"""


HTML_NHAP_TT107 = _STYLE + _HDR_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ kho.ten_don_vi_in or kho.ten_kho }}<br/>
      <b>Bộ phận:</b> {{ kho.bo_phan_in or '' }}
    </div>
    <div class="mau">
      Mẫu số 01 - VT<br/>
      (Ban hành theo Thông tư số 107/2017/TT-BTC<br/>
      ngày 10/10/2017 của Bộ Tài chính)
    </div>
  </div>
  <h2>PHIẾU NHẬP KHO</h2>
  <div class="sub">
    Ngày {{ frappe.utils.formatdate(doc.ngay, "dd") }} tháng {{ frappe.utils.formatdate(doc.ngay, "mm") }}
    năm {{ frappe.utils.formatdate(doc.ngay, "yyyy") }} &nbsp;&nbsp; Số: {{ doc.name }}
  </div>
  <p>Họ và tên người giao: <b>{{ doc.nguoi_giao or '' }}</b></p>
  <p>Theo chứng từ kèm theo: {{ doc.chung_tu_kem or '' }} {% if doc.delivery_note %}(Phiếu giao hàng Miyano {{ doc.delivery_note }}){% endif %}</p>
  <p>Nhập tại kho: <b>{{ kho.ten_kho }}</b> &nbsp; Địa điểm: {{ kho.dia_chi_kho or '' }}</p>
  <table class="chung-tu">
    <thead>
      <tr>
        <th rowspan="2">STT</th>
        <th rowspan="2">Tên, nhãn hiệu, quy cách vật tư</th>
        <th rowspan="2">Mã số</th>
        <th rowspan="2">Đơn vị tính</th>
        <th colspan="2">Số lượng</th>
        <th rowspan="2">Đơn giá</th>
        <th rowspan="2">Thành tiền</th>
      </tr>
      <tr><th>Theo chứng từ</th><th>Thực nhập</th></tr>
    </thead>
    <tbody>""" + _ROWS_LOOP + """</tbody>
    <tfoot>
      <tr><td colspan="7" style="text-align:right"><b>Cộng</b></td><td class="num"><b>{{ '{:,.0f}'.format(doc.tong_tien or 0) }}</b></td></tr>
    </tfoot>
  </table>
  <p>{{ doc.dien_giai or '' }}</p>
  <div class="ky">
    <div><b>Người lập phiếu</b>(Ký, họ tên)</div>
    <div><b>Người giao hàng</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)<br/>{{ kho.thu_kho or '' }}</div>
    <div><b>Kế toán trưởng</b>(Ký, họ tên)</div>
    <div><b>Thủ trưởng đơn vị</b>(Ký, họ tên)</div>
  </div>
</div>
"""

HTML_XUAT_TT107 = _STYLE + _HDR_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ kho.ten_don_vi_in or kho.ten_kho }}<br/>
      <b>Bộ phận:</b> {{ kho.bo_phan_in or '' }}
    </div>
    <div class="mau">
      Mẫu số 02 - VT<br/>
      (Ban hành theo Thông tư số 107/2017/TT-BTC<br/>
      ngày 10/10/2017 của Bộ Tài chính)
    </div>
  </div>
  <h2>PHIẾU XUẤT KHO</h2>
  <div class="sub">
    Ngày {{ frappe.utils.formatdate(doc.ngay, "dd") }} tháng {{ frappe.utils.formatdate(doc.ngay, "mm") }}
    năm {{ frappe.utils.formatdate(doc.ngay, "yyyy") }} &nbsp;&nbsp; Số: {{ doc.name }}
  </div>
  {% set ten_khoa = frappe.db.get_value("Customer Department", doc.khoa_phong, "ten_khoa_phong") if doc.khoa_phong else None %}
  <p>Họ và tên người nhận hàng: <b>{{ doc.nguoi_nhan or '' }}</b> &nbsp; Nơi nhận: <b>{{ ten_khoa or doc.noi_nhan or '' }}</b></p>
  <p>Lý do xuất kho: {{ doc.dien_giai or doc.loai_xuat or '' }}</p>
  <p>Xuất tại kho: <b>{{ kho.ten_kho }}</b> &nbsp; Địa điểm: {{ kho.dia_chi_kho or '' }}</p>
  <table class="chung-tu">
    <thead>
      <tr>
        <th rowspan="2">STT</th>
        <th rowspan="2">Tên, nhãn hiệu, quy cách vật tư</th>
        <th rowspan="2">Mã số</th>
        <th rowspan="2">Đơn vị tính</th>
        <th colspan="2">Số lượng</th>
        <th rowspan="2">Đơn giá</th>
        <th rowspan="2">Thành tiền</th>
      </tr>
      <tr><th>Yêu cầu</th><th>Thực xuất</th></tr>
    </thead>
    <tbody>""" + _ROWS_LOOP + """</tbody>
    <tfoot>
      <tr><td colspan="7" style="text-align:right"><b>Cộng</b></td><td class="num"><b>{{ '{:,.0f}'.format(doc.tong_tien or 0) }}</b></td></tr>
    </tfoot>
  </table>
  <div class="ky">
    <div><b>Người lập phiếu</b>(Ký, họ tên)</div>
    <div><b>Người nhận hàng</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)<br/>{{ kho.thu_kho or '' }}</div>
    <div><b>Kế toán trưởng</b>(Ký, họ tên)</div>
    <div><b>Thủ trưởng đơn vị</b>(Ký, họ tên)</div>
  </div>
</div>
"""

HTML_NHAP_TT200 = _STYLE + _HDR_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ kho.ten_don_vi_in or kho.ten_kho }}<br/>
      <b>Bộ phận:</b> {{ kho.bo_phan_in or '' }}
    </div>
    <div class="mau">
      Mẫu số 01 - VT<br/>
      (Ban hành theo Thông tư số 200/2014/TT-BTC<br/>
      ngày 22/12/2014 của Bộ Tài chính)
    </div>
  </div>
  <h2>PHIẾU NHẬP KHO</h2>
  <div class="sub">
    Ngày {{ frappe.utils.formatdate(doc.ngay, "dd") }} tháng {{ frappe.utils.formatdate(doc.ngay, "mm") }}
    năm {{ frappe.utils.formatdate(doc.ngay, "yyyy") }} &nbsp;&nbsp; Số: {{ doc.name }}<br/>
    Nợ TK ..................... &nbsp;&nbsp; Có TK .....................
  </div>
  <p>Họ và tên người giao: <b>{{ doc.nguoi_giao or '' }}</b></p>
  <p>Theo chứng từ kèm theo: {{ doc.chung_tu_kem or '' }} {% if doc.delivery_note %}(Phiếu giao hàng Miyano {{ doc.delivery_note }}){% endif %}</p>
  <p>Nhập tại kho: <b>{{ kho.ten_kho }}</b> &nbsp; Địa điểm: {{ kho.dia_chi_kho or '' }}</p>
  <table class="chung-tu">
    <thead>
      <tr>
        <th rowspan="2">STT</th>
        <th rowspan="2">Tên, nhãn hiệu, quy cách vật tư</th>
        <th rowspan="2">Mã số</th>
        <th rowspan="2">Đơn vị tính</th>
        <th colspan="2">Số lượng</th>
        <th rowspan="2">Đơn giá</th>
        <th rowspan="2">Thành tiền</th>
      </tr>
      <tr><th>Theo chứng từ</th><th>Thực nhập</th></tr>
    </thead>
    <tbody>""" + _ROWS_LOOP + """</tbody>
    <tfoot>
      <tr><td colspan="7" style="text-align:right"><b>Cộng</b></td><td class="num"><b>{{ '{:,.0f}'.format(doc.tong_tien or 0) }}</b></td></tr>
    </tfoot>
  </table>
  <p>{{ doc.dien_giai or '' }}</p>
  <div class="ky">
    <div><b>Người lập phiếu</b>(Ký, họ tên)</div>
    <div><b>Người giao hàng</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)<br/>{{ kho.thu_kho or '' }}</div>
    <div><b>Kế toán trưởng</b>(Ký, họ tên)</div>
    <div><b>Giám đốc</b>(Ký, họ tên)</div>
  </div>
</div>
"""

HTML_XUAT_TT200 = _STYLE + _HDR_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ kho.ten_don_vi_in or kho.ten_kho }}<br/>
      <b>Bộ phận:</b> {{ kho.bo_phan_in or '' }}
    </div>
    <div class="mau">
      Mẫu số 02 - VT<br/>
      (Ban hành theo Thông tư số 200/2014/TT-BTC<br/>
      ngày 22/12/2014 của Bộ Tài chính)
    </div>
  </div>
  <h2>PHIẾU XUẤT KHO</h2>
  <div class="sub">
    Ngày {{ frappe.utils.formatdate(doc.ngay, "dd") }} tháng {{ frappe.utils.formatdate(doc.ngay, "mm") }}
    năm {{ frappe.utils.formatdate(doc.ngay, "yyyy") }} &nbsp;&nbsp; Số: {{ doc.name }}<br/>
    Nợ TK ..................... &nbsp;&nbsp; Có TK .....................
  </div>
  {% set ten_khoa = frappe.db.get_value("Customer Department", doc.khoa_phong, "ten_khoa_phong") if doc.khoa_phong else None %}
  <p>Họ và tên người nhận hàng: <b>{{ doc.nguoi_nhan or '' }}</b> &nbsp; Nơi nhận: <b>{{ ten_khoa or doc.noi_nhan or '' }}</b></p>
  <p>Lý do xuất kho: {{ doc.dien_giai or doc.loai_xuat or '' }}</p>
  <p>Xuất tại kho: <b>{{ kho.ten_kho }}</b> &nbsp; Địa điểm: {{ kho.dia_chi_kho or '' }}</p>
  <table class="chung-tu">
    <thead>
      <tr>
        <th rowspan="2">STT</th>
        <th rowspan="2">Tên, nhãn hiệu, quy cách vật tư</th>
        <th rowspan="2">Mã số</th>
        <th rowspan="2">Đơn vị tính</th>
        <th colspan="2">Số lượng</th>
        <th rowspan="2">Đơn giá</th>
        <th rowspan="2">Thành tiền</th>
      </tr>
      <tr><th>Yêu cầu</th><th>Thực xuất</th></tr>
    </thead>
    <tbody>""" + _ROWS_LOOP + """</tbody>
    <tfoot>
      <tr><td colspan="7" style="text-align:right"><b>Cộng</b></td><td class="num"><b>{{ '{:,.0f}'.format(doc.tong_tien or 0) }}</b></td></tr>
    </tfoot>
  </table>
  <div class="ky">
    <div><b>Người lập phiếu</b>(Ký, họ tên)</div>
    <div><b>Người nhận hàng</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)<br/>{{ kho.thu_kho or '' }}</div>
    <div><b>Kế toán trưởng</b>(Ký, họ tên)</div>
    <div><b>Giám đốc</b>(Ký, họ tên)</div>
  </div>
</div>
"""

# (name, doc_type, html) — doc_type dùng để xác nhận một mẫu do kho chọn
# (mau_phieu_nhap/mau_phieu_xuat) đúng khớp loại chứng từ trước khi render,
# xem miyano_portal/api/kho.py::_render_phieu_html.
FORMATS = [
    (NAME_NHAP_TT107, "Customer Stock Receipt", HTML_NHAP_TT107),
    (NAME_XUAT_TT107, "Customer Stock Issue", HTML_XUAT_TT107),
    (NAME_NHAP_TT200, "Customer Stock Receipt", HTML_NHAP_TT200),
    (NAME_XUAT_TT200, "Customer Stock Issue", HTML_XUAT_TT200),
]

# Mẫu mặc định khi Customer Warehouse.mau_phieu_nhap / .mau_phieu_xuat để trống.
DEFAULT_NHAP = NAME_NHAP_TT107
DEFAULT_XUAT = NAME_XUAT_TT107


def install_kho_print_formats():
    for name, doc_type, html in FORMATS:
        if frappe.db.exists("Print Format", name):
            continue
        frappe.get_doc({
            "doctype": "Print Format",
            "name": name,
            "doc_type": doc_type,
            "standard": "No",
            "custom_format": 1,
            "print_format_type": "Jinja",
            "html": html,
        }).insert(ignore_permissions=True)


def update_kho_print_formats_khoa_phong():
    """E8/US-E8.4/BR-CP5 — thêm dòng "Khoa phòng nhận" vào hai mẫu XUẤT
    (TT107, TT200) đã cài từ v1_1. `install_kho_print_formats()` ở trên CHỈ
    insert khi print format CHƯA TỒN TẠI (idempotent theo kiểu "bỏ qua nếu
    đã có") — site đã chạy patch v1_1 từ trước sẽ không bao giờ nhận được
    nội dung HTML mới nếu gọi lại đúng hàm đó, vì bốn bản ghi đã tồn tại.

    Hàm này ngược lại: LUÔN ghi đè `html` bằng nội dung MỚI NHẤT trong
    `FORMATS`, bất kể trạng thái hiện tại — idempotent theo kiểu "hội tụ về
    cùng một giá trị", đúng khuôn `v1_9/re_apply_workflow_e6_fix.py` xử lý
    một site đã chạy patch cũ TRƯỚC bản sửa nội dung. Chỉ cập nhật hai mẫu
    XUẤT (TT107/TT200) — hai mẫu NHẬP không có khái niệm khoa phòng."""
    html_by_name = {n: h for n, _dt, h in FORMATS}
    for name in (NAME_XUAT_TT107, NAME_XUAT_TT200):
        if not frappe.db.exists("Print Format", name):
            continue
        frappe.db.set_value("Print Format", name, "html", html_by_name[name])
