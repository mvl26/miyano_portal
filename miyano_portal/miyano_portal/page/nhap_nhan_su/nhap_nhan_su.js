// Màn Desk "Nhập nhân sự bệnh viện" — Task 15 (QĐ-G17…G23).
//
// Bốn bước, đúng khuôn mà hai màn nhập của cổng khách đã dùng
// (frontend/src/views/ImportTonDau.vue, ImportDanhMuc.vue):
//   1. chọn BỆNH VIỆN — trên màn hình, KHÔNG có cột nào trong tệp (QĐ-G18)
//   2. tải bảng mẫu để nhân viên bệnh viện điền
//   3. tải tệp đã điền lên rồi XEM TRƯỚC — chưa ghi gì
//   4. ghi thật, rồi hiện mật khẩu ĐÚNG MỘT LẦN để chép ra bàn giao (QĐ-G19)
//
// Toàn bộ phép kiểm nằm ở server (`miyano_portal/api/nhan_su.py`): màn này chỉ
// hiển thị verdict, không tự quyết dòng nào hợp lệ.

frappe.pages["nhap-nhan-su"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Nhập nhân sự bệnh viện",
		single_column: true,
	});
	new NhapNhanSu(page);
};

const NHAN = {
	tao_moi: { text: "Sẽ tạo mới", color: "green" },
	bo_qua: { text: "Đã có — bỏ qua", color: "gray" },
	canh_bao: { text: "Cần Miyano quyết", color: "orange" },
	tu_choi: { text: "Bị từ chối", color: "red" },
};

class NhapNhanSu {
	constructor(page) {
		this.page = page;
		this.file_url = null;
		this.file_name = null;
		this.preview = null;
		this.make_controls();
		this.render_body();
	}

	get customer() {
		return this.customer_field.get_value();
	}

	make_controls() {
		this.customer_field = this.page.add_field({
			fieldtype: "Link",
			fieldname: "customer",
			label: __("Bệnh viện"),
			options: "Customer",
			reqd: 1,
			change: () => {
				// Đổi bệnh viện thì mọi thứ đã xem trước không còn nghĩa gì —
				// dọn sạch để không ai bấm Ghi với verdict của viện khác.
				this.reset(true);
			},
		});
		this.page.set_primary_action(__("Xem trước"), () => this.xem_truoc(), "search");
		this.page.add_menu_item(__("Tải bảng mẫu Excel"), () => this.tai_mau());
	}

	tai_mau() {
		window.open("/api/method/miyano_portal.api.nhan_su.nhan_su_import_template");
	}

	render_body() {
		this.page.main.html(`
			<div class="nhan-su-import" style="padding: 12px 0">
				<div class="frappe-card" style="padding: 14px; margin-bottom: 12px">
					<b>Bước 1 · Chọn bệnh viện</b>
					<p class="text-muted" style="margin: 6px 0 0">
						Bệnh viện chọn ở ô trên đầu màn hình, cố ý KHÔNG có trong tệp Excel:
						một cột "tên bệnh viện" gõ tay là đường để nhập nhầm người của viện
						này sang viện khác.
					</p>
				</div>
				<div class="frappe-card" style="padding: 14px; margin-bottom: 12px">
					<b>Bước 2 · Tải bảng mẫu cho bệnh viện điền</b>
					<p class="text-muted" style="margin: 6px 0 10px">
						Gồm các cột: Họ tên · Email · Khoa · Mã khoa · Vai trò.
						Vai trò nhận đúng hai giá trị: <b>Quản lý</b> (nhìn toàn viện, để
						trống Khoa) hoặc <b>Nhân viên khoa</b> (bắt buộc có Khoa).
						<b>Không điền mật khẩu vào tệp</b> — Miyano đặt mật khẩu ở bước 4.
					</p>
					<button class="btn btn-default btn-sm btn-tai-mau">⬇ Tải bảng mẫu Excel</button>
				</div>
				<div class="frappe-card" style="padding: 14px; margin-bottom: 12px">
					<b>Bước 3 · Tải tệp đã điền lên và xem trước</b>
					<p class="text-muted" style="margin: 6px 0 10px">
						Bước xem trước <b>không ghi gì</b> — nó chỉ nói từng dòng sẽ ra sao.
					</p>
					<button class="btn btn-default btn-sm btn-chon-tep">📎 Chọn tệp .xlsx</button>
					<span class="ten-tep text-muted" style="margin-left: 10px"></span>
				</div>
				<div class="ket-qua-xem-truoc"></div>
				<div class="ket-qua-ghi"></div>
			</div>
		`);
		this.page.main.find(".btn-tai-mau").on("click", () => this.tai_mau());
		this.page.main.find(".btn-chon-tep").on("click", () => this.chon_tep());
	}

