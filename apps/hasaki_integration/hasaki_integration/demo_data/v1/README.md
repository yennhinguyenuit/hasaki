# Hasaki Transaction Demo Dataset V1.0

Dữ liệu giả lập phục vụ đồ án, không phải số liệu kinh doanh nội bộ Hasaki.

Dataset cố định: 1.200 Order, 3.663 Item; kỳ 01/11/2025–31/10/2026, seed 20261101.
Migration chỉ đọc JSON đã đóng gói, không gọi generator. Không sửa hoặc sinh lại V1 sau khi team đã import; thay đổi cần phiên bản mới.

- `orders.json`: dùng customer_id/SKU; seeder resolve thành Link tại từng site.
- `payments.json`: gồm Paid và Pending; Pending là kế hoạch thanh toán, chưa thu tiền.
- `status_history.json`: lịch sử nghiệp vụ giả lập, không ghi đè audit trail controller.
- `master_snapshot.json`: chỉ mã KH, SKU, thuộc tính sản phẩm và danh mục; không có tên/email/điện thoại/ngày sinh khách hàng.
- `customer_cohorts.json`: nhóm hành vi giả lập ngoài Contact.
- `safety_policy.json`: Document Events và hash controller đã audit; không phải quyền bỏ qua hook.
- `manifest.json`: thống kê, mapping, giới hạn và checksum SHA256.
- `demo_scenarios.json`: khóa tra cứu ổn định cho các thành viên; Havatek bị blocker vì chưa có SKU.

Đọc `docs/DEMO_DATA_GUIDE.md`, `docs/DEMO_DATA_REPORT.md`, `docs/DEMO_DATA_TEST_REPORT.md` ở gốc repository trước triển khai.
