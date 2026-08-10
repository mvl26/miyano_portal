<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { phieuActions, trangThaiBadge } from '../kho-actions'
import { useIsMobile } from '../useMobile'
import { useDongPhieu } from '../useDongPhieu'
import VatTuModal from '../components/VatTuModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const DOCTYPE = 'Customer Stock Receipt'
const LOAI_OPTIONS = ['Nhập khác', 'Tồn đầu kỳ', 'Từ đơn hàng Miyano']
// "Phiếu đảo" CỐ Ý không có trong danh sách: backend chặn tự tạo phiếu loại
// này bằng flags.dang_tao_dao (in-memory, không thể forge), nên hiện nó ra
// làm lựa chọn chỉ để rồi báo lỗi khi lưu là đúng kiểu "nút sẽ lỗi khi bấm"
// mà declaring-document-actions cảnh báo.

const isNew = computed(() => route.params.name === 'moi')

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const submitting = ref(false)
const cancelling = ref(false)

const doc = reactive({
  name: '',
  ngay: new Date().toISOString().slice(0, 10),
  loai_nhap: 'Nhập khác',
  nguoi_giao: '',
  chung_tu_kem: '',
  dien_giai: '',
  docstatus: 0,
  tong_tien: 0,
  items: [],
})

const vatTuList = ref([])
const vatTuLoading = ref(true)

// Tạo nhanh vật tư ngay trong ô chọn (mục "➕ Tạo vật tư mới…") VÀ toàn bộ
// luồng import/export Excel của bảng dòng — dùng chung với PhieuXuatDetail,
// xem useDongPhieu.js. Phiếu nhập không cần bước gì thêm sau khi gán vật tư
// nên không truyền onAssigned/onRowImported; điểm riêng của phiếu nhập là
// don_gia/han_su_dung đọc được từ tệp, tiêm vào qua extraRowFields.
const {
  MUC_TAO_MOI,
  modalOpen,
  modalInitial,
  onVatTuSelect,
  onVatTuSaved,
  importing,
  importInput,
  mauUrl,
  exportUrl,
  dongChuaXuLy,
  onImportFile,
  moTaoTuDong,
} = useDongPhieu({
  doc,
  vatTuList,
  loai: 'nhap',
  DOCTYPE,
  extraRowFields: (r) => ({
    han_su_dung: r.han_su_dung || '',
    don_gia: r.don_gia || 0,
  }),
})

const editable = computed(() => isNew.value || doc.docstatus === 0)
const actions = computed(() => phieuActions(doc))
const badge = computed(() => trangThaiBadge(doc.docstatus))

function tenVatTu(vatTu) {
  const vt = vatTuList.value.find((v) => v.name === vatTu)
  return vt ? vt.ten_vat_tu : ''
}
function dvtVatTu(vatTu) {
  const vt = vatTuList.value.find((v) => v.name === vatTu)
  return vt ? vt.dvt : ''
}

function rowThanhTien(row) {
  return (Number(row.so_luong) || 0) * (Number(row.don_gia) || 0)
}
const tongTienPreview = computed(() => doc.items.reduce((s, r) => s + rowThanhTien(r), 0))

function addRow() {
  doc.items.push({ vat_tu: '', so_lo: '', han_su_dung: '', so_luong: 1, don_gia: 0, ghi_chu: '' })
}
function removeRow(idx) {
  doc.items.splice(idx, 1)
}

async function loadVatTu() {
  vatTuLoading.value = true
  try {
    vatTuList.value = await api.callKho('kho_vat_tu_list')
  } catch (e) {
    showToast(e.message || 'Không tải được danh mục vật tư.', 'error')
  } finally {
    vatTuLoading.value = false
  }
}