	reset(giu_tep) {
		this.preview = null;
		this.page.main.find(".ket-qua-xem-truoc").empty();
		this.page.main.find(".ket-qua-ghi").empty();
		if (!giu_tep) {
			this.file_url = null;
			this.file_name = null;
			this.page.main.find(".ten-tep").text("");
		}
	}

	chon_tep() {
		new frappe.ui.FileUploader({
			allow_multiple: false,
			disable_file_browser: true,
			restrictions: { allowed_file_types: [".xlsx"] },
			on_success: (file_doc) => {
				this.file_url = file_doc.file_url;
				this.file_name = file_doc.file_name;
				this.reset(true);
				this.page.main.find(".ten-tep").text(file_doc.file_name);
			},
		});
	}

	kiem_dau_vao() {
		if (!this.customer) {
			frappe.msgprint(__("Chọn bệnh viện trước đã."));
			return false;
		}
		if (!this.file_url) {
			frappe.msgprint(__("Chọn tệp .xlsx đã điền."));
			return false;
		}
		return true;
	}

	xem_truoc() {
		if (!this.kiem_dau_vao()) return;
		frappe.call({
			method: "miyano_portal.api.nhan_su.nhan_su_import_preview",
			args: { customer: this.customer, file_url: this.file_url },
			freeze: true,
			freeze_message: __("Đang đọc tệp…"),
			callback: (r) => {
				this.preview = r.message;
				this.ve_xem_truoc(r.message);
			},
		});
	}

	ghi() {
		if (!this.kiem_dau_vao()) return;
		const so_tao = this.preview ? this.preview.so_tao_moi : 0;
		frappe.confirm(
			__(
				"Sẽ tạo {0} tài khoản đăng nhập cho <b>{1}</b>. Tài khoản đã tạo thì " +
					"không xoá sạch dấu vết được — đã soát kỹ bảng xem trước chưa?",
				[so_tao, frappe.utils.escape_html(this.customer)]
			),
			() => {
				frappe.call({
					method: "miyano_portal.api.nhan_su.nhan_su_import_commit",
					args: { customer: this.customer, file_url: this.file_url },
					freeze: true,
					freeze_message: __("Đang tạo tài khoản…"),
					callback: (r) => {
						this.page.main.find(".ket-qua-xem-truoc").empty();
						this.ve_ket_qua(r.message);
					},
				});
			}
		);
	}

	// `da_ghi` đổi nhãn "Sẽ tạo mới" thành "Đã tạo" cho bảng SAU khi ghi —
	// cùng một dữ liệu dòng, hai thì khác nhau.
	bang_dong(rows, da_ghi) {
		const o = (s) => frappe.utils.escape_html(s || "");
		const tr = rows
			.map((d) => {
				let nhan = NHAN[d.trang_thai] || NHAN.tu_choi;
				if (da_ghi && d.trang_thai === "tao_moi") {
					nhan = { text: "Đã tạo", color: "green" };
				}
				const ly_do = (d.errors || []).join(" · ") || d.ghi_chu || "";
				const khoa = d.khoa_moi ? `${o(d.ten_khoa)} <i>(khoa mới)</i>` : o(d.ten_khoa);
				return `<tr>
					<td>${d.line}</td>
					<td>${o(d.ho_ten)}</td>
					<td>${o(d.email)}</td>
					<td>${khoa}</td>
					<td>${o(d.vai_tro)}</td>
					<td><span class="indicator-pill ${nhan.color}">${nhan.text}</span></td>
					<td class="text-muted">${o(ly_do)}</td>
				</tr>`;
			})
			.join("");
		return `<div style="overflow-x: auto">
			<table class="table table-bordered" style="margin: 10px 0 0">
				<thead><tr>
					<th style="width: 52px">Dòng</th><th>Họ tên</th><th>Email</th>
					<th>Khoa</th><th>Vai trò</th><th style="width: 130px">Kết luận</th><th>Lý do</th>
				</tr></thead>
				<tbody>${tr}</tbody>
			</table>
		</div>`;
	}

