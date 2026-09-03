<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, statusBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'
import ReasonModal from '../components/ReasonModal.vue'
import KhoiTienTrinh from '../components/chi-tiet/KhoiTienTrinh.vue'
import KhoiBaoGia from '../components/chi-tiet/KhoiBaoGia.vue'
import KhoiGiaoHang from '../components/chi-tiet/KhoiGiaoHang.vue'
import KhoiHoaDonTaiLieu from '../components/chi-tiet/KhoiHoaDonTaiLieu.vue'

// Mã lý do do server trả về (`30_API_Spec` §5) → thông điệp cho người đọc.
// Server trả mã chứ không trả câu chữ để một chỗ đổi câu không phải sửa hai nơi.
const LY_DO = {
  het_han_muc: 'hết hạn mức',
  ngoai_hdnt: 'ngoài hợp đồng',
  thieu_gia: 'chưa có giá',
}

const dangDatLai = ref(false)

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const data = ref(null)
const name = computed(() => route.params.name)

// E6/F-07 [MỚI — QĐ-6] — `portal_order_track` trả THẲNG `loai_don` (thêm ở
// review E6 phần B round 1, dọn dẹp ở round 2). Bản trước không có field
// này nên phải suy bằng heuristic "không gắn HĐNT nào" (`!data.value.hdnt`)
// — đúng cho MỌI đơn đi qua `portal_order_place` nhưng có thể sai với một
// đơn dựng tay trên Desk không gắn HĐNT vì lý do khác. Đọc field thật.
//
// Task 6 (QĐ-G2b) — HAI biến, không phải một. Bản trước dùng CHUNG một
// `laDonMuaLe` cho hai việc khác hẳn nhau: cái NHÃN khách đọc, và cái CHỐT
// bật/tắt khối sửa số lượng (soi gương chốt server). Đổi nghĩa một biến để
// sửa cái nhãn sẽ LẲNG LẶNG dời cái chốt lệch khỏi server.
//
// Từ Task 4, `loai_don === 'Mua lẻ'` KHÔNG còn nghĩa "đơn mua lẻ": nó nghĩa
// là "đơn này có dòng chưa có giá nên cả đơn đi vòng báo giá" (QĐ-G3). Một
// đơn chín dòng hợp đồng + một dòng chờ báo giá cũng mang giá trị đó — dán
// nhãn "Mua lẻ" lên nó là nói với bệnh viện một điều sai.
//
// Task 7 (Ruling P49) — nhãn TẮT khi đơn đã được xác nhận (`docstatus === 1`).
// Vòng báo giá diễn ra lúc đơn còn NHÁP; trên một đơn đã chốt, đã giao xong,
// "Có hàng chờ báo giá" không phải một phân loại sai mà là một lời nói SAI VỀ
// HIỆN TẠI (đo được: MD-HUYETHOC-260825-04, Hoàn thành, giao 100%, vẫn hiện).
// Chỉ NHÃN tắt — `loai_don` là DẤU ghi lại đường đơn đã đi, nó không được tự
// tắt, và mọi CHỐT vẫn đọc dấu nguyên vẹn.
// LOAI_DON_BAO_GIA — bản sao THỨ SÁU của giá trị `"Mua lẻ"` (năm bản kia ở
// Python, xem `portal_mua_le.LOAI_DON_BAO_GIA`). SPA không import được hằng
// số Python, nhưng nó chia được MỘT tên trong file này thay vì viết chuỗi
// thô ở hai chỗ — chỗ duy nhất còn lại mà một lần đổi giá trị sẽ bỏ quên.
const LOAI_DON_BAO_GIA = 'Mua lẻ'
// `docstatus === 0` (nháp), KHÔNG phải `!== 1`: đơn ĐÃ HUỶ mang
// `docstatus === 2`, và `!== 1` sẽ cho nhãn hiện LẠI trên đó. Khách mở một
// đơn đã huỷ mà thấy "đang chờ báo giá" là đúng lớp lỗi P49 vừa dẹp — một
// câu sai về hiện tại. P49 nói nguyên văn "vòng báo giá diễn ra lúc đơn còn
// nháp", nên nháp mới là điều kiện, không phải "chưa chốt".
const coHangChoBaoGia = computed(
  () => data.value?.loai_don === LOAI_DON_BAO_GIA && data.value?.docstatus === 0
)
// Task 4 — cái CHỐT `suaDuocSoLuong` (soi `duoc_sua_da_duyet`) chuyển sang
// `components/chi-tiet/KhoiBaoGia.vue` cùng khối sửa số lượng nó gác; xem
// chú thích đầy đủ ở đó, không chép lần hai.

