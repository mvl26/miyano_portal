<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, statusBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import { showToast } from '../toast'
import ReasonModal from '../components/ReasonModal.vue'
import HoaDonNhap from '../components/HoaDonNhap.vue'

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

// E6/F-07 [MỚI — QĐ-6] — "Đơn mua lẻ": `portal_order_track` giờ trả THẲNG
// `loai_don` (thêm ở review E6 phần B round 1, dọn dẹp ở round 2). Bản
// trước không có field này nên phải suy bằng heuristic "không gắn HĐNT nào"
// (`!data.value.hdnt`) — đúng cho MỌI đơn đi qua `portal_order_place`
// nhưng có thể sai với một đơn dựng tay trên Desk không gắn HĐNT vì lý do
// khác. Đọc field thật, không còn đoán.
const laDonMuaLe = computed(() => data.value?.loai_don === 'Mua lẻ')

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

// Việc 1/brief 2026-08-15 (bao-gia-hai-chieu) — khách sửa số lượng ngay
// trong khối "Chờ bạn đồng ý". Hai map RIÊNG (items theo item_code,
// dat_ngoai theo `name`) — khớp đúng khoá endpoint `portal_order_sua_so_
// luong` dùng để tìm dòng ĐÃ CÓ trên đơn (server chỉ đọc item_code/name +
// qty, mọi field khác trong payload đều bị bỏ qua/từ chối).
const soLuongMoiItems = ref({})
const soLuongMoiDatNgoai = ref({})
const dangSuaSoLuong = ref(false)
function initSoLuongMoi() {
  soLuongMoiItems.value = Object.fromEntries((data.value?.items || []).map((it) => [it.item_code, it.qty]))
  soLuongMoiDatNgoai.value = Object.fromEntries((data.value?.dat_ngoai || []).map((d) => [d.name, d.so_luong]))
}

const huyOpen = ref(false)
const huyDangGui = ref(false)

// Bước hiện tại = mốc đầu tiên chưa hoàn thành (để tô cam như mockup).
const currentIdx = computed(() => {
  if (!data.value) return -1
  const i = data.value.milestones.findIndex((m) => !m.done)
  return i
})
function stepClass(m, idx) {
  if (m.done) return 'done'
  if (idx === currentIdx.value) return 'cur'
  return ''
}

// UC-14 — điền lại giỏ theo đơn cũ, theo giá hiện hành.
async function datLai() {
  if (dangDatLai.value) return
  dangDatLai.value = true
  try {
    const res = await api.call('portal_reorder', { order: name.value })
    if (!res.gio_hang.length) {
      showToast('Không mặt hàng nào của đơn này còn đặt lại được.', 'error')
      return
    }
    store.napGio(res.gio_hang)
    if (data.value?.hdnt) store.setContract(data.value.hdnt)
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
    router.push('/cart')
  } catch (e) {
    showToast(e.message || 'Không đặt lại được đơn này.', 'error')
  } finally {
    dangDatLai.value = false
  }
}

// E9 — màu badge trạng thái biên bản kiểm hàng. Cùng bảng màu với
// KiemHang.vue; giữ hai bản vì hai màn đọc hai nguồn khác nhau và một import
// chéo giữa hai view chỉ vì bảy dòng ánh xạ là một cạnh phụ thuộc không đáng.
const KIEM_HANG_BADGE = {
  'Chờ xử lý': 'b-orange',
  'Đã xác nhận': 'b-green',
  'Đã duyệt trả': 'b-blue',
  'Đã thu hồi': 'b-green',
  'Đã xử lý': 'b-green',
  'Từ chối': 'b-red',
}
function kiemHangBadge(tt) {
  return KIEM_HANG_BADGE[tt] || 'b-gray'
}

