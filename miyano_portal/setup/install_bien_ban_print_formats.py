"""Mẫu in theo chế độ kế toán cho Biên bản kiểm hàng và Phiếu giao hàng.

Yêu cầu chủ đầu tư 2026-08-16: *"những phiếu in, biên bản, pdf đều phải đúng
định dạng thông tư chứ không lấy print có sẵn của ERP"*.

Hai lỗ hổng bản này bịt:

1. `Portal Delivery Inspection` **chưa có mẫu in nào** — bấm In là rơi vào mẫu
   Standard của ERPNext. Đúng ra nó là **Mẫu số 03-VT "Biên bản kiểm nghiệm
   vật tư, công cụ, sản phẩm, hàng hoá"**.
2. `Delivery Note` in bằng mẫu thương mại của Miyano, không phải **Mẫu số
   02-VT "Phiếu xuất kho"**.

Dùng lại `_STYLE` của `install_kho_print_formats` — một bảng CSS cho mọi chứng
từ, để hai mẫu mới không trôi dần khỏi bốn mẫu cũ.

**Ràng buộc bối cảnh Jinja** (đọc docstring `install_kho_print_formats` trước
khi sửa): template chỉ được dựa vào `{"doc", "frappe"}`. Mọi thứ khác phải tự
tra bằng `frappe.db.get_value` NGAY TRONG template.

**Về số hiệu mẫu dưới TT107**: bộ mẫu kho sẵn có giữ nguyên số hiệu VT và chỉ
đổi thông tư trích dẫn (xem `HTML_NHAP_TT107`: "Mẫu số 01 - VT ... Thông tư
107/2017"). Hai mẫu ở đây theo ĐÚNG quy ước đó để không có hai cách đánh số
song song trong cùng một app. Nếu kế toán của khách yêu cầu số hiệu khác dưới
TT107, sửa ở đây là đủ — không chỗ nào khác hardcode số hiệu.

**Phiếu xuất kho 02-VT chỉ có bản TT200**: `Delivery Note` là chứng từ của
CHÍNH Miyano (doanh nghiệp), không phải của khách hàng đơn vị sự nghiệp. TT107
áp cho chứng từ trong kho của khách (`Customer Stock *`), nơi đã có sẵn hai
biến thể.
"""

import frappe

from miyano_portal.setup.install_kho_print_formats import _STYLE

NAME_BIEN_BAN_TT107 = "Miyano - Biên bản kiểm nghiệm (TT107)"
NAME_BIEN_BAN_TT200 = "Miyano - Biên bản kiểm nghiệm (TT200)"
NAME_PHIEU_XUAT_02VT = "Miyano - Phiếu xuất kho (02-VT)"

# Khách hàng của Miyano phần lớn là bệnh viện công — đơn vị hành chính sự
# nghiệp, tức TT107. Cùng lựa chọn mặc định với bốn mẫu kho sẵn có.
DEFAULT_BIEN_BAN = NAME_BIEN_BAN_TT107

# Biên bản kiểm nghiệm KHÔNG có bộ chọn mẫu theo khách như phiếu kho.
# `Customer Warehouse.mau_phieu_nhap/xuat` không dùng được ở đây: biên bản
# kiểm hàng CỐ Ý chạy cho cả khách chưa mở kho (16/21 khách trên site), nên
# không có bản ghi kho nào để treo lựa chọn. Cài cả hai mẫu, mặc định TT107,
# nhân viên đổi trong dropdown khi khách là doanh nghiệp.

_BB_SETUP = (
	'{% set kh = frappe.db.get_value("Customer", doc.customer, '
	'["customer_name", "tax_id"], as_dict=True) or {} %}'
	'{% set dn = frappe.db.get_value("Delivery Note", doc.delivery_note, '
	'["posting_date", "company"], as_dict=True) or {} %}'
)

