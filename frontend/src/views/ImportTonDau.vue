<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const router = useRouter()
const isMobile = useIsMobile()

const templateUrl = api.khoDownloadUrl('kho_import_template')

const fileInput = ref(null)
const selectedFile = ref(null)
const fileUrl = ref('') // file_url của lần upload GẦN NHẤT — preview và commit dùng chung

const previewing = ref(false)
const committing = ref(false)
const previewError = ref('')
const preview = ref(null) // kết quả kho_import_preview
const result = ref(null) // kết quả kho_import_commit (khi đã xác nhận xong)

const MATCH_LABEL = {
  miyano: { text: 'Khớp mã Miyano', cls: 'b-blue' },
  private: { text: 'Mã riêng — tạo mới', cls: 'b-gray' },
  existing: { text: 'Đã có trong kho', cls: 'b-green' },
}

const canConfirm = computed(
  () => !!preview.value && preview.value.error_count === 0 && preview.value.ok_count > 0
)

function onPickFile(e) {
  const f = e.target.files && e.target.files[0]
  selectedFile.value = f || null
  // Chọn tệp khác thì bỏ kết quả preview cũ — tránh xác nhận nhầm dữ liệu của
  // tệp trước đó trong khi màn hình đang hiển thị tệp mới.
  preview.value = null
  fileUrl.value = ''
  previewError.value = ''
  result.value = null
}

async function onPreview() {
  if (!selectedFile.value) return
  previewing.value = true
  previewError.value = ''
  preview.value = null
  try {
    const uploaded = await api.uploadFile(selectedFile.value)
    fileUrl.value = uploaded.file_url
    preview.value = await api.callKho('kho_import_preview', { file_url: fileUrl.value })
  } catch (e) {
    previewError.value = e.message || 'Không đọc được tệp. Vui lòng kiểm tra lại định dạng.'
  } finally {
    previewing.value = false
  }
}

async function onCommit() {
  if (!canConfirm.value || committing.value) return
  committing.value = true
  try {
    result.value = await api.callKho('kho_import_commit', { file_url: fileUrl.value })
    showToast('Đã nhập tồn đầu kỳ thành công.')
  } catch (e) {
    showToast(e.message || 'Nhập tồn đầu kỳ thất bại.', 'error')
  } finally {
    committing.value = false
  }
}

