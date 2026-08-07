"""Bốn mẫu in phiếu nhập/xuất kho khách hàng — TT107 (mặc định, hành chính sự
nghiệp) và TT200 (doanh nghiệp), theo đúng khuôn của
setup/install_print_formats.py (idempotent: bỏ qua nếu đã tồn tại).

Bố cục dựng theo cấu trúc chuẩn Mẫu 01-VT / 02-VT của hai Thông tư. CHƯA khớp
1-1 với mẫu thật mà BV Bạch Mai đang dùng — việc đó cần file mẫu thật của
khách, và kiến trúc (mau_phieu_nhap/mau_phieu_xuat theo từng kho) cho phép
chỉnh riêng cho một khách mà không đụng khách khác.

Các template này KHÔNG chạy qua frappe.www.printview (route đó bị chặn cho
role Customer theo thiết kế — xem miyano_portal/api/kho.py::_render_phieu_html),
nên tự mang theo <style> của riêng mình thay vì dựa vào print.css của Frappe.
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


def _rows_html(rows, extra_col=False):
    trs = []
    for idx, r in enumerate(rows, start=1):
        trs.append(f"""
        <tr>
          <td>{idx}</td>
          <td>{r.ten_vat_tu or ''}</td>
          <td>{(frappe.db.get_value('Customer Warehouse Item', r.vat_tu, 'ma_vat_tu') or '')}</td>
          <td>{r.dvt or ''}</td>
          <td class="num">{r.so_luong:g}</td>
          <td class="num">{r.so_luong:g}</td>
          <td class="num">{'{:,.0f}'.format(r.don_gia or 0)}</td>
          <td class="num">{'{:,.0f}'.format(r.thanh_tien or 0)}</td>
        </tr>""")
    return "".join(trs)


HTML_NHAP_TT107 = _STYLE + """
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
    <tbody>{{ rows_html | safe }}</tbody>
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

HTML_XUAT_TT107 = _STYLE + """
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
  <p>Họ và tên người nhận hàng: <b>{{ doc.nguoi_nhan or '' }}</b> &nbsp; Nơi nhận: <b>{{ doc.noi_nhan or '' }}</b></p>
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
    <tbody>{{ rows_html | safe }}</tbody>
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

HTML_NHAP_TT200 = _STYLE + """
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
    <tbody>{{ rows_html | safe }}</tbody>
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

HTML_XUAT_TT200 = _STYLE + """
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
  <p>Họ và tên người nhận hàng: <b>{{ doc.nguoi_nhan or '' }}</b> &nbsp; Nơi nhận: <b>{{ doc.noi_nhan or '' }}</b></p>
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
    <tbody>{{ rows_html | safe }}</tbody>
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
