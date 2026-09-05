<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import api from '../api'
import { fmtVND } from '../format'
import { useIsMobile } from '../useMobile'
import { BAO_CAO_THIET_BI_COLUMNS, BAO_CAO_THIET_BI_MAY_COLUMNS } from '../kho-bao-cao-columns'
import PhanTrang from '../components/PhanTrang.vue'

// Task 14 — "vật tư này nhập về bao nhiêu, cấp phát cho máy nào, khoa nào?"
// Backend: miyano_portal.api.kho.kho_bao_cao_thiet_bi (THÊM MỚI ở task này —
// xem báo cáo: reports.bao_cao_thiet_bi_rows()/bản Excel đã có từ task 9/10,
// nhưng CHƯA từng có endpoint JSON nào bọc nó cho SPA trước bản này).
//
// Bảng con "theo máy" đã có SẴN trong mỗi dòng (`row.theo_may`) — KHÔNG có
// lời gọi API riêng khi mở rộng một dòng (khác BaoCaoNXT.vue/tab NXT, nơi
// bung lô phải gọi lại server): toggleExpand() chỉ đổi trạng thái hiện/ẩn.

const isMobile = useIsMobile()

function pad(n) {
  return String(n).padStart(2, '0')
}
function isoDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const now = new Date()
const tuNgay = ref(isoDate(new Date(now.getFullYear(), now.getMonth(), 1)))
const denNgay = ref(isoDate(now))

// --- Bộ lọc Máy / Khoa phòng (dropdown) + ô tìm vật tư (debounce) ---
const mayList = ref([])
const khoaPhongList = ref([])
const mayChon = ref('') // '' = tất cả máy
const khoaChon = ref('') // '' = tất cả khoa
const tim = ref('')
let timTimer = null

async function loadMayList() {
  try {
    // ca_inactive=1 — cùng lý do NhatKy.vue/BaoCaoNXT.vue: một máy đã tắt
    // vẫn có thể có cấp phát TRONG QUÁ KHỨ, ô lọc phải tìm được đúng máy đó
    // để xem lại kỳ cũ, không chỉ máy đang hoạt động.
    mayList.value = await api.callKho('kho_thiet_bi_list', { ca_inactive: 1 })
  } catch (e) {
    // Ô lọc Máy sẽ chỉ thiếu, không chặn màn hình.
  }
}
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Ô lọc Khoa phòng sẽ chỉ thiếu, không chặn màn hình.
  }
}

// --- Dữ liệu bảng ---
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)
const loading = ref(false)
const error = ref('')
const result = ref({ dong: [], tong: 0, tong_doi_chieu: null, loc_theo_may_hoac_khoa: false })

const expanded = reactive({}) // vat_tu_id -> bool

function fmtQty(v) {
  return Number(v || 0).toLocaleString('vi-VN')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const out = await api.callKho('kho_bao_cao_thiet_bi', {
      tu_ngay: tuNgay.value,
      den_ngay: denNgay.value,
      thiet_bi: mayChon.value || undefined,
      khoa_phong: khoaChon.value || undefined,
      tim: tim.value.trim() || undefined,
      limit: soDong.value,
      start: (trang.value - 1) * soDong.value,
    })
    result.value = out
    tong.value = out.tong || 0
  } catch (e) {
    // e.message: thông điệp tiếng Việt server đã soạn sẵn (đã bóc tên lớp
    // lỗi ở api.js) — hiển thị NGUYÊN VĂN, không thay bằng câu chung chung.
    error.value = e.message || 'Không tải được báo cáo vật tư theo máy và khoa.'
    result.value = { dong: [], tong: 0, tong_doi_chieu: null, loc_theo_may_hoac_khoa: false }
    tong.value = 0
  } finally {
    loading.value = false
  }
}

function locThayDoi() {
  trang.value = 1
  load()
}

watch([tuNgay, denNgay, mayChon, khoaChon], locThayDoi)

// Debounce 300ms — cùng khuôn ô tìm của ThietBiList.vue/DanhMucVatTu.vue.
watch(tim, () => {
  clearTimeout(timTimer)
  trang.value = 1
  timTimer = setTimeout(() => load(), 300)
})

// PhanTrang.vue tự đổi trang.value/soDong.value (v-model) — nghe ở đây để
// gọi lại API, cùng khuôn mọi màn báo cáo khác.
watch([trang, soDong], load)

function toggleExpand(row) {
  expanded[row.vat_tu_id] = !expanded[row.vat_tu_id]
}