	ve_xem_truoc(kq) {
		const o = (s) => frappe.utils.escape_html(s || "");
		const khoa_moi = (kq.khoa_se_tao || [])
			.map((k) => `sẽ tạo khoa mới: <b>${o(k.ten_khoa_phong)}</b> (${o(k.ma_khoa) || "chưa có mã"})`)
			.join("<br>");
		const loi = (kq.loi_toan_tep || []).map((m) => `<div class="text-danger">⛔ ${o(m)}</div>`).join("");
		const canh_bao = (kq.canh_bao_toan_tep || [])
			.map((m) => `<div class="text-warning">⚠ ${o(m)}</div>`)
			.join("");
		const html = `
			<div class="frappe-card" style="padding: 14px; margin-bottom: 12px">
				<b>Bước 4 · Kết quả xem trước — chưa ghi gì</b>
				<div style="margin-top: 8px">
					Tổng ${kq.total} dòng ·
					<span class="indicator-pill green">${kq.so_tao_moi} sẽ tạo mới</span>
					<span class="indicator-pill gray">${kq.so_bo_qua} đã có</span>
					<span class="indicator-pill orange">${kq.so_canh_bao} cần quyết</span>
					<span class="indicator-pill red">${kq.so_tu_choi} bị từ chối</span>
				</div>
				${loi}${canh_bao}
				${khoa_moi ? `<div style="margin-top: 8px">${khoa_moi}</div>` : ""}
				${this.bang_dong(kq.rows || [])}
				<div style="margin-top: 12px">
					<button class="btn btn-primary btn-sm btn-ghi" ${
						kq.so_tu_choi || !kq.so_tao_moi ? "disabled" : ""
					}>Tạo ${kq.so_tao_moi} tài khoản</button>
					${
						kq.so_tu_choi
							? '<span class="text-muted" style="margin-left: 10px">Còn dòng bị từ chối — sửa tệp rồi tải lại. Một dòng lỗi thì không dòng nào được ghi.</span>'
							: ""
					}
				</div>
			</div>`;
		this.page.main.find(".ket-qua-xem-truoc").html(html);
		this.page.main.find(".btn-ghi").on("click", () => this.ghi());
	}

	ve_ket_qua(kq) {
		const o = (s) => frappe.utils.escape_html(s || "");
		const mat_khau = kq.mat_khau || {};
		const emails = Object.keys(mat_khau);
		const dong_mk = emails
			.map((e) => `<tr><td>${o(e)}</td><td><code>${o(mat_khau[e])}</code></td></tr>`)
			.join("");
		const khoa = (kq.khoa_da_tao || [])
			.map((k) => `${o(k.ten_khoa_phong)} (${o(k.ma_khoa) || "không mã"})`)
			.join(", ");
		const html = `
			<div class="frappe-card" style="padding: 14px">
				<h5>✅ Đã tạo ${kq.so_tao_moi} tài khoản cho ${o(kq.customer)}</h5>
				<div class="text-muted">
					Bỏ qua ${kq.so_bo_qua} dòng đã có · ${kq.so_canh_bao} dòng cần Miyano quyết
					${khoa ? `· khoa mới: ${khoa}` : ""}
				</div>
				${
					emails.length
						? `<div class="alert alert-warning" style="margin-top: 12px">
								<b>Mật khẩu chỉ hiện MỘT LẦN.</b> Chép ngay để bàn giao — rời khỏi
								màn này là không xem lại được. Nhắc người nhận đổi mật khẩu ngay
								sau khi đăng nhập lần đầu.
							</div>
							<div style="overflow-x: auto">
								<table class="table table-bordered">
									<thead><tr><th>Email</th><th>Mật khẩu</th></tr></thead>
									<tbody>${dong_mk}</tbody>
								</table>
							</div>
							<button class="btn btn-default btn-sm btn-chep">Chép danh sách</button>`
						: ""
				}
				${this.bang_dong(kq.rows || [], true)}
			</div>`;
		this.page.main.find(".ket-qua-ghi").html(html);
		this.page.main.find(".btn-chep").on("click", () => {
			const text = emails.map((e) => `${e}\t${mat_khau[e]}`).join("\n");
			frappe.utils.copy_to_clipboard(text);
		});
	}
}
