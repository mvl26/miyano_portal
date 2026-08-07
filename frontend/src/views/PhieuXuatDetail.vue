<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { phieuActions, trangThaiBadge } from '../kho-actions'
import { useIsMobile } from '../useMobile'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const DOCTYPE = 'Customer Stock Issue'
const LOAI_OPTIONS = ['Xuất sử dụng', 'Xuất huỷ - hết hạn', 'Xuất trả lại', 'Điều chỉnh kiểm kê']
// "Phiếu đảo" CỐ Ý không có trong danh sách — cùng lý do với PhieuNhapDetail.

const isNew = computed(() => route.params.name === 'moi')

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const submitting = ref(false)
const cancelling = ref(false)

const doc = reactive({
  name: '',
  ngay: new Date().toISOString().slice(0, 10),
  loai_xuat: 'Xuất sử dụng',
  noi_nhan: '',
  nguoi_nhan: '',
  dien_giai: '',
  docstatus: 0,
  tong_tien: 0,
  items: [],
})

const vatTuList = ref([])

const editable = computed(() => isNew.value || doc.docstatus === 0)
const actions = computed(() => phieuActions(doc))
const badge = computed(() => trangThaiBadge(doc.docstatus))

function blankRow() {
  return {
    vat_tu: '', so_lo: '', so_luong: 1, xac_nhan_het_han: false, ghi_chu: '',
    han_su_dung: null, don_gia: 0, // chỉ để xem trước — server luôn tính lại từ lô
    _lots: [], _lotsLoading: false, _hetHan: false,
  }
}
function addRow() {
  doc.items.push(blankRow())
}
function removeRow(idx) {
  doc.items.splice(idx, 1)
}

function applyLotToRow(row, soLo) {
  const lot = row._lots.find((l) => l.so_lo === soLo)
  if (!lot) return
  row.so_lo = lot.so_lo
  row.han_su_dung = lot.han_su_dung
  row.don_gia = lot.don_gia
  row._hetHan = !!lot.het_han
  if (!row._hetHan) row.xac_nhan_het_han = false
}

// Gọi kho_lo_goi_y() để lấy danh sách lô theo thứ tự FEFO (hạn gần nhất
// trước, lô không hạn xếp cuối) kèm số lượng đề xuất lấy từ mỗi lô — và mặc
// định chọn lô đầu tiên trả về, tức lô gần hết hạn nhất.
async function loadLotsForRow(row) {
  if (!row.vat_tu) {
    row._lots = []
    return
  }
  row._lotsLoading = true
  try {
    const out = await api.callKho('kho_lo_goi_y', { vat_tu: row.vat_tu, so_luong: row.so_luong || 0 })
    row._lots = out.lots || []
    if (row._lots.length) {
      // Giữ lựa chọn cũ nếu lô đó vẫn còn trong danh sách (đổi so_luong không
      // nên tự đổi lô người dùng đã chọn); nếu chưa chọn hoặc lô cũ hết
      // tồn thì mặc định lô đầu tiên (gần hết hạn nhất).
      const stillThere = row._lots.some((l) => l.so_lo === row.so_lo)
      applyLotToRow(row, stillThere ? row.so_lo : row._lots[0].so_lo)
    } else {
      row.so_lo = ''
      row.han_su_dung = null
      row.don_gia = 0
      row._hetHan = false
    }
  } catch (e) {
    showToast(e.message || 'Không tải được danh sách lô.', 'error')
  } finally {
    row._lotsLoading = false
  }
}

function onVatTuChange(row) {
  row.so_lo = ''
  loadLotsForRow(row)
}
function onSoLuongChange(row, val) {
  row.so_luong = Number(val) || 0
  loadLotsForRow(row)
}
function onSoLoChange(row) {
  applyLotToRow(row, row.so_lo)
}

function rowThanhTien(row) {
  return (Number(row.so_luong) || 0) * (Number(row.don_gia) || 0)
}
const tongTienPreview = computed(() => doc.items.reduce((s, r) => s + rowThanhTien(r), 0))