async function load() {
  if (isNew.value) {
    loading.value = false
    if (!doc.items.length) addRow()
    return
  }
  loading.value = true
  error.value = ''
  try {
    const out = await api.callKho('kho_phieu_get', { doctype: DOCTYPE, name: route.params.name })
    Object.assign(doc, out)
  } catch (e) {
    error.value = e.message || 'Không tải được phiếu nhập.'
  } finally {
    loading.value = false
  }
}

function validateClient() {
  if (!doc.items.length) {
    showToast('Phiếu phải có ít nhất một dòng vật tư.', 'error')
    return false
  }
  for (const [i, r] of doc.items.entries()) {
    if (!r.vat_tu) {
      showToast(`Dòng ${i + 1}: chưa chọn vật tư.`, 'error')
      return false
    }
    if (!r.so_lo) {
      showToast(`Dòng ${i + 1}: chưa nhập số lô.`, 'error')
      return false
    }
    // Dòng đọc từ tệp có thể mang Số lượng ≤ 0 (ô trống thành 0, hoặc số âm).
    // Server đã chặn bằng voucher._check_so_luong; kiểm ở đây để người dùng
    // đang sửa một dòng đỏ tại chỗ biết ngay còn thiếu gì, không phải đợi một
    // vòng gọi mạng.
    if (!(Number(r.so_luong) > 0)) {
      showToast(`Dòng ${i + 1}: số lượng phải lớn hơn 0.`, 'error')
      return false
    }
  }
  return true
}

function payload() {
  const p = {
    ngay: doc.ngay,
    loai_nhap: doc.loai_nhap,
    nguoi_giao: doc.nguoi_giao,
    chung_tu_kem: doc.chung_tu_kem,
    dien_giai: doc.dien_giai,
    items: doc.items.map((r) => ({
      vat_tu: r.vat_tu, so_lo: r.so_lo, han_su_dung: r.han_su_dung || null,
      so_luong: r.so_luong, don_gia: r.don_gia, ghi_chu: r.ghi_chu,
    })),
  }
  if (!isNew.value) p.name = doc.name
  return p
}

async function save({ silent } = {}) {
  if (dongChuaXuLy.value) {
    showToast(`Còn ${dongChuaXuLy.value} dòng lỗi trong tệp chưa được xử lý — chọn vật tư cho dòng đó, hoặc xoá dòng.`, 'error')
    return null
  }
  if (!validateClient()) return null
  saving.value = true
  try {
    const out = await api.callKho('kho_phieu_nhap_save', { payload: payload() })
    Object.assign(doc, out)
    if (isNew.value) {
      router.replace(`/kho/nhap/${out.name}`)
    }
    if (!silent) showToast('Đã lưu phiếu nháp.')
    return out
  } catch (e) {
    showToast(e.message || 'Không lưu được phiếu.', 'error')
    return null
  } finally {
    saving.value = false
  }
}

async function doSubmit() {
  const saved = await save({ silent: true })
  if (!saved) return
  if (!window.confirm(`Ghi sổ phiếu ${saved.name}? Sau khi ghi sổ chỉ có thể huỷ, không sửa được nữa.`)) return
  submitting.value = true
  try {
    const out = await api.callKho('kho_phieu_submit', { doctype: DOCTYPE, name: saved.name })
    Object.assign(doc, out)
    showToast(`Đã ghi sổ phiếu ${out.name}.`)
  } catch (e) {
    showToast(e.message || 'Không ghi sổ được phiếu.', 'error')
  } finally {
    submitting.value = false
  }
}

async function doCancel() {
  if (!window.confirm(`Huỷ phiếu ${doc.name}? Hệ thống sẽ sinh một phiếu đảo để hoàn tồn.`)) return
  cancelling.value = true
  try {
    const out = await api.callKho('kho_phieu_cancel', { doctype: DOCTYPE, name: doc.name })
    Object.assign(doc, out)
    showToast('Đã huỷ phiếu.')
  } catch (e) {
    showToast(e.message || 'Không huỷ được phiếu.', 'error')
  } finally {
    cancelling.value = false
  }
}

