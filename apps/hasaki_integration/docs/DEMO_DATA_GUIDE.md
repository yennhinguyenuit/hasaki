# Hướng dẫn Hasaki Transaction Demo Dataset V1.0

**Dữ liệu giả lập phục vụ đồ án, không phải số liệu kinh doanh nội bộ Hasaki.**

**Cập nhật triển khai:** Đã backup, import qua Migration Patch, chạy migrate lần hai, seeder độc lập và regression A4.8 37/37 Passed. Reconcile đủ 1.200 đơn/3.663 Item/1.200 Payment; dữ liệu cũ/demo giữ nguyên, chỉ chấp nhận User.last_active đổi. Dữ liệu regression mới đã dọn đúng phạm vi. Chi tiết ở [báo cáo triển khai](DEMO_DATA_DEPLOYMENT_REPORT.md); không import lại hoặc reset marker/Patch Log.

## Trạng thái bàn giao ngày 27/11/2026

Source sẵn để review, chưa commit/push/merge/copy vào repo nhóm. 16/16 offline/mô phỏng Passed. Cơ chế cập nhật App bằng migrate đã kiểm thử thật; người dùng đã kiểm tra HSK Order và HSK Payment trên Desk và xác nhận hiển thị đúng. Install-app lần đầu end-to-end còn Not Tested; source/hook/callback không thay thế việc cài mới thật. Không tạo/cài lại App hoặc site hiện tại để thử.

Chỉ bật dataset trên site demo được chủ môi trường xác nhận. Cờ mặc định tắt; App không suy đoán site local đồng nghĩa demo. Giữ cờ tắt trên production. Seeder không gửi dữ liệu sang WooCommerce và không tạo HSK Integration Event.

## Nhận diện môi trường

Local Nhi đã kiểm tra: container `crm-frappe-1`, Bench `/home/frappe/frappe-bench`, site `crm.localhost`; mount thư mục Windows `C:\Users\Yen Nhi\frappe-crm` vào `/workspace`, App link đến `/workspace/hasaki_integration`. Frappe 15.127.1, CRM 1.92.0.

Đã kiểm tra lại theo ràng buộc triển khai bổ sung: `hasaki_integration` 0.0.1 đã cài trên `crm.localhost`; `readlink -f /home/frappe/frappe-bench/apps/hasaki_integration` trả `/workspace/hasaki_integration`. Tiếp tục dùng source Windows hiện tại. Trên môi trường Nhi, chỉ áp dụng mục **Thành viên đã cài App**: không chạy `bench new-app`, không chạy lại `install-app`, không tạo site thay thế, không đổi Docker/volume/mount/symlink và không tạo lại năm DocType A4.8. Hướng dẫn cài mới bên dưới chỉ dành cho thành viên thực sự chưa có App.

Phạm vi bổ sung chỉ gồm dataset, seeder, patch, kiểm thử và tài liệu; `hooks.py` chỉ đăng ký seeder khi install/migrate. API, Webhook receiver, WordPress Plugin, JSON schema và controller A4.8 không có diff so với Git HEAD. Regression runtime đạt 37/37. Không tự commit/push/merge; đích bàn giao giữ nguyên `C:\Users\Yen Nhi\hasaki-team-a48\apps\hasaki_integration`.

Máy khác phải tìm container/site/Bench thực tế, không dùng mặc định của Nhi nếu chưa đối chiếu:

```powershell
docker ps --format '{{.Names}}\t{{.Status}}'
# Điền sau khi đã kiểm tra máy của bạn:
$DemoContainer = 'crm-frappe-1'
$DemoBench = '/home/frappe/frappe-bench'
$DemoSite = 'crm.localhost'
docker inspect $DemoContainer --format '{{json .Mounts}}'
docker exec -w $DemoBench $DemoContainer bench version
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite list-apps
docker exec -w $DemoBench $DemoContainer readlink -f apps/hasaki_integration
```

Không in hoặc gửi nội dung site_config.json chứa secret. Không dùng helper local_setup để tạo lại user hoặc Master Data.

## Thành viên đã cài App

1. Nhận source đã được nhóm duyệt vào đúng App đang được Bench dùng, gồm cả `hasaki_integration/demo_data/v1`. Không chỉ copy file patch. Nếu dùng git pull, bảo đảm working tree riêng đã được xử lý và commit dataset thực sự đã có trên main; bản local hiện tại chưa push.
2. Kiểm tra schema, mapping và tác động hook bằng dry-run chỉ đọc:

```powershell
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite execute hasaki_integration.seed_demo_data.dry_run
```

Kỳ vọng `valid=true`, 100 mã khách hàng và 200 SKU mapping duy nhất, `database_writes=0`. Nếu thiếu mã/trùng mã hoặc có hook/rule chưa audit, dừng. Không sửa Contact/Product hoặc policy để cho import chạy qua. Schema chưa có thì migrate khi cờ demo tắt trước, sau đó dry-run lại.