// Ba trạng thái rỗng KHÁC NHAU (bài học Task 12 — câu chữ phải đúng với
// THỰC TRẠNG dữ liệu, không chỉ khớp trạng thái ô lọc):
//   1. Đang tìm — so `tim.trim()`, CÙNG điều kiện load() dùng để quyết định
//      có gửi `tim` hay không (gõ toàn khoảng trắng thì server không lọc
//      gì, "khớp bộ lọc" sẽ là câu sai).
//   2. Không tìm nhưng có lọc Máy/Khoa phòng — rỗng vì bộ lọc, không phải vì
//      kỳ không có phát sinh gì cả.
//   3. Không lọc gì — đây mới thật là "kỳ này chưa có phát sinh" (đúng câu
//      brief yêu cầu).
const trangThaiRong = computed(() => {
  if (tim.value.trim()) return 'Không có vật tư nào khớp ô tìm kiếm trong kỳ này.'
  if (mayChon.value || khoaChon.value) {
    return 'Không có vật tư nào khớp bộ lọc Máy/Khoa phòng đã chọn trong kỳ này.'
  }
  return 'Kỳ này chưa có phát sinh.'
})

// Bất biến ton_dau + nhap - cap_phat - xuat_khac = ton_cuoi được ĐẢM BẢO
// từng dòng ở backend (reports.bao_cao_thiet_bi_rows, có test canh
// test_hang_van_can_khi_ky_co_ca_xuat_huy_va_phieu_dao) — dòng tổng ở đây
// tự đối chiếu lại LẦN NỮA trên chính con số đã nhận, KHÔNG tin suông là
// backend luôn đúng. So bằng NGƯỠNG SAI SỐ (không phải ===): cả hai vế đều
// là số THẬP PHÂN đã làm tròn ở backend (_r/round, xem docstring reports.py
// — test Python dùng assertAlmostEqual(places=4)), so tuyệt đối sẽ dương
// tính giả vì bụi làm tròn — một cảnh báo "không cân" kêu oan cũng là một
// lời nói dối, y hệt việc im lặng khi thật sự lệch.
const canDoi = computed(() => {
  const td = result.value.tong_doi_chieu
  if (!td) return true
  const diff = td.ton_dau + td.nhap - td.cap_phat - td.xuat_khac - td.ton_cuoi
  return Math.abs(diff) < 1e-4
})

function dsMaySuDung(row) {
  const thatSu = row.theo_may.filter((m) => m.thiet_bi)
  const coChuaGan = row.theo_may.some((m) => !m.thiet_bi)
  // Khử trùng lặp theo DOCNAME (`m.thiet_bi`), không theo tên hiển thị —
  // cùng quy ước xuyên suốt nhánh (backend gộp theo_may theo docname, xem
  // reports.bao_cao_thiet_bi_rows). Từ khi khoa lấy theo PHIẾU (đợt sửa
  // cuối, I-1), một máy lên hai phiếu khác nhau trong kỳ — kể cả khi chỉ
  // khác ở có/không điền khoa_phong trên phiếu — tạo HAI bucket cùng
  // `thiet_bi` khác `khoa_phong` trong `row.theo_may` (xem key ghép ở
  // template dưới). Cột tóm tắt này liệt kê MÁY, không liệt kê MÁY×KHOA,
  // nên phải gộp lại — không khử sẽ hiện "Máy A, Máy A".
  const idDuyNhat = [...new Set(thatSu.map((m) => m.thiet_bi))]
  const tenTheoId = new Map(thatSu.map((m) => [m.thiet_bi, m.ten_may]))
  return {
    ten: idDuyNhat.map((id) => tenTheoId.get(id)),
    coChuaGan,
    rong: row.theo_may.length === 0,
  }
}

// kho_bao_cao_excel (loai="thiet_bi") CHỈ nhận tu_ngay/den_ngay/khoa_phong/
// vat_tu (xem chữ ký hàm, api/kho.py) — KHÔNG có tham số `thiet_bi` (Máy)
// và cũng không nhận `tim`. Excel vì vậy KHÔNG áp được hai bộ lọc đó — xem
// `excelBoLocThieu` ngay dưới, hiện rõ trên màn hình thay vì lặng lẽ xuất
// thiếu bộ lọc khách tưởng đã áp dụng.
function exportUrl() {
  const base = '/api/method/miyano_portal.api.kho.kho_bao_cao_excel'
  let u = `${base}?loai=thiet_bi&tu_ngay=${encodeURIComponent(tuNgay.value)}&den_ngay=${encodeURIComponent(denNgay.value)}`
  if (khoaChon.value) u += `&khoa_phong=${encodeURIComponent(khoaChon.value)}`
  return u
}
function xuatExcel() {
  window.open(exportUrl(), '_blank')
}
const excelBoLocThieu = computed(() => !!(mayChon.value || tim.value.trim()))