# Cột "Kết quả kiểm nghiệm" của 03-VT tách làm hai: ĐÚNG quy cách phẩm chất
# (`sl_nhan`) và KHÔNG đúng quy cách phẩm chất (`sl_tra`). Phần chênh còn lại
# là hàng KHÔNG TỚI NƠI — không thuộc cột nào trong hai cột đó, nên ghi vào
# cột Ghi chú thay vì nhét bừa vào "không đúng quy cách": thiếu hàng và hàng
# hỏng là hai sự việc khác nhau, và biên bản này là chứng từ pháp lý.
_BB_ROWS = """
    {% for i in doc.items %}
    {% set thieu = (i.sl_giao or 0) - (i.sl_nhan or 0) - (i.sl_tra or 0) %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ i.item_name or i.item_code }}</td>
      <td>{{ i.item_code }}</td>
      <td>Kiểm đếm, quan sát bằng mắt</td>
      <td>{{ i.uom or '' }}</td>
      <td class="num">{{ "{:g}".format(i.sl_giao or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.sl_nhan or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.sl_tra or 0) }}</td>
      <td>
        {%- if thieu > 0 %}Thiếu {{ "{:g}".format(thieu) }} {{ i.uom or '' }}. {% endif -%}
        {{ i.ly_do or '' }}
      </td>
    </tr>
    {% endfor %}
"""


def _html_bien_ban(so_thong_tu: str, ngay_thong_tu: str) -> str:
	"""Mẫu 03-VT. Chỉ khác nhau ở dòng trích dẫn thông tư."""
	return _STYLE + _BB_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ kh.customer_name or doc.customer }}<br/>
      <b>Bộ phận:</b> ......................................
    </div>
    <div class="mau">
      Mẫu số 03 - VT<br/>
      (Ban hành theo Thông tư số """ + so_thong_tu + """<br/>
      ngày """ + ngay_thong_tu + """ của Bộ Tài chính)
    </div>
  </div>
  <h2>BIÊN BẢN KIỂM NGHIỆM</h2>
  <div class="sub">
    (Vật tư, công cụ, sản phẩm, hàng hoá)<br/>
    Ngày {{ frappe.utils.formatdate(doc.ngay_kiem, "dd") }}
    tháng {{ frappe.utils.formatdate(doc.ngay_kiem, "mm") }}
    năm {{ frappe.utils.formatdate(doc.ngay_kiem, "yyyy") }}
    &nbsp;&nbsp; Số: {{ doc.name }}
  </div>

  <p>- Căn cứ Phiếu giao hàng số <b>{{ doc.delivery_note or '' }}</b>
     {% if dn.posting_date %}ngày {{ frappe.utils.formatdate(dn.posting_date, "dd/MM/yyyy") }}{% endif %}
     {% if doc.sales_order %}(theo đơn hàng {{ doc.sales_order }}){% endif %}.</p>

  <p>- Ban kiểm nghiệm gồm:</p>
  <p style="margin-left:24px">
    Ông/Bà ................................................... Chức vụ ............................ Trưởng ban<br/>
    Ông/Bà ................................................... Chức vụ ............................ Uỷ viên<br/>
    Ông/Bà ................................................... Chức vụ ............................ Uỷ viên
  </p>

  <p>- Đã kiểm nghiệm các loại:</p>
  <table class="chung-tu">
    <thead>
      <tr>
        <th rowspan="2">STT</th>
        <th rowspan="2">Tên, nhãn hiệu, quy cách vật tư, công cụ, sản phẩm, hàng hoá</th>
        <th rowspan="2">Mã số</th>
        <th rowspan="2">Phương thức kiểm nghiệm</th>
        <th rowspan="2">Đơn vị tính</th>
        <th rowspan="2">Số lượng theo chứng từ</th>
        <th colspan="2">Kết quả kiểm nghiệm</th>
        <th rowspan="2">Ghi chú</th>
      </tr>
      <tr>
        <th>Số lượng đúng quy cách, phẩm chất</th>
        <th>Số lượng không đúng quy cách, phẩm chất</th>
      </tr>
    </thead>
    <tbody>""" + _BB_ROWS + """</tbody>
  </table>

  <p style="margin-top:12px"><b>Ý kiến của Ban kiểm nghiệm:</b></p>
  <p style="margin-left:24px">
    {%- if doc.ghi_chu %}{{ doc.ghi_chu }}{% else %}
    ...........................................................................................................................
    {% endif -%}
  </p>

  <div class="ky">
    <div><b>Đại diện kỹ thuật</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)</div>
    <div><b>Trưởng ban</b>(Ký, họ tên)</div>
  </div>
</div>
"""


_XUAT_SETUP = (
	'{% set cty = frappe.db.get_value("Company", doc.company, '
	'["company_name", "tax_id"], as_dict=True) or {} %}'
)

_XUAT_ROWS = """
    {% for i in doc.items %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ i.item_name or i.item_code }}</td>
      <td>{{ i.item_code }}</td>
      <td>{{ i.uom or '' }}</td>
      <td class="num">{{ "{:g}".format(i.qty or 0) }}</td>
      <td class="num">{{ "{:g}".format(i.qty or 0) }}</td>
      <td class="num">{{ "{:,.0f}".format(i.rate or 0) }}</td>
      <td class="num">{{ "{:,.0f}".format(i.amount or 0) }}</td>
    </tr>
    {% endfor %}