// review I-4 — spec §3.4: "Dòng đã khớp mã chuyển sang nhóm trên, kèm ghi
// chú nhỏ '(từ yêu cầu: <tên khách gõ>)' để khách đối chiếu được cái mình
// gõ với cái Miyano khớp." Server đã trả `item_khop`/`da_xu_ly` cho MỌI
// dòng `dat_ngoai` (`portal_order_track`, `api/portal.py`) — tách ở đây
// theo `da_xu_ly`, KHÔNG còn để mọi dòng nằm chung dưới tiêu đề "Đang chờ
// Miyano xác nhận nguồn" như bản trước (bản đó chỉ đổi badge, dòng đã khớp
// vẫn đọc như đang chờ).
const datNgoaiDaKhop = computed(() => (data.value?.dat_ngoai || []).filter((d) => d.da_xu_ly))
const datNgoaiChoXuLy = computed(() => (data.value?.dat_ngoai || []).filter((d) => !d.da_xu_ly))

const acceptOpen = ref(false)
const rejecting = ref(false)
const accepting = ref(false)

// Task 4 — `soLuongMoiItems`/`soLuongMoiDatNgoai`/`initSoLuongMoi()` chuyển
// sang `KhoiBaoGia.vue` cùng khối ô nhập chúng phục vụ. `dangSuaSoLuong` ở
// lại: nó còn đi hai đường — truyền xuống con làm prop `dang-gui` (nhãn nút
// + disable), và là `:submitting` của `ReasonModal` xác nhận bên dưới.
const dangSuaSoLuong = ref(false)

const huyOpen = ref(false)
const huyDangGui = ref(false)

// UC-14 — đặt lại theo đơn cũ, theo giá hiện hành.
//
// Task 10 — đích đến ĐỔI: trước bản này hàm nạp `store.cart` rồi đẩy sang
// `/cart`. Giỏ toàn cục đó không còn (màn Đặt hàng gộp giữ giỏ TRONG chính
// nó, dưới dạng một phiếu Nháp), và để `/cart` chuyển hướng suông sẽ là một
// hỏng LẶNG LẼ tệ nhất hạng: toast báo thành công, màn mở ra, giỏ trống.
//
// Thay bằng: tạo thẳng một phiếu Nháp mang đúng các dòng đặt lại được, rồi
// mở `/dat-hang/<ten>`. Lợi thêm hai điều, không chỉ là cách vá:
//   * TẦNG của mỗi dòng do `PortalDeXuatMua._suy_nguon_gia()` quyết ở
//     `validate()` — CÙNG một luật với mọi đường khác, không phải một bản
//     suy tầng thứ hai viết riêng cho nút "Đặt lại";
//   * đơn đặt lại giờ cũng có một chứng từ đề nghị đứng sau, đúng mô hình
//     "mọi đơn đều đi qua một phiếu" mà cổng đang hội tụ về.
async function datLai() {
  if (dangDatLai.value) return
  dangDatLai.value = true
  try {
    const res = await api.call('portal_reorder', { order: name.value })
    if (!res.gio_hang.length) {
      showToast('Không mặt hàng nào của đơn này còn đặt lại được.', 'error')
      return
    }
    const ten = (await api.callDeXuat('de_xuat_tao_nhap')).name
    await api.callDeXuat('de_xuat_luu_nhap', {
      ten,
      items: JSON.stringify(
        res.gio_hang.map((d) => ({
          item_code: d.item_code,
          item_name: d.item_name || d.item_code,
          dvt: d.uom || '',
          so_luong_de_xuat: Number(d.qty) || 0,
        }))
      ),
    })
    if (res.bi_loai.length) {
      // Nêu ĐỦ dòng bị loại kèm lý do. Im lặng bỏ bớt là cách chắc chắn
      // khiến khách đặt thiếu hàng mà không biết.
      showToast(
        'Không đưa vào giỏ được: ' +
          res.bi_loai
            .map((d) => `${d.item_code} (${LY_DO[d.ly_do] || d.ly_do})`)
            .join(', '),
        'error'
      )
    }
    router.push({ name: 'dat-hang', params: { ten } })
  } catch (e) {
    showToast(e.message || 'Không đặt lại được đơn này.', 'error')
  } finally {
    dangDatLai.value = false
  }
}