// --- Hoá đơn nháp đính theo phiếu giao (E7b) --------------------------------
// Cờ `d.co_hoa_don_nhap` đi sẵn trong `portal_order_track`; NỘI DUNG chỉ nạp
// khi khách bấm xem — khác khối HĐĐT ở trang Hoá đơn (nhúng sẵn): ở đây có
// thể có nhiều đợt giao, nhét sẵn dòng hàng của mọi bản nháp vào response chi
// tiết đơn là trả về một đống dữ liệu hầu như không ai mở tới.
const nhapMo = ref(null)
const nhapData = ref({})
const nhapDangTai = ref(null)

async function toggleNhap(dnName) {
  if (nhapMo.value === dnName) {
    nhapMo.value = null
    return
  }
  nhapMo.value = dnName
  if (dnName in nhapData.value) return
  nhapDangTai.value = dnName
  try {
    const khoi = await api.call('portal_einvoice_nhap', { delivery_note: dnName })
    nhapData.value = { ...nhapData.value, [dnName]: khoi }
  } catch (e) {
    showToast(e.message || 'Không xem được hoá đơn nháp.', 'error')
    nhapMo.value = null
  } finally {
    nhapDangTai.value = null
  }
}

function urlPdfNhap(dnName) {
  const khoi = nhapData.value[dnName]
  if (!khoi || !khoi.nhap_tai_duoc) return ''
  return (
    '/api/method/miyano_portal.api.portal.portal_einvoice_nhap_pdf?delivery_note=' +
    encodeURIComponent(dnName)
  )
}

// M3 (E3 phần B review): `so_dot` (BR-K16 — thứ tự DN ĐÃ GHI SỔ của SO) và
// chỉ số mảng `i+1` KHÔNG PHẢI luôn cùng một con số — `data.deliveries` lọc
// docstatus < 2 (GỒM CẢ DN nháp chưa ghi sổ), còn so_dot chỉ đếm DN đã ghi
// sổ (docstatus=1). Một đơn có DN đang soạn (nháp) xen giữa hai DN đã ghi
// sổ sẽ khiến "Đợt {{i+1}}" và so_dot lệch nhau ngay trên cùng màn hình.
// Dùng so_dot khi có (khách có kho, DN đã ghi sổ); chỉ số mảng chỉ còn là
// phương án dự phòng khi chưa có mốc nào (khách không có kho, hoặc DN còn
// nháp — chưa từng qua delivery_hook).
function dotLabel(d, i) {
  return d.so_dot || i + 1
}