onMounted(() => {
  loadMayList()
  loadKhoaPhongList()
  load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Báo cáo vật tư · máy · khoa phòng</h2>
        <div class="sub">Vật tư này nhập về bao nhiêu, cấp phát cho máy nào, khoa nào</div>
      </div>
      <div class="flex" style="gap: 8px">
        <button class="btn-o btn-sm" @click="xuatExcel">⬇ Xuất Excel</button>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>
    <div class="sb" v-else style="margin-bottom: 12px">
      <h2>Vật tư · máy · khoa phòng</h2>
      <button class="btn-o btn-sm" @click="xuatExcel">⬇ Excel</button>
    </div>

    <div class="card mb10">
      <div class="flex" style="flex-wrap: wrap; gap: 14px">
        <div class="field" style="margin-bottom: 0">
          <label>Từ ngày</label>
          <input type="date" v-model="tuNgay" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Đến ngày</label>
          <input type="date" v-model="denNgay" />
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Máy</label>
          <select v-model="mayChon">
            <option value="">— Tất cả máy —</option>
            <option v-for="m in mayList" :key="m.name" :value="m.name">
              {{ m.ma_thiet_bi }} — {{ m.ten_thiet_bi }}{{ m.active ? '' : ' (đã tắt)' }}
            </option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0">
          <label>Khoa phòng</label>
          <select v-model="khoaChon">
            <option value="">— Tất cả khoa —</option>
            <option v-for="k in khoaPhongList" :key="k.name" :value="k.name">
              {{ k.ten_khoa_phong }}{{ k.active ? '' : ' (đã tắt)' }}
            </option>
          </select>
        </div>
        <div class="field" style="margin-bottom: 0; flex: 1; min-width: 200px">
          <label>Tìm vật tư</label>
          <input type="text" v-model="tim" placeholder="Mã hoặc tên vật tư…" />
        </div>
      </div>
      <p class="tag" style="margin-top: 6px">
        File Excel là danh sách phẳng (vật tư × máy) — chỉ gồm những vật tư ĐÃ cấp phát cho ít nhất một máy trong
        kỳ, không có các cột Tồn đầu/Đã nhập/Xuất khác/Tồn cuối của bảng trên màn hình.
        <template v-if="excelBoLocThieu">
          File cũng KHÔNG áp bộ lọc Máy hoặc ô tìm vật tư — luôn xuất theo Từ ngày/Đến ngày/Khoa phòng đã chọn.
        </template>
      </p>
    </div>

    <p class="tag mb10" v-if="result.loc_theo_may_hoac_khoa">
      Đang lọc theo Máy hoặc Khoa phòng: bảng chi tiết theo máy (mở rộng một dòng) chỉ hiện phần khớp bộ lọc, còn
      cột "Đã cấp phát" vẫn là tổng CẢ vật tư trong kỳ — hai số sẽ KHÔNG khớp nhau trong lúc đang lọc. Bỏ chọn
      Máy/Khoa phòng để đối chiếu tổng cấp phát với tổng theo máy.
    </p>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!result.dong.length" class="empty">{{ trangThaiRong }}</div>

    <template v-else>
      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th v-for="c in BAO_CAO_THIET_BI_COLUMNS" :key="c.field"
                  :class="{ right: !['ma_vat_tu', 'vat_tu', 'dvt', 'may_su_dung'].includes(c.field) }">
                {{ c.label }}
                <span
                  v-if="c.field === 'xuat_khac'"
                  class="tag" style="cursor: help"
                  title="Xuất huỷ / hết hạn, xuất trả lại, điều chỉnh kiểm kê, và phần thuộc phiếu đã bị huỷ. Các loại này không gắn máy nên không nằm trong phần tách theo máy."
                >ⓘ</span>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in result.dong" :key="row.vat_tu_id">
              <tr class="clickable" @click="toggleExpand(row)">
                <td><b>{{ row.ma_vat_tu }}</b></td>
                <td>{{ row.vat_tu }}</td>
                <td>{{ row.dvt }}</td>
                <td class="right">{{ fmtQty(row.ton_dau) }}</td>
                <td class="right">{{ fmtQty(row.nhap) }}</td>
                <td class="right"><b>{{ fmtQty(row.cap_phat) }}</b></td>
                <td class="right">{{ fmtQty(row.xuat_khac) }}</td>
                <td class="right"><b>{{ fmtQty(row.ton_cuoi) }}</b></td>
                <td>
                  <template v-if="dsMaySuDung(row).rong">—</template>
                  <template v-else>
                    <span>{{ dsMaySuDung(row).ten.join(', ') }}</span>
                    <span v-if="dsMaySuDung(row).coChuaGan" class="chua-gan">
                      {{ dsMaySuDung(row).ten.length ? ', ' : '' }}Chưa gắn máy
                    </span>
                  </template>
                </td>
                <td>{{ expanded[row.vat_tu_id] ? '▾' : '▸' }}</td>
              </tr>
              <tr v-if="expanded[row.vat_tu_id]">
                <td :colspan="BAO_CAO_THIET_BI_COLUMNS.length + 1" style="background: #f8fafc; padding: 12px 16px">
                  <div v-if="!row.theo_may.length" class="empty" style="padding: 12px">
                    Chưa cấp phát cho máy nào trong kỳ này.
                    <template v-if="row.may_tuong_thich.length">
                      Máy tương thích đã khai (chưa từng xuất trong kỳ):
                      {{ row.may_tuong_thich.map((m) => m.ten).join(', ') }}.
                    </template>
                  </div>
                  <div v-else style="overflow-x: auto">
                    <table style="background: transparent">
                      <thead>
                        <tr>
                          <th v-for="c in BAO_CAO_THIET_BI_MAY_COLUMNS" :key="c.field"
                              :class="{ right: !['ten_may', 'ten_khoa'].includes(c.field) }">
                            {{ c.label }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <!-- "Chưa gắn máy" backend LUÔN xếp cuối theo_may (đã
                             kiểm ở test_tb6_bao_cao.py::test_phieu_cu_khong_
                             may_vao_nhom_chua_gan) — KHÔNG re-sort ở đây, chỉ
                             tô khác đi để không trông như một máy thật.

                             KEY ghép CẢ thiet_bi LẪN khoa_phong (đợt sửa cuối,
                             I-1): từ khi khoa lấy từ PHIẾU thay vì từ máy, một
                             máy dùng chung có thể xuất hiện ở HAI dòng trong
                             cùng theo_may (cùng máy, khác khoa trên phiếu) —
                             key chỉ theo thiet_bi sẽ trùng, khiến Vue mis-patch
                             hàng. -->
                        <tr v-for="m in row.theo_may"
                            :key="(m.thiet_bi || '__chua_gan__') + '|' + (m.khoa_phong || '__chua_gan_khoa__')"
                            :class="{ 'chua-gan': !m.thiet_bi }">
                          <td>{{ m.ten_may }}</td>
                          <td>{{ m.ten_khoa || '—' }}</td>
                          <td class="right">{{ fmtQty(m.sl) }}</td>
                          <td class="right">{{ fmtVND(m.gia_tri) }}</td>
                          <td class="right">{{ m.pct }}%</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
          <tfoot v-if="result.tong_doi_chieu">
            <tr>
              <td colspan="3" style="text-align: right"><b>Tổng cộng (toàn kỳ)</b></td>
              <td class="right"><b>{{ fmtQty(result.tong_doi_chieu.ton_dau) }}</b></td>
              <td class="right"><b>{{ fmtQty(result.tong_doi_chieu.nhap) }}</b></td>
              <td class="right"><b>{{ fmtQty(result.tong_doi_chieu.cap_phat) }}</b></td>
              <td class="right"><b>{{ fmtQty(result.tong_doi_chieu.xuat_khac) }}</b></td>
              <td class="right"><b>{{ fmtQty(result.tong_doi_chieu.ton_cuoi) }}</b></td>
              <td colspan="2">
                <span v-if="!canDoi" class="warn">⚠ Số liệu không cân — báo kỹ thuật</span>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div class="note note-loi" v-if="!canDoi">
        <b>⚠ Số liệu không cân — báo kỹ thuật.</b>
        Tồn đầu + Đã nhập − Đã cấp phát − Xuất khác phải bằng Tồn cuối ở dòng tổng, nhưng số liệu nhận được không
        khớp. Vui lòng liên hệ nhân viên kỹ thuật Miyano, đừng tự đối chiếu tay bằng số liệu này.
      </div>

      <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
      <p class="tag" style="margin-top: 6px">
        Cột "Đã cấp phát" luôn khớp đúng tổng SL xuất của bảng theo máy khi KHÔNG lọc Máy/Khoa phòng — hai cột xuất
        tách riêng vì báo cáo này chỉ tính "Xuất sử dụng" chưa bị huỷ vào cấp phát; "Xuất khác" gồm huỷ/hết hạn,
        trả lại, điều chỉnh kiểm kê và phần thuộc phiếu đã bị huỷ, các loại này không gắn máy theo thiết kế.
      </p>
    </template>
  </div>
</template>

<style scoped>
/* "Chưa gắn máy" — dữ liệu THẬT (một dòng xuất sử dụng không ghi máy), KHÔNG
   phải một máy để so tên, nên KHÔNG được tô như một máy thật. Cùng lý lẽ
   `.rowdim`/`.tag` sẵn có của app — chữ xám nghiêng, không icon cảnh báo (đây
   không phải một lỗi, đây là dữ liệu lịch sử có thật). */
.chua-gan {
  color: var(--gray);
  font-style: italic;
}
</style>