// Task 4 — `KIEM_HANG_BADGE`/`kiemHangBadge`/`nhapMo`/`nhapData`/
// `nhapDangTai`/`toggleNhap`/`urlPdfNhap`/`dotLabel`/`pdfUrl` chuyển sang
// `components/chi-tiet/KhoiGiaoHang.vue` (và một bản riêng của `pdfUrl` sang
// `KhoiHoaDonTaiLieu.vue`, xem chú thích ở đó) cùng khối "Giao hàng"/"Hoá
// đơn của đơn này" chúng phục vụ. Không chép lại ở đây.

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.call('portal_order_track', { order: name.value })
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết đơn hàng.'
  } finally {
    loading.value = false
  }
}

// Việc 1/brief 2026-08-15 — "Gửi lại để báo giá": chỉ gửi CÁC DÒNG THẬT SỰ
// đổi số lượng (không gửi nguyên giỏ) — payload gọn, và tránh gửi field
// `rate`/`item_code` mà server không cần (server chỉ đọc `item_code`/`name`
// + `qty`, đọc gì khác cũng bị bỏ qua, nhưng gửi thừa vẫn là gửi thừa).
//
// controller ruling 2026-08-16 — bản trước bỏ hẳn bước xác nhận vì
// `window.confirm()` treo tab, với lý do "Đồng ý đặt hàng" cạnh đó cũng
// không hỏi. Nửa đầu đúng (không quay lại window.confirm), nửa sau sai:
// "Đồng ý đặt hàng" là bước TIẾN TỚI, còn nút này đặt `rate` các dòng đã
// đổi về 0 và đẩy đơn về "Chờ xác nhận" — bấm nhầm là khách MẤT báo giá
// đang có. Việc gây mất mát cần xác nhận. Dùng lại ĐÚNG khuôn `ReasonModal`
// mà "Huỷ đơn" đang dùng (`minLen: 0` — không bắt nhập lý do, chỉ cần một
// bước xác nhận trong modal của app, không phải dialog gốc trình duyệt).
const guiLaiOpen = ref(false)
// Task 4 — `KhoiBaoGia` đã validate + tính sẵn phần chênh lệch (item_code/
// name + qty mới) trước khi phát `sua-so-luong`; ở đây chỉ CẤT payload đó
// chờ khách xác nhận trong modal, không tính lại từ ref cục bộ nữa (những
// ref đó đã chuyển sang component con).
const dongGuiLai = ref({ items: [], dat_ngoai: [] })

