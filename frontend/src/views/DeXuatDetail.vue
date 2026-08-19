<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDateTime, deXuatBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import { showToast } from '../toast'
import { hanhDongChoPhep } from '../de-xuat-actions'
import ReasonModal from '../components/ReasonModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const doc = ref(null)
const ten = computed(() => route.params.ten)

const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Best-effort — cùng khuôn DeXuatList.vue: một khách chưa mở kho vẫn
    // phải xem được chi tiết phiếu, chỉ mất phần dịch tên khoa.
  }
}
const tenKhoa = computed(() => {
  if (!doc.value) return ''
  if (!doc.value.khoa_phong) return 'Toàn viện'
  const k = khoaPhongList.value.find((x) => x.name === doc.value.khoa_phong)
  return k ? k.ten_khoa_phong : doc.value.khoa_phong
})

// Toolbar hành động — DỮ LIỆU, không rải v-if khắp template (xem
// de-xuat-actions.js). hanhDongChoPhep() đã tự bọc when() trong try/catch.
const actions = computed(() => hanhDongChoPhep(doc.value, store.me))

async function load() {
  loading.value = true
  error.value = ''
  try {
    doc.value = await api.callDeXuat('de_xuat_chi_tiet', { ten: ten.value })
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết phiếu đề xuất.'
  } finally {
    loading.value = false
  }
}

// M1 (Task 4) — "hạ về 0" chỉ có nghĩa SAU khi quản lý đã thật sự cầm phiếu
// lên xử lý (`_ap_dieu_chinh` chỉ chạy trong đường duyệt). Ở "Nháp"/"Chờ
// duyệt", `so_luong_duyet` mới chỉ là bản sao mặc định của `so_luong_de_
// xuat` (đóng dấu lúc Gửi duyệt) — coi nó là "Không duyệt" ở hai trạng thái
// đó sẽ gắn badge sai cho MỌI dòng của MỌI phiếu chưa ai đụng tới. Máy trạng
// thái (`portal_de_xuat_mua.py` CHUYEN_HOP_LE) chỉ cho "Đã huỷ" đi ra từ
// "Chờ duyệt"/"Từ chối" — không đi qua "Đã duyệt" — nên khỏi cần liệt kê nó.
const daDieuChinh = computed(() => ['Đã duyệt', 'Chờ duyệt sửa'].includes(doc.value?.trang_thai))
function khongDuyet(row) {
  return daDieuChinh.value && Number(row.so_luong_duyet) === 0
}

// Cột "SL xin sửa" chỉ hiện khi phiếu ở "Chờ duyệt sửa" (backend đã đổi mốc
// "chưa có yêu cầu" (-1) thành null ở de_xuat_chi_tiet — chỉ dòng có giá trị
// thật mới hiện số).
const hienCotXinSua = computed(() => doc.value?.trang_thai === 'Chờ duyệt sửa')

// --- Dispatch hành động chung -----------------------------------------
const dangChay = ref('')
const TOAST_THANH_CONG = {
  de_xuat_xoa_nhap: 'Đã xoá phiếu.',
  de_xuat_duyet_phieu: 'Đã duyệt phiếu — đơn hàng đã được tạo.',
  de_xuat_tu_choi: 'Đã từ chối phiếu.',
  de_xuat_huy: 'Đã huỷ phiếu.',
  de_xuat_duyet_sua: 'Đã đồng ý sửa số lượng — đơn hàng đã cập nhật.',
  de_xuat_tu_choi_sua: 'Đã từ chối yêu cầu xin sửa.',
}

async function chayHanhDong(action, extraArgs) {
  if (dangChay.value) return
  dangChay.value = action.method
  try {
    await api.callDeXuat(action.method, { ten: ten.value, ...(extraArgs || {}) })
    showToast(TOAST_THANH_CONG[action.method] || `Đã ${action.label}.`)
    // Xoá nháp thì phiếu không còn tồn tại nữa — quay lại danh sách thay vì
    // tải lại một chi tiết đã bị xoá.
    if (action.method === 'de_xuat_xoa_nhap') {
      router.push('/de-xuat')
    } else {
      argModalAction.value = null
      await load()
    }
  } catch (e) {
    showToast(e.message || 'Không thực hiện được thao tác này.', 'error')
  } finally {
    dangChay.value = ''
  }
}