async function loadVatTu() {
  try {
    vatTuList.value = await api.callKho('kho_vat_tu_list')
  } catch (e) {
    showToast(e.message || 'Không tải được danh mục vật tư.', 'error')
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
    doc.items = (out.items || []).map((r) => ({
      ...r, _lots: [], _lotsLoading: false, _hetHan: false,
    }))
    // Nháp đã có dòng sẵn (ví dụ do Delivery Note sinh, hoặc lưu dở lần
    // trước): nạp lại danh sách lô cho từng dòng để select không trống —
    // loadLotsForRow() tự giữ nguyên so_lo hiện tại nếu nó còn trong tồn.
    if (doc.docstatus === 0) {
      await Promise.all(doc.items.map((r) => loadLotsForRow(r)))
    }
  } catch (e) {
    error.value = e.message || 'Không tải được phiếu xuất.'
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
      showToast(`Dòng ${i + 1}: chưa chọn lô.`, 'error')
      return false
    }
    if (r._hetHan && !r.xac_nhan_het_han) {
      showToast(`Dòng ${i + 1}: lô ${r.so_lo} đã hết hạn — tích xác nhận trước khi xuất.`, 'error')
      return false
    }
  }
  return true
}

function payload() {
  const p = {
    ngay: doc.ngay,
    loai_xuat: doc.loai_xuat,
    noi_nhan: doc.noi_nhan,
    nguoi_nhan: doc.nguoi_nhan,
    dien_giai: doc.dien_giai,
    items: doc.items.map((r) => ({
      vat_tu: r.vat_tu, so_lo: r.so_lo, so_luong: r.so_luong,
      xac_nhan_het_han: r.xac_nhan_het_han ? 1 : 0, ghi_chu: r.ghi_chu,
    })),
  }
  if (!isNew.value) p.name = doc.name
  return p
}