function pdfUrl(doctype, docname) {
  return (
    '/api/method/miyano_portal.api.portal.portal_document_download?doctype=' +
    encodeURIComponent(doctype) +
    '&name=' +
    encodeURIComponent(docname)
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.call('portal_order_track', { order: name.value })
    initSoLuongMoi()
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

function moGuiLai() {
  const coDoi =
    (data.value.items || []).some(
      (it) => Number(soLuongMoiItems.value[it.item_code]) !== Number(it.qty)
    ) ||
    (data.value.dat_ngoai || []).some(
      (d) => Number(soLuongMoiDatNgoai.value[d.name]) !== Number(d.so_luong)
    )
  if (!coDoi) {
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  guiLaiOpen.value = true
}

async function guiLaiBaoGia() {
  if (dangSuaSoLuong.value) return
  const doiItems = (data.value.items || [])
    .filter((it) => Number(soLuongMoiItems.value[it.item_code]) !== Number(it.qty))
    .map((it) => ({ item_code: it.item_code, qty: Number(soLuongMoiItems.value[it.item_code]) }))
  const doiDatNgoai = (data.value.dat_ngoai || [])
    .filter((d) => Number(soLuongMoiDatNgoai.value[d.name]) !== Number(d.so_luong))
    .map((d) => ({ name: d.name, qty: Number(soLuongMoiDatNgoai.value[d.name]) }))
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
        <router-link to="/orders" v-if="!isMobile"><button class="btn-o" style="margin-bottom: 8px">← Quay lại</button></router-link>
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
            <span v-if="laDonMuaLe" class="badge b-purple">Mua lẻ</span>
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
      <div v-if="data.chap_nhan && data.chap_nhan.can_dong_y" class="card mb10" style="margin-bottom: 14px">
        <div class="note" style="background: #fff7ed; border-color: #fed7aa; color: #9a3412">
          ⏳ <b>Báo giá hiệu lực đến {{ fmtDate(data.chap_nhan.han_hieu_luc) }}.</b>
          Sau ngày này đơn tự đóng — cần hàng phải yêu cầu báo giá lại. <span class="newtag">MỚI</span>
        </div>
        <p style="font-size: 13px; margin: 8px 0 10px">
          Bấm <b>Đồng ý</b> = chấp nhận đặt hàng theo giá trên. Hệ thống ghi lại người bấm và thời điểm.
        </p>
        <div class="flex" style="flex-wrap: wrap">
          <button class="btn-g" :disabled="accepting" @click="dongY">
            {{ accepting ? 'Đang gửi…' : '✔ Đồng ý đặt hàng' }}
          </button>
          <button class="btn-o btn-danger" :disabled="accepting" @click="acceptOpen = true">✕ Không đồng ý…</button>
          <a
            class="btn-o"
            :href="`/api/method/miyano_portal.api.portal.portal_bao_gia_pdf?order=${encodeURIComponent(name)}`"
            target="_blank"
            rel="noopener"
          >⬇ Tải báo giá (PDF)</a>
        </div>

        <!-- Việc 1/brief 2026-08-15 — sửa số lượng NGAY tại đây, chỉ cho
             đơn Mua lẻ (đúng điều kiện server `portal_order_sua_so_luong`
             đòi `custom_loai_don == "Mua lẻ"`). Đơn giá cho N hộp không còn
             đúng ở M hộp — gửi lại là để sales báo giá lại, KHÔNG giữ giá
             cũ (server tự đặt rate = 0 cho dòng đã đổi). -->
        <div v-if="laDonMuaLe" style="margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px">
          <p style="font-size: 13px; margin-bottom: 8px">
            Số lượng chưa đúng? Sửa rồi bấm <b>Gửi lại để báo giá</b> — đơn sẽ
            về Miyano báo giá lại theo số lượng mới (giá hiện tại của dòng đã
            đổi không còn áp dụng).
          </p>
          <div v-for="it in data.items" :key="'sl-' + it.item_code" class="rowline">
            <span>
              <b>{{ it.item_code }}</b> — {{ it.item_name }}
              <br /><span class="tag">{{ it.uom }} · hiện {{ it.qty }} · {{ fmtVND(it.rate) }}/{{ it.uom }}</span>
            </span>
            <input
              type="number" min="0" step="any"
              v-model.number="soLuongMoiItems[it.item_code]"
              style="width: 90px; text-align: right"
            />
          </div>
          <div v-for="d in data.dat_ngoai" :key="'sl-dn-' + d.name" class="rowline">
            <span>
              <b>{{ d.ten_hang }}</b>
              <br /><span class="tag">{{ d.dvt }} · hiện {{ d.so_luong }} (đặt ngoài)</span>
            </span>
            <input
              type="number" min="0" step="any"
              v-model.number="soLuongMoiDatNgoai[d.name]"
              style="width: 90px; text-align: right"
            />
          </div>
          <button class="btn-o" style="margin-top: 8px" :disabled="dangSuaSoLuong" @click="moGuiLai">
            {{ dangSuaSoLuong ? 'Đang gửi…' : '✎ Gửi lại để báo giá' }}
          </button>
        </div>

        <!-- Việc 2/brief 2026-08-15 — Huỷ đơn = HUỶ THẬT (khác requestCancel
             bên dưới — đó chỉ ghi yêu cầu chờ xử lý, dùng cho đơn đã xác
             nhận). Áp cho MỌI loại đơn đang ở trạng thái này (server không
             giới hạn theo custom_loai_don), không chỉ Mua lẻ. -->
        <div style="margin-top: 10px; border-top: 1px solid var(--line); padding-top: 10px">
          <button class="btn-o btn-danger" :disabled="huyDangGui" @click="huyOpen = true">
            🗑 Huỷ đơn…
          </button>
        </div>
      </div>

      <!-- Tiến trình -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="h3">Tiến trình</div>
        <!-- desktop: ngang -->
        <div v-if="!isMobile" class="tl">
          <div v-for="(m, i) in data.milestones" :key="m.key" class="st" :class="stepClass(m, i)">
            <div class="dot">{{ m.done ? '✓' : i + 1 }}</div>
            <div class="lb">{{ m.label }}</div>
          </div>
        </div>
        <!-- mobile: dọc -->
        <div v-else class="vtl">
          <div v-for="(m, i) in data.milestones" :key="m.key" class="vst" :class="stepClass(m, i)">
            <div class="vdot">{{ m.done ? '✓' : i + 1 }}</div>
            <div class="vlb"><b>{{ m.label }}</b>{{ m.done ? 'Hoàn thành' : (i === currentIdx ? 'Đang thực hiện' : 'Chưa thực hiện') }}</div>
          </div>
        </div>
      </div>

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
        <div class="card">
          <div class="h3">Giao hàng</div>
          <!-- Miyano hẹn lại lịch giao (2026-08-16). Đặt Ở ĐẦU khối giao
               hàng: khi có lời hẹn thì đó là thứ khách vào trang này để đọc,
               không phải danh sách đợt đã giao. -->
          <div
            v-if="data.hen_giao"
            style="border: 1px solid var(--orange); border-radius: 8px; padding: 10px; margin-bottom: 12px"
          >
            <p style="margin: 0 0 4px">
              <span class="badge b-orange">{{ data.hen_giao.loai }}</span>
              <b style="margin-left: 8px">Dự kiến giao {{ fmtDate(data.hen_giao.ngay) }}</b>
            </p>
            <p v-if="data.hen_giao.ly_do" class="tag" style="margin: 0">
              {{ data.hen_giao.ly_do }}
            </p>
          </div>
          <template v-if="data.deliveries.length">
            <div v-for="(d, i) in data.deliveries" :key="d.name" style="margin-bottom: 12px">
              <p style="font-size: 13px"><b>Đợt {{ dotLabel(d, i) }} – {{ fmtDate(d.posting_date) }} ({{ d.percent }}%)</b></p>
              <p class="tag">
                Phiếu giao: {{ d.name }}
                <template v-if="d.carrier"> · {{ d.carrier }}</template>
                <template v-if="d.awb"> · Vận đơn: {{ d.awb }}</template>
              </p>
              <!-- US-E3.4 (F-07 khối đợt giao) — chỉ hiện khi khách có kho
                   (server chỉ trả d.phieu_nhap trong trường hợp đó). -->
              <p v-if="d.phieu_nhap" class="tag" style="margin-top: 2px">
                Phiếu nhập:
                <router-link
                  v-if="d.phieu_nhap.trang_thai === 'Nháp'"
                  :to="`/kho/nhap/${d.phieu_nhap.name}`"
                  style="text-decoration: underline"
                >
                  {{ d.phieu_nhap.name }} — Nháp, chờ kiểm nhận
                </router-link>
                <span v-else-if="d.phieu_nhap.co_chenh_lech" style="color: var(--red); font-weight: 600">
                  {{ d.phieu_nhap.name }} — Có chênh lệch ⚠
                </span>
                <span v-else>{{ d.phieu_nhap.name }} — Đã ghi sổ</span>
              </p>
              <!-- E9 (2026-08-16) — kiểm hàng khi nhận. KHÔNG gắn với việc
                   khách có kho hay không: `d.kiem_hang` luôn có mặt trên mọi
                   đợt giao, `null` nghĩa là khách chưa lập biên bản. -->
              <p class="tag" style="margin-top: 4px">
                <template v-if="d.kiem_hang">
                  Kiểm hàng:
                  <router-link :to="`/kiem-hang/${d.name}`" style="text-decoration: underline">
                    {{ d.kiem_hang.name }}
                  </router-link>
                  <span
                    class="badge"
                    :class="kiemHangBadge(d.kiem_hang.trang_thai)"
                    style="margin-left: 6px"
                  >{{ d.kiem_hang.trang_thai }}</span>
                </template>
                <template v-else>
                  <router-link :to="`/kiem-hang/${d.name}`">
                    <button class="btn-o btn-sm">Kiểm hàng đợt này</button>
                  </router-link>
                </template>
              </p>

              <!-- E7b — hoá đơn nháp lập từ chính phiếu giao này. Neo ở đây
                   chứ không ở trang Hoá đơn: chứng từ HĐĐT sinh từ phiếu giao
                   có thể chưa có Sales Invoice nào để bám vào. -->
              <template v-if="d.co_hoa_don_nhap">
                <p class="tag" style="margin-top: 4px">
                  <span class="badge b-gray">Hoá đơn nháp</span>
                  <button class="btn-o btn-sm" style="margin-left: 8px" @click="toggleNhap(d.name)">
                    {{ nhapMo === d.name ? '▾ Ẩn hoá đơn nháp' : '▸ Xem hoá đơn nháp' }}
                  </button>
                </p>
                <div
                  v-if="nhapMo === d.name"
                  style="border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-top: 6px"
                >
                  <p v-if="nhapDangTai === d.name" class="tag">Đang tải hoá đơn nháp…</p>
                  <HoaDonNhap
                    v-else-if="nhapData[d.name]"
                    :du-lieu="nhapData[d.name]"
                    :url-pdf="urlPdfNhap(d.name)"
                  />
                  <p v-else class="tag">Phiếu giao này chưa có hoá đơn nháp.</p>
                </div>
              </template>
              <a :href="pdfUrl('Delivery Note', d.name)" target="_blank" rel="noopener">
                <button class="btn-o btn-sm" style="margin-top: 6px">⬇ Phiếu giao đợt {{ dotLabel(d, i) }}</button>
              </a>
            </div>
          </template>
          <p v-else class="tag">Chưa có đợt giao hàng nào.</p>

          <!-- Khoảng trống 2026-08-16 — trước bản này cổng chỉ có mốc "Hoá
               đơn" bật/tắt và một trang Hoá đơn TOÀN CỤC; khách muốn xem hoá
               đơn CỦA ĐƠN NÀY phải tự dò. `data.hoa_don` do
               `portal_order_track` trả về, nối qua Sales Invoice Item. -->
          <template v-if="data.hoa_don && data.hoa_don.length">
            <hr class="sep" />
            <div class="h3">Hoá đơn của đơn này</div>
            <div v-for="h in data.hoa_don" :key="h.name" class="rowline">
              <span>
                <b>{{ h.name }}</b> · {{ fmtDate(h.ngay) }}<br />
                <span class="tag">
                  {{ fmtVND(h.tong_tien) }}
                  <template v-if="h.con_no > 0"> · còn nợ {{ fmtVND(h.con_no) }}</template>
                  <template v-if="h.han_thanh_toan"> · hạn {{ fmtDate(h.han_thanh_toan) }}</template>
                </span>
              </span>
              <a :href="pdfUrl('Sales Invoice', h.name)" target="_blank" rel="noopener">
                <button class="btn-o btn-sm">⬇ PDF</button>
              </a>
            </div>
          </template>

          <hr class="sep" />
          <a :href="pdfUrl('Sales Order', data.order)" target="_blank" rel="noopener">
            <button class="btn-o btn-sm">⬇ PDF đơn hàng</button>
          </a>
          <button
            class="btn-o btn-sm"
            style="margin-left: 8px"
            :disabled="dangDatLai"
            @click="datLai"
          >
            🔁 Đặt lại đơn này
          </button>
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