// Hành động có `args` (hiện chỉ một textarea bắt buộc — Từ chối/Không đồng ý
// sửa) → mở modal chung trước khi gọi, kiểm required qua chính ReasonModal.
const argModalAction = ref(null)
function onSubmitArgModal(gia_tri) {
  const key = argModalAction.value.args[0].key
  chayHanhDong(argModalAction.value, { [key]: gia_tri })
}

// Ruling coordinator (1) — nút "Gửi duyệt" KHÔNG ẩn dù `ly_do_yeu_cau` trống
// (when() của registry không phản ánh điều kiện này). Bấm mà thiếu lý do →
// mở modal hỏi lý do (bắt buộc), lưu qua `de_xuat_luu_nhap` rồi mới gửi —
// KHÔNG hỏi lại nếu phiếu đã có lý do từ trước.
const lyDoYeuCauOpen = ref(false)
const dangLuuLyDo = ref(false)
function nhanGuiDuyet(action) {
  if ((doc.value?.ly_do_yeu_cau || '').trim()) {
    chayHanhDong(action)
    return
  }
  lyDoYeuCauOpen.value = true
}
async function xacNhanLyDoRoiGui(lyDo) {
  dangLuuLyDo.value = true
  try {
    await api.callDeXuat('de_xuat_luu_nhap', { ten: ten.value, ly_do_yeu_cau: lyDo })
    lyDoYeuCauOpen.value = false
    await chayHanhDong({ method: 'de_xuat_gui_duyet', label: 'Gửi duyệt' })
  } catch (e) {
    showToast(e.message || 'Không lưu được lý do yêu cầu.', 'error')
  } finally {
    dangLuuLyDo.value = false
  }
}

