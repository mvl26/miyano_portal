"""Review I-4 (round 1) đã sửa NỘI DUNG `v1_8/mo_rong_workflow_e6.py`
(state "Báo giá hết hạn": `allow_edit` "Sales User" -> "System Manager" +
thêm cạnh ra "Mở lại"), nhưng `Patch Log` chỉ ghi TÊN patch đã chạy — không
so nội dung — nên một site đã chạy `migrate` với bản v1_8 CŨ (trước bản
sửa) sẽ KHÔNG tự nhận bản sửa qua `bench migrate` lần nữa, vì patch
`miyano_portal.patches.v1_8.mo_rong_workflow_e6` đã bị đánh dấu "đã chạy".

Review round 2 chỉ thẳng: sửa bằng `bench execute` gõ tay trên một site là
cách sửa KHÔNG persist — site khác (hoặc site này sau một lần restore DB)
sẽ không có gì áp lại bản sửa. Patch này là bản persist thật: gọi LẠI đúng
hàm `execute()` của v1_8 (đã tự idempotent-theo-THUỘC-TÍNH, không chỉ theo
sự tồn tại — xem docstring ở đó) qua một tên patch MỚI, CHƯA từng chạy trên
bất kỳ site nào, nên `bench migrate` chắc chắn thực thi nó đúng một lần
trên mọi site — kể cả site đã chạy v1_8 bản cũ lẫn site cài mới (vốn đã
nhận đúng bản v1_8 đã sửa, nên gọi lại ở đây là no-op an toàn).
"""

from miyano_portal.patches.v1_8.mo_rong_workflow_e6 import execute as _execute_v1_8


def execute():
    _execute_v1_8()