3. Sau kiểm thử site riêng và được chủ site đồng ý import, backup database **và files**:

```powershell
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite backup --with-files
```

Kiểm tra backup hoàn thành, lưu ở khu vực riêng của site ngoài Git. Không restore theo hướng dẫn này. Các lệnh dưới là thao tác ghi, chỉ chạy trên site demo đã được chủ site duyệt. Quy trình này đã được kiểm thử trên crm.localhost; máy thành viên thay biến theo môi trường thực tế:

```powershell
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite set-config hasaki_enable_demo_data 1 --parse
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite migrate
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite execute hasaki_integration.seed_demo_data.status
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite execute hasaki_integration.seed_demo_data.reconcile
```

4. Kỳ vọng sau import đầu: `complete=true`, 1.200 Order và 1.200 Payment thuộc namespace demo, `matches_frozen_dataset=true`. Tổng số toàn site còn gồm giao dịch cũ; không đối chiếu tổng bảng với 1.200. Local tại audit đã có 57 Order/15 Payment trước đó.
5. Mở Desk → HSK Order, lọc `source_store = hasaki-demo-v1` hoặc `integration_key` theo demo_scenarios.json; mở HSK Payment theo Link Order. Naming Series vẫn là series hiện tại, tên Document khác nhau giữa các site. Lịch sử trong child table là audit thời điểm import thật; không phải lịch sử quá khứ trong JSON.

## Thành viên chưa cài App

1. Đồng bộ **gói App hoàn chỉnh đã duyệt** vào Bench. Nếu Bench đã đăng ký App, không get-app lại. Kiểm tra không trùng DocType/schema do App thành viên khác sở hữu.
2. Xác nhận Master Data từ snapshot chung đã có: 100 mã KH, 200 SKU và danh mục tương ứng. Không dùng tên/email/điện thoại để thay mã KH; không tự tạo master thiếu. Custom fields master phải sẵn có trên site.
3. Backup site với `backup --with-files` như trên.
4. Nếu App chưa được đăng ký Bench, lệnh bên dưới nhận **đường dẫn source phía Linux/container** hoặc URL App độc lập đã duyệt; repository nhóm là monorepo có `apps/hasaki_integration`, không dùng URL gốc monorepo như App độc lập:

```powershell
# Thay giá trị bằng đường dẫn thực đã kiểm tra, không chạy nguyên placeholder:
$ReviewedAppSource = '<DUONG_DAN_SOURCE_APP_TRONG_CONTAINER>'
docker exec -w $DemoBench $DemoContainer bench get-app $ReviewedAppSource
```

5. Chỉ sau khi xác nhận demo và cho phép import, bật cờ rồi install/migrate:

```powershell
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite set-config hasaki_enable_demo_data 1 --parse
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite install-app hasaki_integration
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite migrate
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite execute hasaki_integration.seed_demo_data.status
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite execute hasaki_integration.seed_demo_data.reconcile
```

Frappe 15.127.1 đánh dấu patch App là completed trước gọi after_install (đã đọc source installer.py đang chạy). Vì vậy after_install gọi cùng seeder; after_migrate cũng thử lại nếu cờ bật. Cài mới/migrate thật trên site thứ hai vẫn **Not Tested**. Không tuyên bố thành công chỉ vì Patch Log đã có dòng.

## Retry, chống trùng và bảo vệ chỉnh sửa