// Ruling coordinator (2) — "Xin sửa số lượng" không khớp khuôn args (đầu
// vào là NHIỀU dòng số lượng, không phải một ô lý do), nên xử lý RIÊNG ở
// đây thay vì đi qua `argModalAction`. Chỉ đề nghị sửa những dòng ĐANG NẰM
// trên đơn (`so_luong_duyet > 0`) — dòng quản lý đã hạ về 0 không còn trên
// Sales Order, xin sửa nó chỉ nhận lỗi "không còn trên đơn" từ server.
const xinSuaOpen = ref(false)
const xinSuaSoLuong = ref({})
const xinSuaDangGui = ref(false)
const dongXinSua = computed(() => (doc.value?.items || []).filter((it) => Number(it.so_luong_duyet) > 0))
function moXinSua() {
  xinSuaSoLuong.value = Object.fromEntries(dongXinSua.value.map((it) => [it.item_code, it.so_luong_duyet]))
  xinSuaOpen.value = true
}
async function guiXinSua() {
  if (xinSuaDangGui.value) return
  const doiItems = dongXinSua.value
    .filter((it) => Number(xinSuaSoLuong.value[it.item_code]) !== Number(it.so_luong_duyet))
    .map((it) => ({ item_code: it.item_code, qty: Number(xinSuaSoLuong.value[it.item_code]) }))
  if (!doiItems.length) {
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  xinSuaDangGui.value = true
  try {
    await api.callDeXuat('de_xuat_xin_sua', { ten: ten.value, dong: JSON.stringify({ items: doiItems }) })
    xinSuaOpen.value = false
    showToast('Đã gửi yêu cầu xin sửa số lượng — chờ quản lý duyệt.')
    await load()
  } catch (e) {
    showToast(e.message || 'Không gửi được yêu cầu xin sửa số lượng.', 'error')
  } finally {
    xinSuaDangGui.value = false
  }
}

function onClickAction(action) {
  if (action.method === 'de_xuat_gui_duyet') return nhanGuiDuyet(action)
  if (action.method === 'de_xuat_xin_sua') return moXinSua()
  if (action.args && action.args.length) {
    argModalAction.value = action
    return
  }
  chayHanhDong(action)
}

const VARIANT_CLASS = {
  primary: 'btn',
  success: 'btn-g',
  danger: 'btn-o btn-danger',
  secondary: 'btn-o',
}
function classHanhDong(action) {
  return VARIANT_CLASS[action.variant] || 'btn-o'
}

onMounted(async () => {
  loadKhoaPhongList()
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Không có `me` thì panel hành động rơi về rỗng (hanhDongChoPhep bọc
      // when() trong try/catch) — an toàn hơn là chặn cả màn.
    }
  }
  load()
})
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <router-link to="/de-xuat"><button class="btn-o" style="margin-bottom: 8px">← Quay lại</button></router-link>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="doc">
      <!-- Đầu phiếu: mã + badge trạng thái, khoa phòng, khối truy vết —
           QĐ-KP-9: ba thứ này hiện ngay đầu, không đi tìm trong lịch sử. -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="sb">
          <b style="font-size: 18px">{{ doc.ma_de_xuat || '(chưa gửi duyệt)' }}</b>
          <span class="badge" :class="deXuatBadge(doc.trang_thai)">{{ doc.trang_thai }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">{{ tenKhoa }}</p>

        <div style="margin-top: 12px; border-top: 1px solid var(--line); padding-top: 10px">
          <p class="tag" style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px">
            Truy vết yêu cầu
          </p>
          <p style="font-size: 13px; margin-bottom: 2px">
            <b>Người yêu cầu:</b> {{ doc.nguoi_yeu_cau || doc.owner }}
          </p>
          <p style="font-size: 13px; margin-bottom: 2px">
            <b>Thời điểm gửi:</b> {{ doc.thoi_diem_gui ? fmtDateTime(doc.thoi_diem_gui) : 'Chưa gửi' }}
          </p>
          <p style="font-size: 13px">
            <b>Lý do yêu cầu:</b>
            <span v-if="doc.ly_do_yeu_cau"> {{ doc.ly_do_yeu_cau }}</span>
            <span v-else class="tag"> Chưa có</span>
          </p>
        </div>

        <p v-if="doc.ly_do_tu_choi" class="tag" style="color: var(--red); margin-top: 8px">
          Lý do từ chối: {{ doc.ly_do_tu_choi }}
        </p>

        <!-- Đơn hàng sinh ra từ phiếu — mã tra cứu của khách (`ma_de_xuat`,
             chép sang `custom_ma_tra_cuu` của Sales Order lúc duyệt) hiện
             TRƯỚC, mã hệ thống sau (QĐ-A4). -->
        <p v-if="doc.sales_order" style="font-size: 13px; margin-top: 8px">
          <b>Đơn hàng:</b>
          <router-link :to="`/orders/${doc.sales_order}`" style="text-decoration: underline; margin-left: 4px">
            {{ doc.ma_de_xuat || doc.sales_order }}
            <span v-if="doc.ma_de_xuat" class="tag">({{ doc.sales_order }})</span>
          </router-link>
        </p>
      </div>

      <!-- Panel hành động — render từ hanhDongChoPhep(doc, me). Hide, don't
           disable: khi rỗng thì không hiện khối này luôn. -->
      <div v-if="actions.length" class="card mb10" style="margin-bottom: 14px">
        <div class="flex" style="flex-wrap: wrap">
          <button
            v-for="a in actions"
            :key="a.method"
            :class="classHanhDong(a)"
            :disabled="!!dangChay"
            @click="onClickAction(a)"
          >
            {{ dangChay === a.method ? 'Đang gửi…' : a.label }}
          </button>
        </div>
      </div>

      <!-- Bảng dòng hàng — ba cột số, điểm cốt lõi của màn. -->
      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Mặt hàng</th>
              <th class="right">SL đề xuất</th>
              <th class="right">SL duyệt</th>
              <th v-if="hienCotXinSua" class="right">SL xin sửa</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in doc.items" :key="it.item_code" :style="khongDuyet(it) ? 'text-decoration: line-through; color: var(--gray)' : ''">
              <td>
                <b>{{ it.item_code }}</b>
                <template v-if="it.item_name"> — {{ it.item_name }}</template>
                <span v-if="it.dvt" class="tag"> ({{ it.dvt }})</span>
                <br />
                <span v-if="khongDuyet(it)" class="badge b-red" style="margin-top: 4px">Không duyệt</span>
                <span v-if="it.nguon_dong === 'Quản lý thêm'" class="badge b-purple" style="margin-top: 4px">Quản lý thêm</span>
                <template v-if="it.ghi_chu_quan_ly">
                  <br /><span class="tag">Ghi chú quản lý: {{ it.ghi_chu_quan_ly }}</span>
                </template>
              </td>
              <td class="right" title="Khoá vĩnh viễn từ lúc gửi duyệt">{{ it.so_luong_de_xuat }}</td>
              <td class="right">{{ it.so_luong_duyet }}</td>
              <td v-if="hienCotXinSua" class="right">
                <span v-if="it.so_luong_xin_sua !== null && it.so_luong_xin_sua !== undefined">{{ it.so_luong_xin_sua }}</span>
                <span v-else class="tag">—</span>
              </td>
            </tr>
            <tr v-if="!doc.items || !doc.items.length">
              <td :colspan="hienCotXinSua ? 4 : 3" class="tag">Chưa có dòng hàng nào.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="doc.ghi_chu" class="card mb10" style="margin-top: 14px">
        <div class="h3">Ghi chú</div>
        <p style="font-size: 13px; margin-top: 6px">{{ doc.ghi_chu }}</p>
      </div>
    </template>

    <!-- Ruling coordinator (1) — hỏi lý do yêu cầu khi bấm Gửi duyệt mà
         phiếu chưa có lý do. Server bắt buộc non-empty, không có ngưỡng ký
         tự tối thiểu nào khác — `min-len="1"`. -->
    <ReasonModal
      :open="lyDoYeuCauOpen"
      title="Nhập lý do yêu cầu"
      desc="Lý do yêu cầu là bắt buộc khi gửi duyệt — quản lý sẽ đọc lý do này khi xét phiếu."
      placeholder="VD: Khoa cần bổ sung vật tư tiêu hao cho quý này..."
      :min-len="1"
      :submitting="dangLuuLyDo"
      submit-label="Lưu và gửi duyệt"
      @close="lyDoYeuCauOpen = false"
      @submit="xacNhanLyDoRoiGui"
    />

    <!-- Hành động có `args` dạng một textarea bắt buộc (Từ chối, Không đồng
         ý sửa) — dùng chung một modal, khoá theo `argModalAction`. -->
    <ReasonModal
      :open="!!argModalAction"
      :title="argModalAction ? argModalAction.label : ''"
      :desc="argModalAction ? `${argModalAction.args[0].label} — bắt buộc, được ghi vào phiếu.` : ''"
      :min-len="1"
      :submitting="!!dangChay"
      submit-label="Gửi"
      @close="argModalAction = null"
      @submit="onSubmitArgModal"
    />

    <!-- Ruling coordinator (2) — "Xin sửa số lượng": khoa nhập số mong muốn
         cho từng dòng đang có trên đơn, chỉ những dòng ĐỔI thật mới được
         gửi (khớp `_loc_thay_doi_that` phía server). -->
    <div v-if="xinSuaOpen" :class="isMobile ? 'sheet' : 'modal'" @click.self="xinSuaOpen = false">
      <div class="card" style="width: 520px; max-width: 92vw">
        <h3>Xin sửa số lượng</h3>
        <p class="tag" style="margin: 8px 0 12px">
          Nhập số lượng mong muốn cho từng dòng — chỉ dòng có đổi số mới được gửi. Quản lý sẽ duyệt lại yêu cầu này.
        </p>
        <div v-for="it in dongXinSua" :key="it.item_code" class="rowline">
          <span>
            <b>{{ it.item_code }}</b>
            <template v-if="it.item_name"> — {{ it.item_name }}</template>
            <br /><span class="tag">Đang duyệt: {{ it.so_luong_duyet }} {{ it.dvt }}</span>
          </span>
          <input
            type="number" min="0" step="any"
            v-model.number="xinSuaSoLuong[it.item_code]"
            style="width: 90px; text-align: right"
          />
        </div>
        <p v-if="!dongXinSua.length" class="tag">Không có dòng nào đang trên đơn để xin sửa.</p>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o" :disabled="xinSuaDangGui" @click="xinSuaOpen = false">Quay lại</button>
          <button class="btn" :disabled="xinSuaDangGui" @click="guiXinSua">
            {{ xinSuaDangGui ? 'Đang gửi…' : 'Gửi yêu cầu' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