// Task 4 — trước bản này `moGuiLai()` (validate rồi mở modal) và
// `guiLaiBaoGia()` (tính chênh lệch rồi gọi API) đứng CHUNG một file, cùng
// đọc `soLuongMoiItems`/`soLuongMoiDatNgoai`. Việc validate + tính chênh
// lệch đã chuyển sang `KhoiBaoGia.moGuiLai()` (khác hàm cùng tên ở đây, xem
// file đó); hàm này chỉ còn NHẬN payload qua sự kiện `sua-so-luong` rồi mở
// modal xác nhận — đúng vị trí `moGuiLai()` cũ đứng trong luồng UI.
function nhanSuaSoLuong(dong) {
  dongGuiLai.value = dong
  guiLaiOpen.value = true
}

async function guiLaiBaoGia() {
  if (dangSuaSoLuong.value) return
  const { items: doiItems, dat_ngoai: doiDatNgoai } = dongGuiLai.value
  if (!doiItems.length && !doiDatNgoai.length) {
    guiLaiOpen.value = false
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  dangSuaSoLuong.value = true
  try {
    await api.call('portal_order_sua_so_luong', {
      order: name.value,
      dong: JSON.stringify({ items: doiItems, dat_ngoai: doiDatNgoai }),
    })
    guiLaiOpen.value = false
    showToast('Đã gửi số lượng mới — đơn chuyển sang chờ Miyano báo giá lại.')
    load()
  } catch (e) {
    showToast(e.message || 'Không gửi được thay đổi số lượng. Vui lòng thử lại.', 'error')
  } finally {
    dangSuaSoLuong.value = false
  }
}

// Việc 2/brief 2026-08-15 — nút Huỷ = HUỶ THẬT, đơn đóng ngay (khác hẳn
// `requestCancel`/`portal_request_cancel` bên dưới — chỉ ghi yêu cầu chờ
// nhân viên xử lý, dùng cho đơn ĐÃ XÁC NHẬN).
async function huyDon(lyDo) {
  if (huyDangGui.value) return
  huyDangGui.value = true
  try {
    await api.call('portal_order_huy', { order: name.value, ly_do: lyDo })
    huyOpen.value = false
    showToast('Đã huỷ đơn hàng theo yêu cầu của bạn.')
    load()
  } catch (e) {
    showToast(e.message || 'Không huỷ được đơn. Vui lòng thử lại.', 'error')
  } finally {
    huyDangGui.value = false
  }
}

// E6/F-07 [MỚI — QĐ-6] — "Chờ bạn đồng ý" (pg-accept trong prototype). Nằm
// TRONG chi tiết đơn (không phải trang riêng): backend mô hình hoá đây là
// một trạng thái của CHÍNH Sales Order (`workflow_state`), lộ ra qua
// `portal_order_track().chap_nhan` — không phải một chứng từ khác.
async function dongY() {
  if (accepting.value) return
  accepting.value = true
  try {
    await api.call('portal_order_accept', { order: name.value, action: 'dong_y' })
    showToast('Đã đồng ý — đơn chuyển sang chờ Miyano xác nhận.')
    load()
  } catch (e) {
    showToast(e.message || 'Không ghi nhận được đồng ý. Vui lòng thử lại.', 'error')
  } finally {
    accepting.value = false
  }
}
async function khongDongY(lyDo) {
  if (rejecting.value) return
  rejecting.value = true
  try {
    await api.call('portal_order_accept', { order: name.value, action: 'khong_dong_y', ly_do: lyDo })
    acceptOpen.value = false
    showToast('Đã gửi phản hồi không đồng ý — Miyano sẽ liên hệ lại.')
    load()
  } catch (e) {
    showToast(e.message || 'Không gửi được phản hồi. Vui lòng thử lại.', 'error')
  } finally {
    rejecting.value = false
  }
}

async function requestCancel() {
  const reason = window.prompt('Lý do yêu cầu huỷ / sửa đơn:')
  if (!reason) return
  try {
    await api.call('portal_request_cancel', { order: name.value, reason })
    window.alert('Đã gửi yêu cầu huỷ/sửa đơn đến Miyano.')
    load()
  } catch (e) {
    window.alert(e.message || 'Không gửi được yêu cầu.')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <router-link :to="{ name: 'yeu-cau' }" v-if="!isMobile"><button class="btn-o" style="margin-bottom: 8px">← Quay lại</button></router-link>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="sb">
          <b style="font-size: 16px">{{ data.order }}</b>
          <span>
            <!-- Task 6 (QĐ-G3) — nhãn nói đúng thứ đơn này là: đơn CÓ HÀNG
                 CHỜ BÁO GIÁ (nên cả đơn đi qua vòng báo giá của Miyano),
                 không phải "đơn mua lẻ". -->
            <span v-if="coHangChoBaoGia" class="badge b-purple">Có hàng chờ báo giá</span>
            <!-- `status_vi` (từ trạng thái ERPNext gốc) không phân biệt được
                 "Chờ bạn đồng ý" với "Chờ xác nhận" thường — cả hai đều là
                 SO nháp (Draft, chưa giao gì). `chap_nhan.can_dong_y` (suy từ
                 workflow_state thật) mới là tín hiệu đúng, ưu tiên hiển thị
                 badge này khi có. -->
            <span v-if="data.chap_nhan && data.chap_nhan.can_dong_y" class="badge b-yellow" style="margin-left: 4px">Chờ bạn đồng ý</span>
            <span v-else class="badge" :class="statusBadge(data.status_vi)" style="margin-left: 4px">{{ data.status_vi }}</span>
          </span>
        </div>
        <p class="tag" style="margin-top: 4px">
          Đặt ngày {{ fmtDate(data.order_date) }}
          <template v-if="data.hdnt"> · {{ data.hdnt }}</template>
          <template v-if="data.po_khach"> · Số dự trù: {{ data.po_khach }}</template>
        </p>
        <p v-if="data.ly_do_tu_choi" class="tag" style="color: var(--red); margin-top: 4px">
          Lý do từ chối: {{ data.ly_do_tu_choi }}
        </p>
      </div>

      <!-- E6/F-07 [MỚI — QĐ-6] — banner "Chờ bạn đồng ý" -->
      <!-- Task 4/ruling — banner + khối sửa số lượng chuyển vào KhoiBaoGia;
           ba nút hành động (Đồng ý/Không đồng ý/Huỷ đơn) VẪN do
           OrderDetail.vue render (registry Task 3 + thanh hành động Task 7
           thay thế sau), qua hai slot đúng vị trí flex cũ — không phải một
           nút bị rớt lại ngoài ý muốn. -->
      <KhoiBaoGia
        v-if="data.chap_nhan && data.chap_nhan.can_dong_y"
        :don="data"
        :dang-gui="dangSuaSoLuong"
        @sua-so-luong="nhanSuaSoLuong"
      >
        <template #hanh-dong>
          <button class="btn-g" :disabled="accepting" @click="dongY">
            {{ accepting ? 'Đang gửi…' : '✔ Đồng ý đặt hàng' }}
          </button>
          <button class="btn-o btn-danger" :disabled="accepting" @click="acceptOpen = true">✕ Không đồng ý…</button>
        </template>
        <template #huy>
          <button class="btn-o btn-danger" :disabled="huyDangGui" @click="huyOpen = true">
            🗑 Huỷ đơn…
          </button>
        </template>
      </KhoiBaoGia>

      <!-- Tiến trình -->
      <KhoiTienTrinh :milestones="data.milestones" />

      <div class="grid2">
        <!-- Mặt hàng -->
        <div v-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>MÃ</th><th>TÊN VẬT TƯ</th><th>ĐVT</th><th class="right">SL đặt</th>
                <th class="right">Đã giao</th><th class="right">Đơn giá</th><th class="right">Thành tiền</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in data.items" :key="it.item_code">
                <td><b>{{ it.item_code }}</b></td>
                <td>{{ it.item_name }}</td>
                <td>{{ it.uom }}</td>
                <td class="right">{{ it.qty }}</td>
                <td class="right">{{ it.delivered_qty }}</td>
                <td class="right">{{ fmtVND(it.rate) }}</td>
                <td class="right">{{ fmtVND(it.amount) }}</td>
              </tr>
            </tbody>
          </table>

          <!-- review I-4 — dòng ĐÃ khớp mã (`da_xu_ly=1`) hiện CÙNG NHÓM
               "hàng có mã" ở trên, không còn nằm dưới tiêu đề "Đang chờ".
               Ghi chú "(từ yêu cầu: …)" giữ nguyên tên khách gõ để đối
               chiếu; `item_khop` là mã Miyano đã tìm được. -->
          <template v-if="datNgoaiDaKhop.length">
            <h4 style="margin: 14px 12px 6px">Đã khớp mã (từ yêu cầu đặt ngoài)</h4>
            <table>
              <thead>
                <tr><th>Mã đã khớp</th><th>Yêu cầu của bạn</th><th>ĐVT</th><th class="right">SL</th></tr>
              </thead>
              <tbody>
                <tr v-for="(d, i) in datNgoaiDaKhop" :key="'khop-' + i">
                  <td><b>{{ d.item_khop }}</b> <span class="badge b-green">Đã tìm được nguồn</span></td>
                  <td>
                    <span class="tag">(từ yêu cầu: {{ d.ten_hang }})</span>
                    <template v-if="d.ghi_chu"><br /><span class="tag">{{ d.ghi_chu }}</span></template>
                  </td>
                  <td>{{ d.dvt }}</td>
                  <td class="right">{{ d.so_luong }}</td>
                </tr>
              </tbody>
            </table>
          </template>

          <template v-if="datNgoaiChoXuLy.length">
            <h4 style="margin: 14px 12px 6px">Đang chờ Miyano xác nhận nguồn</h4>
            <table>
              <thead>
                <tr><th>Tên hàng</th><th>ĐVT</th><th class="right">SL</th><th>Tình trạng</th></tr>
              </thead>
              <tbody>
                <tr v-for="(d, i) in datNgoaiChoXuLy" :key="i">
                  <td>{{ d.ten_hang }}<br /><span v-if="d.ghi_chu" class="tag">{{ d.ghi_chu }}</span></td>
                  <td>{{ d.dvt }}</td>
                  <td class="right">{{ d.so_luong }}</td>
                  <td><span class="badge b-gray">Miyano đang tìm nguồn</span></td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
        <div v-else class="card">
          <div class="h3">Mặt hàng</div>
          <div v-for="it in data.items" :key="it.item_code" class="rowline">
            <span>
              <b>{{ it.item_code }}</b>
              <template v-if="it.item_name"><br /><span style="font-size: 13px">{{ it.item_name }}</span></template><br />
              <span class="tag">{{ it.qty }} {{ it.uom }} × {{ fmtVND(it.rate) }} · đã giao {{ it.delivered_qty }}</span>
            </span>
            <b>{{ fmtVND(it.amount) }}</b>
          </div>

          <!-- review I-4 — cùng logic tách theo `da_xu_ly` như bản desktop. -->
          <template v-if="datNgoaiDaKhop.length">
            <h4 style="margin: 14px 0 6px">Đã khớp mã (từ yêu cầu đặt ngoài)</h4>
            <div v-for="(d, i) in datNgoaiDaKhop" :key="'khop-' + i" class="rowline">
              <span>
                <b>{{ d.item_khop }}</b>
                <br /><span style="font-size: 13px">(từ yêu cầu: {{ d.ten_hang }})</span>
                <template v-if="d.ghi_chu"><br /><span style="font-size: 13px">{{ d.ghi_chu }}</span></template><br />
                <span class="tag">{{ d.so_luong }} {{ d.dvt }}</span>
              </span>
              <span class="badge b-green">Đã tìm được nguồn</span>
            </div>
          </template>

          <template v-if="datNgoaiChoXuLy.length">
            <h4 style="margin: 14px 0 6px">Đang chờ Miyano xác nhận nguồn</h4>
            <div v-for="(d, i) in datNgoaiChoXuLy" :key="i" class="rowline">
              <span>
                <b>{{ d.ten_hang }}</b>
                <template v-if="d.ghi_chu"><br /><span style="font-size: 13px">{{ d.ghi_chu }}</span></template><br />
                <span class="tag">{{ d.so_luong }} {{ d.dvt }}</span>
              </span>
              <span class="badge b-gray">Miyano đang tìm nguồn</span>
            </div>
          </template>
        </div>

        <!-- Giao hàng -->
        <!-- Task 4 — MỘT `.card` chung cho KhoiGiaoHang + KhoiHoaDonTaiLieu +
             nút Huỷ/Sửa đơn (giữ ở OrderDetail.vue, xem ruling Bước 6), để
             `grid2` không có thêm con và bố cục không đổi. -->
        <div class="card">
          <KhoiGiaoHang :don="data" />
          <KhoiHoaDonTaiLieu :don="data" :dang-dat-lai="dangDatLai" @dat-lai="datLai" />
          <!-- Ẩn khi đang "Chờ bạn đồng ý": hai bộ hành động (Đồng ý/Không
               đồng ý ở banner trên và Huỷ/Sửa đơn ở đây) cùng hiện sẽ tranh
               nhau — báo giá tự có đường "Không đồng ý" riêng, không cần
               thêm nút Huỷ/Sửa. -->
          <button
            v-if="data.status_vi === 'Chờ xác nhận' && !(data.chap_nhan && data.chap_nhan.can_dong_y)"
            class="btn-o btn-sm"
            style="margin-left: 8px; color: var(--red); border-color: var(--red)"
            @click="requestCancel"
          >
            Huỷ / Sửa đơn
          </button>
        </div>
      </div>
    </template>

    <!-- controller ruling 2026-08-16 — "Gửi lại để báo giá" đặt rate về 0 và
         đẩy đơn về sales; cần một bước xác nhận (khác "Đồng ý đặt hàng", vốn
         là bước tiến tới). `min-len="0"` — không bắt nhập lý do, chỉ xác
         nhận trong đúng khuôn modal của app. -->
    <ReasonModal
      :open="guiLaiOpen"
      title="Gửi lại để báo giá"
      desc="Số lượng dòng đã đổi sẽ về giá 0 và đơn chuyển về 'Chờ xác nhận' để Miyano báo giá lại — báo giá hiện tại của các dòng đó KHÔNG còn hiệu lực. Bấm Xác nhận để tiếp tục."
      :min-len="0"
      :submitting="dangSuaSoLuong"
      submit-label="Xác nhận gửi lại"
      @close="guiLaiOpen = false"
      @submit="guiLaiBaoGia"
    />

    <ReasonModal
      :open="acceptOpen"
      title="Không đồng ý báo giá"
      placeholder="VD: Giá cao hơn dự toán, đề nghị xem lại..."
      :submitting="rejecting"
      submit-label="Gửi"
      @close="acceptOpen = false"
      @submit="khongDongY"
    />

    <!-- Việc 2/brief 2026-08-15 — Huỷ đơn = HUỶ THẬT, cần lý do (>= 10 ký
         tự, khớp `LY_DO_TOI_THIEU_KHACH` phía server). -->
    <ReasonModal
      :open="huyOpen"
      title="Huỷ đơn hàng"
      desc="Đơn sẽ ĐÓNG NGAY, không thể hoàn tác từ phía khách. Vui lòng nêu lý do (≥ 10 ký tự) — được gửi kèm email cho Miyano."
      placeholder="VD: Đặt nhầm số lượng, không còn nhu cầu..."
      :submitting="huyDangGui"
      submit-label="Xác nhận huỷ"
      @close="huyOpen = false"
      @submit="huyDon"
    />
  </div>
</template>