"""

HTML_PHIEU_XUAT_02VT = _STYLE + _XUAT_SETUP + """
<div class="phieu-kho">
  <div class="hdr">
    <div>
      <b>Đơn vị:</b> {{ cty.company_name or doc.company }}<br/>
      <b>Mã số thuế:</b> {{ cty.tax_id or '' }}
    </div>
    <div class="mau">
      Mẫu số 02 - VT<br/>
      (Ban hành theo Thông tư số 200/2014/TT-BTC<br/>
      ngày 22/12/2014 của Bộ Tài chính)
    </div>
  </div>
  <h2>PHIẾU XUẤT KHO</h2>
  <div class="sub">
    Ngày {{ frappe.utils.formatdate(doc.posting_date, "dd") }}
    tháng {{ frappe.utils.formatdate(doc.posting_date, "mm") }}
    năm {{ frappe.utils.formatdate(doc.posting_date, "yyyy") }}
    &nbsp;&nbsp; Số: {{ doc.name }}<br/>
    Nợ TK ..................... &nbsp;&nbsp; Có TK .....................
  </div>
  <p>- Họ và tên người nhận hàng: ..................................................
     Bộ phận: ..................................</p>
  <p>- Lý do xuất kho: Giao hàng cho <b>{{ doc.customer_name or doc.customer }}</b>
     {% if doc.is_return %}<b>(PHIẾU TRẢ HÀNG — hàng nhận lại từ khách)</b>{% endif %}</p>
  <p>- Xuất tại kho: <b>{{ doc.set_warehouse or (doc.items[0].warehouse if doc.items else '') }}</b></p>

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
    <tbody>""" + _XUAT_ROWS + """</tbody>
    <tfoot>
      <tr>
        <td colspan="7" style="text-align:right"><b>Cộng</b></td>
        <td class="num"><b>{{ "{:,.0f}".format(doc.total or 0) }}</b></td>
      </tr>
    </tfoot>
  </table>
  <p>Tổng số tiền (viết bằng chữ): {{ tien_bang_chu(doc.grand_total or doc.total or 0) }}</p>
  <p>Số chứng từ gốc kèm theo: {{ doc.po_no or '' }}</p>

  <!-- Thông tin vận chuyển KHÔNG nằm trong mẫu 02-VT, nhưng giao nhận đang
       dùng nó hằng ngày. Đặt DƯỚI khối chuẩn, tách bằng nhãn riêng — thêm
       thông tin bên dưới không làm sai mẫu, còn bỏ đi thì mất dữ liệu thật. -->
  {% if doc.transporter_name or doc.lr_no %}
  <p style="margin-top:8px; font-style:italic">
    Vận chuyển: {{ doc.transporter_name or '' }}{% if doc.lr_no %} — Vận đơn số {{ doc.lr_no }}{% endif %}
  </p>
  {% endif %}

  <div class="ky">
    <div><b>Người lập phiếu</b>(Ký, họ tên)</div>
    <div><b>Người nhận hàng</b>(Ký, họ tên)</div>
    <div><b>Thủ kho</b>(Ký, họ tên)</div>
    <div><b>Kế toán trưởng</b>(Ký, họ tên)</div>
    <div><b>Giám đốc</b>(Ký, họ tên)</div>
  </div>
</div>
"""

FORMATS = [
	(NAME_BIEN_BAN_TT107, "Portal Delivery Inspection",
	 _html_bien_ban("107/2017/TT-BTC", "10/10/2017")),
	(NAME_BIEN_BAN_TT200, "Portal Delivery Inspection",
	 _html_bien_ban("200/2014/TT-BTC", "22/12/2014")),
	(NAME_PHIEU_XUAT_02VT, "Delivery Note", HTML_PHIEU_XUAT_02VT),
]


def install_bien_ban_print_formats() -> list[str]:
	"""Idempotent theo kiểu "bỏ qua nếu đã có" — cùng khuôn hai installer sẵn
	có. Trả danh sách mẫu VỪA tạo, để patch/test nhìn được chuyện gì đã xảy ra
	thay vì phải đoán."""
	moi = []
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
		moi.append(name)
	return moi