Patch đăng ký trong `[post_model_sync]`, đúng cơ chế [Database Migrations](https://docs.frappe.io/framework/user/en/database-migrations). [after_migrate](https://docs.frappe.io/framework/user/en/bench/reference/migrate) xử lý trường hợp patch đã được log khi demo tắt rồi mới bật cờ sau đó.

- Khi tắt cờ: patch/hook không import. Patch Log có thể hoàn tất phần code, nhưng `status.complete` vẫn false và không có marker dataset.
- Khi bật cờ mà thiếu master/schema/safety check: raise lỗi; không tạo marker thành công. Không dùng migrate --skip-failing để che lỗi.
- Khắc phục nguồn Master Data đúng snapshot hoặc yêu cầu chủ App rà soát tích hợp rồi chạy dry-run, migrate lại. Không tạo master ngẫu nhiên hoặc bỏ validation.
- Import dùng ORM/controller, một savepoint; lỗi rollback toàn bộ phần import. Không tự commit trong hàm seeder. Caller Bench/patch sở hữu commit; không gọi hàm này từ nghiệp vụ đang có transaction khác.
- Marker hoàn tất lưu tại global default `hasaki_demo_transactions_v1` cùng hash manifest, trong cùng transaction. Có khóa file theo site để ngăn tiến trình import đồng thời; unique key database vẫn bảo vệ collision.
- Khi đã có marker: không cập nhật, xóa hoặc tạo lại giao dịch bị người dùng sửa/xóa. Nếu thiếu bản ghi, status.complete false; operator kiểm tra reconcile. Không xóa marker hoặc reset Patch Log để ép nhập lại.
- Nếu có key demo mà chưa có marker: dừng vì collision, không nhận quyền sở hữu giao dịch sẵn có.
- Lệnh dự phòng sau dry-run, backup và xác nhận tương đương migrate:

```powershell
docker exec -w $DemoBench $DemoContainer bench --site $DemoSite execute hasaki_integration.seed_demo_data.seed
```

## Kiểm thử trước nghiệm thu

Offline (không ghi database):

```powershell
python -m hasaki_integration.validate_demo_data
python scripts/report_demo_data.py
```

Chỉ chạy generator lúc chuẩn bị bản V1 chưa phát hành: `python -m hasaki_integration.generate_demo_data`. Không gọi generator khi migrate hoặc trên từng máy thành viên để tạo dataset mới. Windows/Linux dùng LF cố định để checksum giống nhau.

Đã chuẩn bị `hasaki_integration.tests.test_demo_data_site.run` cho **site test riêng đã có Master Data chung và schema hiện tại**, không tạo/restore Master Data. Hàm chặn crm.localhost, yêu cầu `hasaki_demo_test_site=1`, `hasaki_enable_demo_data=1`, chưa có marker V1; kiểm tra import/reconcile/chạy lại/giữ sửa đổi/rollback qua ORM thật rồi rollback dữ liệu test. Review source trước chạy. Không migrate với cờ demo bật trước test vì sẽ import và tạo marker trước khi suite bắt đầu.

Migrate hai lần đã kiểm thử thật trên crm.localhost theo xác nhận của chủ site. Install-app mới end-to-end còn Not Tested; không tạo/cài lại App/site hiện tại. 37 regression A4.8 hardcode HTTP 127.0.0.1:8000 và site header crm.localhost. Runner mới `hasaki_integration.demo_regression.run` đã chạy đủ 37 case và dọn đúng bản ghi test mới, lưu verdict trước cleanup, bảo toàn demo và giao dịch cũ. Chỉ dùng runner khi chủ site đã duyệt. Không dùng runner A4.8 gốc nếu không muốn giữ lại record test. Trên site khác phải cấu hình endpoint/site header đúng trước; đổi tên site Bench không đổi HTTP target.

## Giới hạn nghiệp vụ

Không có Havatek, chưa chuẩn bị được bảo hành còn/hết hạn; không tự tạo SKU hoặc field. loyalty_eligible giữ 0 toàn bộ vì chưa có quy tắc nhóm triển khai. Đơn POS Paid/mua lặp lại đã có để Trâm áp dụng quy tắc sau. Không tạo Loyalty Transaction, Refund, Return, Complaint, voucher hoặc chi phí ABC/CAC. Ngày đổi trả demo lấy mốc 31/10/2026; không tự coi đủ điều kiện tại ngày hiện tại. Chi tiết ở DEMO_DATA_REPORT.md và demo_scenarios.json.

## Bàn giao repository nhóm

Git status App ban đầu có 14 JSON audit/test cũ untracked; giữ nguyên, không gộp tự động vào gói commit mới. Repo nhóm `C:\Users\Yen Nhi\hasaki-team-a48` tại kiểm tra đang branch `nhi`, working tree sạch. Không tự commit/push/merge hoặc copy ghi đè repo nhóm.

Từ source App đã kiểm thử, chỉ đồng bộ các file liệt kê trong `docs/DEMO_DATA_FILES.txt` vào `apps/hasaki_integration` của repo nhóm, giữ cấu trúc tương đối. Ví dụ chuẩn bị copy từng file sau review bằng PowerShell:

```powershell
$DemoSource = 'C:\Users\Yen Nhi\frappe-crm\hasaki_integration'
$DemoDestination = 'C:\Users\Yen Nhi\hasaki-team-a48\apps\hasaki_integration'
$DemoManifest = Join-Path $DemoSource 'docs\DEMO_DATA_FILES.txt'
foreach ($DemoRelativeFile in Get-Content -LiteralPath $DemoManifest) {
    $DemoInputFile = Join-Path $DemoSource $DemoRelativeFile
    $DemoOutputFile = Join-Path $DemoDestination $DemoRelativeFile
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DemoOutputFile) | Out-Null
    Copy-Item -LiteralPath $DemoInputFile -Destination $DemoOutputFile
}
git -C 'C:\Users\Yen Nhi\hasaki-team-a48' diff --check
git -C 'C:\Users\Yen Nhi\hasaki-team-a48' diff --stat
git -C 'C:\Users\Yen Nhi\hasaki-team-a48' status --short
```

Lệnh copy là hướng dẫn chưa chạy. Review diff hooks.py/patches.txt để giữ thay đổi mới của nhóm nếu có; không chép đè mù quáng. Không dùng robocopy /MIR; không copy .git, site_config, secrets, SQL, backups, log hoặc môi trường local. Danh sách chỉ chứa mã KH và sản phẩm công khai trong snapshot, không có tên/email/điện thoại/ngày sinh khách hàng.