const printUrl = computed(
  () =>
    `/api/method/miyano_portal.api.kho.kho_phieu_pdf?doctype=${encodeURIComponent(DOCTYPE)}&name=${encodeURIComponent(doc.name)}`
)

function onAction(key) {
  if (key === 'submit') doSubmit()
  else if (key === 'cancel') doCancel()
  else if (key === 'print') window.open(printUrl.value, '_blank')
}

onMounted(async () => {
  await Promise.all([loadVatTu(), load()])
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>{{ isNew ? 'Tạo phiếu nhập kho' : doc.name }}</h2>
        <div class="sub" v-if="!isNew">
          <span class="badge" :class="badge.cls">{{ badge.label }}</span>
        </div>
      </div>
      <div class="flex" style="gap: 8px">
        <button
          v-for="a in actions"
          :key="a.key"
          class="btn"
          :class="{ 'btn-o': a.variant !== 'primary', 'btn-danger': a.variant === 'danger' }"
          :disabled="submitting || cancelling"
          @click="onAction(a.key)"
        >
          {{ a.label }}
        </button>
        <button v-if="editable" class="btn-o" :disabled="saving" @click="save()">
          {{ saving ? 'Đang lưu…' : 'Lưu nháp' }}
        </button>
        <router-link to="/kho/nhap" class="btn-o">Quay lại</router-link>
      </div>
    </div>
    <div v-else style="margin-bottom: 12px">
      <div class="sb">
        <h2>{{ isNew ? 'Tạo phiếu nhập' : doc.name }}</h2>
        <span v-if="!isNew" class="badge" :class="badge.cls">{{ badge.label }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else>
      <div class="card mb10">
        <div class="grid2">
          <div class="field">
            <label>Ngày</label>
            <input type="date" v-model="doc.ngay" :disabled="!editable" />
          </div>
          <div class="field">
            <label>Loại nhập</label>
            <select v-model="doc.loai_nhap" :disabled="!editable">
              <option v-for="o in LOAI_OPTIONS" :key="o" :value="o">{{ o }}</option>
              <!-- Phiếu vào bằng cách khác (import, hook DN) có thể mang loại
                   không nằm trong LOAI_OPTIONS — vẫn hiển thị đúng giá trị đó. -->
              <option v-if="!LOAI_OPTIONS.includes(doc.loai_nhap)" :value="doc.loai_nhap">{{ doc.loai_nhap }}</option>
            </select>
          </div>
          <div class="field">
            <label>Người giao hàng</label>
            <input v-model="doc.nguoi_giao" :disabled="!editable" />
          </div>
          <div class="field">
            <label>Chứng từ kèm theo</label>
            <input v-model="doc.chung_tu_kem" :disabled="!editable" />
          </div>
        </div>
        <div class="field" style="margin-top: 10px">
          <label>Diễn giải</label>
          <textarea v-model="doc.dien_giai" :disabled="!editable" rows="2"></textarea>
        </div>
      </div>

      <div v-if="editable" class="flex mb10" style="gap: 8px; flex-wrap: wrap">
        <a class="btn-o btn-sm" :href="mauUrl">Tải file mẫu</a>
        <button class="btn-o btn-sm" :disabled="importing" @click="importInput.click()">
          {{ importing ? 'Đang đọc…' : '⬆ Nhập từ Excel' }}
        </button>
        <a v-if="doc.name" class="btn-o btn-sm" :href="exportUrl">⬇ Xuất Excel</a>
        <input ref="importInput" type="file" accept=".xlsx" style="display: none" @change="onImportFile" />
      </div>

      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th style="min-width: 180px">Vật tư</th>
              <th>Số lô</th>
              <th>Hạn dùng</th>
              <th class="right">Số lượng</th>
              <th class="right">Đơn giá</th>
              <th class="right">Thành tiền</th>
              <th v-if="editable"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, idx) in doc.items"
              :key="idx"
              :style="r._trang_thai === 'loi' ? 'background:#fff1f0' : (r._trang_thai === 'ma_moi' ? 'background:#fffbe6' : '')"
            >
              <td>
                <select v-if="editable" v-model="r.vat_tu" style="width: 100%" @change="onVatTuSelect(r, idx)">
                  <option value="" disabled>-- Chọn vật tư --</option>
                  <option v-for="v in vatTuList" :key="v.name" :value="v.name">
                    {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
                  </option>
                  <option :value="MUC_TAO_MOI">➕ Tạo vật tư mới…</option>
                </select>
                <span v-else>{{ r.ten_vat_tu || tenVatTu(r.vat_tu) }}</span>

                <div v-if="editable && r._trang_thai === 'ma_moi' && !r.vat_tu" class="warn" style="margin-top: 4px">
                  ⚠ Mã <b>{{ r._ma_vat_tu }}</b> chưa có trong kho.
                  <button class="btn-o btn-sm" @click="moTaoTuDong(r, idx)">Tạo vật tư mới</button>
                </div>
                <div v-if="r._loi && r._loi.length" class="tag" style="color: #cf1322; margin-top: 4px">
                  ✗ Dòng {{ r._loi_line }} trong tệp: {{ r._loi.join('; ') }}
                </div>
              </td>
              <td>
                <input v-if="editable" v-model="r.so_lo" style="width: 110px" />
                <span v-else>{{ r.so_lo }}</span>
              </td>
              <td>
                <input v-if="editable" type="date" v-model="r.han_su_dung" style="width: 140px" />
                <span v-else>{{ r.han_su_dung ? fmtDate(r.han_su_dung) : '—' }}</span>
              </td>
              <td class="right">
                <input
                  v-if="editable"
                  :value="r.so_luong"
                  @change="r.so_luong = Number($event.target.value) || 0"
                  inputmode="numeric"
                  style="width: 80px; text-align: right"
                />
                <span v-else>{{ Number(r.so_luong).toLocaleString('vi-VN') }}</span>
              </td>
              <td class="right">
                <input
                  v-if="editable"
                  :value="r.don_gia"
                  @change="r.don_gia = Number($event.target.value) || 0"
                  inputmode="numeric"
                  style="width: 100px; text-align: right"
                />
                <span v-else>{{ fmtVND(r.don_gia) }}</span>
              </td>
              <td class="right">{{ fmtVND(editable ? rowThanhTien(r) : r.thanh_tien) }}</td>
              <td v-if="editable">
                <button class="btn-o btn-sm" @click="removeRow(idx)">✕</button>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td :colspan="editable ? 5 : 5" style="text-align: right"><b>Tổng cộng</b></td>
              <td class="right"><b>{{ fmtVND(editable ? tongTienPreview : doc.tong_tien) }}</b></td>
              <td v-if="editable"></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <button v-if="editable" class="btn-o btn-sm" style="margin-top: 10px" @click="addRow">+ Thêm dòng</button>

      <!-- Nút hành động (mobile) -->
      <div v-if="isMobile" class="flex" style="gap: 8px; margin-top: 16px; flex-wrap: wrap">
        <button
          v-for="a in actions"
          :key="a.key"
          class="btn"
          :class="{ 'btn-o': a.variant !== 'primary', 'btn-danger': a.variant === 'danger' }"
          :disabled="submitting || cancelling"
          @click="onAction(a.key)"
        >
          {{ a.label }}
        </button>
        <button v-if="editable" class="btn-o" :disabled="saving" @click="save()">
          {{ saving ? 'Đang lưu…' : 'Lưu nháp' }}
        </button>
      </div>

      <VatTuModal
        :open="modalOpen"
        :initial="modalInitial"
        mode="tao"
        @saved="onVatTuSaved"
        @close="modalOpen = false"
      />
    </template>
  </div>
</template>