async function save({ silent } = {}) {
  if (!validateClient()) return null
  saving.value = true
  try {
    const before = doc.items // giữ tham chiếu TRƯỚC khi Object.assign ghi đè
    const out = await api.callKho('kho_phieu_xuat_save', { payload: payload() })
    const savedItems = out.items
    Object.assign(doc, out)
    // Giữ lại danh sách lô (_lots) đã tải của mỗi dòng theo (vat_tu, so_lo) —
    // tránh gọi lại kho_lo_goi_y() cho những dòng không đổi, chỉ nạp thêm
    // cho dòng thật sự thiếu (dòng mới, hoặc lô vừa đổi).
    doc.items = savedItems.map((r) => {
      const cu = before.find((old) => old.vat_tu === r.vat_tu && old.so_lo === r.so_lo)
      return {
        ...r,
        _lots: cu ? cu._lots : [],
        _lotsLoading: false,
        _hetHan: cu ? cu._hetHan : false,
      }
    })
    if (doc.docstatus === 0) {
      await Promise.all(doc.items.filter((r) => !r._lots.length).map((r) => loadLotsForRow(r)))
    }
    if (isNew.value) {
      router.replace(`/kho/xuat/${out.name}`)
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
  if (!window.confirm(`Ghi sổ phiếu ${saved.name}? Tồn kho sẽ bị trừ ngay. Sau khi ghi sổ chỉ có thể huỷ, không sửa được nữa.`)) return
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
    showToast('Đã huỷ phiếu, tồn kho đã được hoàn trả.')
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
        <h2>{{ isNew ? 'Tạo phiếu xuất kho' : doc.name }}</h2>
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
        <router-link to="/kho/xuat" class="btn-o">Quay lại</router-link>
      </div>
    </div>
    <div v-else style="margin-bottom: 12px">
      <div class="sb">
        <h2>{{ isNew ? 'Tạo phiếu xuất' : doc.name }}</h2>
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
            <label>Loại xuất</label>
            <select v-model="doc.loai_xuat" :disabled="!editable">
              <option v-for="o in LOAI_OPTIONS" :key="o" :value="o">{{ o }}</option>
              <option v-if="!LOAI_OPTIONS.includes(doc.loai_xuat)" :value="doc.loai_xuat">{{ doc.loai_xuat }}</option>
            </select>
          </div>
          <div class="field">
            <label>Nơi nhận</label>
            <input v-model="doc.noi_nhan" :disabled="!editable" placeholder="VD: Khoa Hồi sức tích cực" />
          </div>
          <div class="field">
            <label>Người nhận</label>
            <input v-model="doc.nguoi_nhan" :disabled="!editable" />
          </div>
        </div>
        <div class="field" style="margin-top: 10px">
          <label>Lý do xuất</label>
          <textarea v-model="doc.dien_giai" :disabled="!editable" rows="2"></textarea>
        </div>
      </div>

      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th style="min-width: 180px">Vật tư</th>
              <th style="min-width: 220px">Lô (FEFO)</th>
              <th>Hạn dùng</th>
              <th class="right">Tồn lô</th>
              <th class="right">Số lượng xuất</th>
              <th class="right">Đơn giá</th>
              <th class="right">Thành tiền</th>
              <th v-if="editable"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in doc.items" :key="idx">
              <td>
                <select v-if="editable" v-model="r.vat_tu" style="width: 100%" @change="onVatTuChange(r)">
                  <option value="" disabled>-- Chọn vật tư --</option>
                  <option v-for="v in vatTuList" :key="v.name" :value="v.name">
                    {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
                  </option>
                </select>
                <span v-else>{{ r.ten_vat_tu }}</span>
              </td>
              <td>
                <template v-if="editable">
                  <div v-if="r._lotsLoading" class="tag">Đang tải lô…</div>
                  <select v-else-if="r._lots.length" v-model="r.so_lo" style="width: 100%" @change="onSoLoChange(r)">
                    <option v-for="l in r._lots" :key="l.so_lo" :value="l.so_lo">
                      {{ l.so_lo }} · còn {{ Number(l.so_luong_ton).toLocaleString('vi-VN') }}
                      {{ l.han_su_dung ? '· HSD ' + fmtDate(l.han_su_dung) : '· không hạn' }}
                      {{ l.het_han ? ' ⚠ QUÁ HẠN' : '' }}
                    </option>
                  </select>
                  <span v-else-if="r.vat_tu" class="tag">Vật tư này chưa còn tồn lô nào.</span>
                  <span v-else class="tag">Chọn vật tư trước</span>
                  <div v-if="r._hetHan" class="warn" style="margin-top: 4px; display: flex; align-items: center; gap: 4px">
                    <label style="display: flex; align-items: center; gap: 4px; font-weight: 600">
                      <input type="checkbox" v-model="r.xac_nhan_het_han" />
                      Xác nhận xuất lô đã hết hạn
                    </label>
                  </div>
                </template>
                <span v-else>
                  {{ r.so_lo }}
                  <span v-if="r.xac_nhan_het_han" class="badge b-red" style="margin-left: 4px">Đã xác nhận hết hạn</span>
                </span>
              </td>
              <td>{{ r.han_su_dung ? fmtDate(r.han_su_dung) : '—' }}</td>
              <td class="right">
                <span v-if="editable && r._lots.length">
                  {{ Number((r._lots.find((l) => l.so_lo === r.so_lo) || {}).so_luong_ton || 0).toLocaleString('vi-VN') }}
                </span>
                <span v-else>—</span>
              </td>
              <td class="right">
                <input
                  v-if="editable"
                  :value="r.so_luong"
                  @change="onSoLuongChange(r, $event.target.value)"
                  inputmode="numeric"
                  style="width: 80px; text-align: right"
                />
                <span v-else>{{ Number(r.so_luong).toLocaleString('vi-VN') }}</span>
              </td>
              <td class="right">{{ fmtVND(r.don_gia) }}</td>
              <td class="right">{{ fmtVND(rowThanhTien(r)) }}</td>
              <td v-if="editable">
                <button class="btn-o btn-sm" @click="removeRow(idx)">✕</button>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="6" style="text-align: right"><b>Tổng cộng</b></td>
              <td class="right"><b>{{ fmtVND(editable ? tongTienPreview : doc.tong_tien) }}</b></td>
              <td v-if="editable"></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p class="tag" style="margin-top: 6px" v-if="editable">
        Đơn giá và hạn dùng lấy tự động theo lô đã chọn, không thể sửa tay.
      </p>
      <button v-if="editable" class="btn-o btn-sm" style="margin-top: 10px" @click="addRow">+ Thêm dòng</button>

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
    </template>
  </div>
</template>
