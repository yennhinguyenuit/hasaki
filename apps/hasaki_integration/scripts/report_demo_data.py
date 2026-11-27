"""Run offline checks and render evidence/statistics without database writes."""
import io
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hasaki_integration.validate_demo_data import load, validate

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    (ROOT / path).write_text(value, encoding='utf-8', newline='\n')


def run():
    validate()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromName('hasaki_integration.tests.test_demo_data_offline')
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    write('docs/demo_offline_results.json', json.dumps({
        'date': '2026-11-27', 'environment': 'Offline Python, no database connection',
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'output': stream.getvalue()}, indent=2) + '\n')
    data = load()
    m = data['manifest']
    categories = {c['category_id']: c['category_name'] for c in data['master_snapshot']['categories']}
    payment_states = Counter(p['status'] for p in data['payments'])
    deployed = (ROOT / 'docs/demo_deployment_validation.json').exists()
    deployment_note = ('Đã import qua Migration Patch; xem DEMO_DATA_DEPLOYMENT_REPORT.md cho kết quả kiểm thử runtime mới nhất.'
                       if deployed else 'Đã sinh dataset và dry-run; chưa import database.')
    rows = ['# BÁO CÁO HASAKI DEMO DATASET V1.0', '',
            '**Dữ liệu giả lập phục vụ đồ án, không phải số liệu kinh doanh nội bộ Hasaki.**', '',
            f'Ngày kiểm tra: 27/11/2026. Trạng thái: {deployment_note}', '',
            '## Thống kê dataset', '', '| Chỉ tiêu | Giá trị |', '|---|---:|']
    stats = [('Khách có giao dịch', m['counts']['customers']), ('Order', 1200), ('Order Item', m['counts']['items']),
             ('Payment', m['counts']['payments']), ('Payment Paid', payment_states['Paid']),
             ('Payment Pending', payment_states['Pending']), ('Sự kiện nghiệp vụ trong JSON', m['counts']['business_status_events']),
             ('Đơn lịch sử bổ sung', 0), ('Tổng giá trị đơn VND', m['total_value']),
             ('AOV toàn bộ đơn VND', m['average_order_value']), ('Doanh thu Completed + Paid VND', m['realized_revenue']),
             ('Chiết khấu toàn bộ đơn VND', m['discounts']), ('Giá vốn toàn bộ đơn VND', m['total_cost']),
             ('Giá vốn đơn doanh thu VND', m['realized_cost']), ('Doanh thu trừ giá vốn hàng bán VND', m['gross_profit_before_other_costs']),
             ('Tỷ lệ khách có hơn một đơn (mọi trạng thái)', f"{m['repeat_purchase_rate']:.0%}")]
    rows += [f'| {key} | {value:,} |' if isinstance(value, (int, float)) else f'| {key} | {value} |' for key, value in stats]
    rows += ['', 'Doanh thu gồm phí vận chuyển; hiệu số doanh thu–giá vốn chưa trừ chi phí vận chuyển, Marketing hoặc chi phí ABC. Không phải lợi nhuận ròng.', '']
    for title, distribution in [('Kênh', m['channels']), ('Trạng thái', m['statuses']), ('Tháng', m['months']),
                                ('Doanh số dòng hàng Completed theo danh mục, chưa gồm phí vận chuyển',
                                 {f'{k} — {categories.get(k, k)}': v for k, v in sorted(m['category_realized_sales'].items(), key=lambda item: -item[1])})]:
        rows += [f'## {title}', '', '| Nhóm | Giá trị |', '|---|---:|']
        rows += [f'| {k} | {v:,} |' for k, v in distribution.items()]
        rows.append('')
    rows += ['## Giả định hành vi và giỏ hàng', '',
             '100 mã KH được chia theo thứ tự mã: 10 khách mới × 1 đơn; 20 khách không thường xuyên × 3; '
             '20 khách định kỳ × 10; 20 khách thân thiết × 20; 20 khách giá trị cao × 25; 10 khách lâu chưa quay lại × 3. '
             'Đây là phân nhóm mô phỏng, không ghi nhãn vào Contact. Khách mới phát sinh tháng 10; khách lâu chưa quay lại chỉ phát sinh trước tháng 3. '
             'Ngày mua còn lại lấy mẫu có trọng số; không phải lịch định kỳ bảo đảm cùng ngày hàng tháng.', '',
             'Giỏ hàng được ghép theo tên sản phẩm thành nhóm chăm sóc da/tóc/cơ thể/trang điểm/thiết bị, '
             'ưu tiên cùng nhóm và chỉ dùng SKU có thật. Đây là quy tắc sinh giỏ, không tạo danh mục mới. '
             'Mỗi đơn 1–4 dòng; nhóm giá trị cao có thể mua số lượng lớn hơn. '
             'Ngày 11/11, 12/12, 8/3, 20/10 có trọng số 4; nửa đầu tháng 2 trọng số 3; giữa/cuối tháng trọng số 2; ngày thường 1. '
             'Các đơn chưa hoàn thành đặt 28–31/10. Không mô phỏng chi nhánh thật; source_store là namespace demo.', '',
             'Giá bán/giá vốn lấy snapshot hiện hữu và giả định cố định cả kỳ. Chiết khấu giả lập 0/5/10/15%, '
             'làm tròn xuống VND. POS không phí giao; kênh khác phí 25.000 khi giá trị hàng dưới 500.000, còn lại miễn phí. '
             'Completed luôn có Payment Paid; Pending/Cancelled có Payment Pending (bản ghi dự kiến, chưa thu tiền); '
             'Processing/Shipping chỉ Paid khi không phải COD. Không có Refund hoặc chứng từ thanh toán đính kèm.', '',
             '## Giao dịch demo', '', '| Scenario | Thành viên | Khóa tra cứu |', '|---|---|---|']
    rows += [f"| {s['scenario_id']} | {s['member']} | {s['order_key'] or 'BLOCKED: chưa có SKU Havatek'} |" for s in data['demo_scenarios']]
    rows += ['', 'Các điều kiện đổi trả tính tại mốc 31/10/2026 và còn phải đối chiếu chính sách của nhóm; '
             'không khẳng định còn hạn vào ngày 27/11/2026. Ngày Completed online trong JSON chỉ là ngày nhận hàng giả lập, '
             'không dùng như bằng chứng giao nhận hoặc ngày bắt đầu bảo hành thật.', '', '## Audit thực tế', '',
             'Frappe 15.127.1, CRM 1.92.0, hasaki_integration 0.0.1. Bench thấy ba App cài trên site: frappe, crm, hasaki_integration. '
             'BeautyMatch có source trong Bench nhưng không nằm trong installed_apps của site; không chỉnh sửa. '
             'Counts trước import: Contact 108; Address 100; User 6; CRM Lead 99; CRM Deal 30; CRM Product 200; '
             'CRM Lead Source 8; HSK Product Category 14; Order 57; Item 57; History 69; Payment 15; Integration Event 257.', '',
             '100 Contact có mã KH; 8 Contact không có mã được loại khỏi mapping, không chỉnh sửa. '
             'CRM Product.custom_category trống; liên kết danh mục thực tế là custom_product_category. '
             '200 SKU có giá bán/giá vốn dương và mapping duy nhất. Không có Havatek. '
             'Controller không tự gán loyalty_eligible, receiver chỉ giữ cờ cũ hoặc mặc định 0.', '',
             'Không phát hiện Notification/Webhook đang bật. Safety preflight đối chiếu Document Events đã audit, '
             'hash controller và các rule động liên quan Order/Payment; thay đổi sẽ làm import dừng thay vì tắt hook. '
             'Site khác có hook Loyalty/Refund/Notification phải được chủ App rà soát trước; không sửa policy để bỏ qua lỗi.', '',
             '## Giới hạn và việc còn lại', '']
    rows += [f'- {limit}' for limit in m['limitations']]
    runtime_report = ROOT / 'docs/demo_deployment_regression.json'
    runtime_passed = runtime_report.exists() and json.loads(runtime_report.read_text())['passed']
    rows += ['', ('- Migration Patch, migrate lần hai, seeder độc lập và regression A4.8 37/37 đã Passed trên crm.localhost; dữ liệu test đã dọn đúng phạm vi.'
                  if runtime_passed else '- Trạng thái runtime chi tiết ở DEMO_DATA_DEPLOYMENT_REPORT.md; không dùng test offline thay bằng chứng database.'),
             '- Install-app lần đầu end-to-end vẫn Not Tested; không tạo/cài lại App để kiểm thử trên site hiện tại. Desk đã được người dùng kiểm tra thủ công và xác nhận đúng.',
             '- Không tạo site thay thế, không restore database và không tạo lại Master Data để vượt giới hạn này.',
             '- Đã backup, xác nhận và bật demo trên crm.localhost; không bật cờ trên production.',
             '- Build wheel bằng flit_core 3.12.0 cô lập trong thư mục tạm Passed: đủ 8 JSON nguyên byte và patch; không cài vào site hoặc thay thư viện Bench.', '',
             'Bằng chứng: demo_site_audit.json, demo_dry_run.json, demo_offline_results.json, demo_package_results.json; manifest chứa checksum từng JSON.']
    write('docs/DEMO_DATA_REPORT.md', '\n'.join(rows) + '\n')
    print(json.dumps({'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'items': m['counts']['items']}))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    run()