function startOver() {
  selectedFile.value = null
  fileUrl.value = ''
  preview.value = null
  previewError.value = ''
  result.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function goToKho() {
  router.push('/kho')
}
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Nhập tồn đầu kỳ</h2>
        <div class="sub">Tải mẫu Excel, điền vật tư, xem trước rồi xác nhận — không có gì được ghi cho tới khi bạn xác nhận.</div>
      </div>
    </div>
    <h2 v-else style="margin-bottom: 4px">Nhập tồn đầu kỳ</h2>
    <p class="tag" v-if="isMobile" style="margin-bottom: 16px">
      Tải mẫu, điền vật tư, xem trước rồi xác nhận.
    </p>

    <!-- Đã nhập xong -->
    <div v-if="result" class="card">
      <h3 style="margin-bottom: 8px">✅ Đã nhập tồn đầu kỳ thành công</h3>
      <p>Phiếu nhập: <b>{{ result.receipt }}</b></p>
      <p>Đã ghi {{ result.rows_written }} dòng vật tư, tạo mới {{ result.created_items }} mã vật tư trong kho.</p>
      <div class="flex" style="margin-top: 16px">
        <button class="btn" @click="goToKho">Xem tồn kho</button>
        <button class="btn-o" @click="startOver">Nhập thêm tệp khác</button>
      </div>
    </div>

    <template v-else>
      <!-- Bước 1: tải mẫu -->
      <div class="card mb10">
        <div class="sb">
          <div>
            <b>Bước 1 · Tải tệp mẫu</b>
            <p class="tag" style="margin-top: 4px">
              Gồm các cột: Mã vật tư, Tên vật tư, ĐVT, Số lô, Hạn sử dụng, Số lượng, Đơn giá, Quy cách, Nhóm.
            </p>
          </div>
          <a :href="templateUrl" class="btn-o btn-sm" download>⬇ Tải mẫu Excel</a>
        </div>
      </div>

      <!-- Bước 2: chọn & xem trước -->
      <div class="card mb10">
        <b>Bước 2 · Chọn tệp đã điền và xem trước</b>
        <div class="flex" style="margin-top: 10px; flex-wrap: wrap">
          <input ref="fileInput" type="file" accept=".xlsx" @change="onPickFile" />
          <button class="btn" :disabled="!selectedFile || previewing" @click="onPreview">
            {{ previewing ? 'Đang đọc tệp…' : 'Xem trước' }}
          </button>
        </div>
        <p v-if="previewError" class="warn" style="margin-top: 10px">{{ previewError }}</p>
      </div>

      <!-- Bước 3: kết quả xem trước -->
      <div v-if="preview" class="card mb10">
        <b>Bước 3 · Kết quả xem trước</b>

        <div class="flex" style="margin-top: 10px; flex-wrap: wrap; gap: 8px">
          <span class="badge b-blue">{{ preview.summary.matched_miyano }} dòng khớp mã Miyano</span>
          <span class="badge b-gray">{{ preview.summary.private_new }} dòng mã riêng (tạo mới)</span>
          <span class="badge b-green">{{ preview.summary.existing_in_kho }} dòng đã có trong kho</span>
          <span v-if="preview.error_count" class="badge b-red">{{ preview.error_count }} dòng lỗi</span>
        </div>

        <!-- Danh sách lỗi -->
        <div v-if="preview.rows_error.length" class="mt10" style="margin-top: 14px">
          <p class="warn">Sửa các dòng sau trong tệp rồi tải lại — chưa có dữ liệu nào được ghi:</p>
          <div v-for="row in preview.rows_error" :key="row.line" class="rowline">
            <span><b>Dòng {{ row.line }}</b> ({{ row.ma_vat_tu }})</span>
            <span style="color: var(--red)">{{ row.errors.join('; ') }}</span>
          </div>
        </div>

        <!-- Bảng dòng hợp lệ -->
        <div v-if="preview.rows_ok.length" class="mt10" style="margin-top: 14px; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Dòng</th>
                <th>Mã vật tư</th>
                <th>Tên vật tư</th>
                <th>ĐVT</th>
                <th>Số lô</th>
                <th>Hạn dùng</th>
                <th class="right">Số lượng</th>
                <th class="right">Đơn giá</th>
                <th>Phân loại</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in preview.rows_ok" :key="row.line">
                <td>{{ row.line }}</td>
                <td><b>{{ row.ma_vat_tu }}</b></td>
                <td>{{ row.ten_vat_tu }}</td>
                <td>{{ row.dvt }}</td>
                <td>{{ row.so_lo }}</td>
                <td>{{ row.han_su_dung ? fmtDate(row.han_su_dung) : '—' }}</td>
                <td class="right">{{ Number(row.so_luong).toLocaleString('vi-VN') }}</td>
                <td class="right">{{ fmtVND(row.don_gia) }}</td>
                <td>
                  <span class="badge" :class="MATCH_LABEL[row.match_type].cls">
                    {{ MATCH_LABEL[row.match_type].text }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">Không có dòng hợp lệ nào trong tệp này.</div>
      </div>

      <!-- Bước 4: xác nhận -->
      <div v-if="preview" class="card">
        <b>Bước 4 · Xác nhận nhập</b>
        <p class="tag" style="margin-top: 4px">
          Xác nhận sẽ tạo các mã vật tư còn thiếu và một phiếu nhập "Tồn đầu kỳ" đã ghi sổ.
          Không thể sửa lại sau khi xác nhận — chỉ có thể huỷ phiếu.
        </p>
        <button class="btn" style="margin-top: 10px" :disabled="!canConfirm || committing" @click="onCommit">
          {{ committing ? 'Đang ghi sổ…' : 'Xác nhận nhập' }}
        </button>
        <span v-if="preview.error_count" class="warn" style="margin-left: 10px">
          Còn {{ preview.error_count }} dòng lỗi — sửa tệp và xem trước lại trước khi xác nhận.
        </span>
      </div>
    </template>
  </div>
</template>
