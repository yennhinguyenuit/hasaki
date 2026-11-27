"""Offline, deterministic generator. Migration only reads the frozen JSON files."""
import hashlib
import json
import random
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent / 'demo_data' / 'v1'
SEED = 20261101


def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def generate():
    rng = random.Random(SEED)
    master = json.loads((ROOT / 'master_snapshot.json').read_text(encoding='utf-8'))
    customers = sorted(c['custom_customer_id'] for c in master['contacts'] if c['custom_customer_id'])
    assert len(customers) == len(set(customers)) == 100
    products = [p for p in master['products'] if not p['disabled']]
    assert all(p['standard_rate'] > 0 and p['custom_cost_price'] > 0 for p in products)
    groups = defaultdict(list)
    def family(p):
        name = ''.join(c for c in unicodedata.normalize('NFD', p['product_name'].lower()) if unicodedata.category(c) != 'Mn').replace('đ', 'd')
        for group, terms in [('devices', ['may ', 'ban chai dien', 'luoc dien']),
                             ('hair', ['dau goi', 'dau xa', 'toc']),
                             ('body', ['sua tam', 'co the', 'duong the']),
                             ('makeup', ['son ', 'trang diem', 'phan ', 'mascara', 'ke mat'])]:
            if any(term in name for term in terms):
                return group
        return 'skincare'
    for p in products:
        # Analytical basket families do not create or change product categories.
        groups[family(p)].append(p)
    cohorts = [('new', 10, 1), ('infrequent', 20, 3), ('regular', 20, 10),
               ('loyal', 20, 20), ('high_value', 20, 25), ('lapsed', 10, 3)]
    assignments, offset = [], 0
    for cohort, size, frequency in cohorts:
        for customer in customers[offset:offset + size]:
            assignments.extend([(customer, cohort)] * frequency)
        offset += size
    rng.shuffle(assignments)
    channels = ['WooCommerce'] * 660 + ['POS'] * 480 + ['Manual'] * 60
    rng.shuffle(channels)
    statuses = ['Completed'] * 1020 + ['Cancelled'] * 72 + ['Shipping'] * 48 + ['Processing'] * 36 + ['Pending'] * 24
    rng.shuffle(statuses)
    # Swap channels, preserving exact quotas, so no POS order has Shipping.
    for i, status in enumerate(statuses):
        if status == 'Shipping' and channels[i] == 'POS':
            j = next(j for j in range(1200) if statuses[j] != 'Shipping' and channels[j] != 'POS')
            channels[i], channels[j] = channels[j], channels[i]
    start = datetime(2025, 11, 1, 9)
    days = [start + timedelta(days=i) for i in range(361)]
    def weight(d):
        return (4 if (d.month, d.day) in [(11, 11), (12, 12), (3, 8), (10, 20)] else
                3 if (d.month == 2 and d.day <= 16) else 2 if d.day in range(14, 17) or d.day >= 27 else 1)
    orders, payments, history, cohort_map = [], [], [], {}
    for i, ((customer, cohort), channel, status) in enumerate(zip(assignments, channels, statuses), 1):
        date_pool = [d for d in days if (d < datetime(2026, 3, 1) if cohort == 'lapsed' else
                                       d >= datetime(2026, 10, 1) if cohort == 'new' else True)]
        dt = rng.choices(date_pool, weights=[weight(d) for d in date_pool])[0]
        if status in ('Pending', 'Processing', 'Shipping'):
            # Keep lapsed customers inactive; exchange with an active cohort.
            if cohort == 'lapsed':
                j = next(j for j in range(i, 1200) if assignments[j][1] not in ('lapsed', 'new') and statuses[j] == 'Completed')
                assignments[i - 1], assignments[j] = assignments[j], assignments[i - 1]
                customer, cohort = assignments[i - 1]
            dt = datetime(2026, 10, 28 + rng.randrange(4), 9)
        dt += timedelta(minutes=rng.randrange(540))
        key_id = f'DEMO-V1-{i:04d}'
        store = 'hasaki-demo-v1'
        key = f'woo:{store}:{key_id}' if channel == 'WooCommerce' else f'demo:v1:{channel.lower()}:{key_id}'
        size = {'new': 1, 'infrequent': 2, 'regular': 3, 'loyal': 3, 'high_value': rng.choice([3, 3, 4]), 'lapsed': 2}[cohort]
        anchor = rng.choice(products)
        pool = groups[family(anchor)]
        selected = rng.sample(pool, min(size, len(pool)))
        if len(selected) < size:
            selected += rng.sample([p for p in products if p not in selected], size - len(selected))
        if cohort == 'high_value':
            selected.sort(key=lambda p: p['standard_rate'], reverse=True)
        rate = rng.choice([0, 0, 5, 10, 15]) if weight(dt) > 1 else rng.choice([0, 0, 5])
        items = []
        for n, p in enumerate(selected, 1):
            qty = rng.choice([1, 1, 2, 3]) if cohort == 'high_value' else rng.choice([1, 1, 1, 2])
            price = int(p['standard_rate'])
            discount = price * qty * rate // 100
            items.append(dict(sku=p['product_code'], external_line_id=f'{key_id}-{n}', qty=qty,
                              unit_price=price, discount_amount=discount, line_total=qty * price - discount,
                              cost_price=int(p['custom_cost_price']), loyalty_eligible=0))
        shipping = 0 if channel == 'POS' or sum(it['line_total'] for it in items) >= 500000 else 25000
        path = ['Pending', 'Completed'] if channel == 'POS' else ['Pending', 'Processing', 'Shipping', 'Completed']
        if status == 'Cancelled':
            path = ['Pending', 'Cancelled']
        else:
            path = path[:path.index(status) + 1] if status in path else ['Pending', status]
        timeline = []
        for n, s in enumerate(path):
            elapsed = timedelta(minutes=5 * n) if channel == 'POS' or status != 'Completed' else timedelta(hours=24 * n)
            timeline.append({'status': s, 'business_at': str(dt + elapsed)})
        history.append({'integration_key': key, 'simulated': True, 'events': timeline})
        order = dict(customer_id=customer, source_channel=channel, source_store=store,
                     external_order_id=key_id, integration_key=key, order_date=str(dt), status=status,
                     currency='VND', shipping_total=shipping, discount_total=sum(it['discount_amount'] for it in items),
                     grand_total=sum(it['line_total'] for it in items) + shipping, items=items)
        orders.append(order)
        cohort_map[customer] = cohort
        method = rng.choice(['cash', 'bank_transfer', 'card', 'e_wallet']) if channel == 'POS' else rng.choice(['cod', 'bank_transfer', 'card', 'e_wallet'])
        paid = status == 'Completed' or (status in ('Processing', 'Shipping') and method != 'cod')
        payments.append(dict(order_key=key, payment_integration_key=f'demo:v1:payment:{key_id}',
                             transaction_id=f'SIMULATED-{key_id}', payment_method=method,
                             status='Paid' if paid else 'Pending', amount=order['grand_total'],
                             paid_at=(timeline[-1]['business_at'] if method == 'cod' or channel == 'POS' else str(dt + timedelta(minutes=2))) if paid else None))
    scenarios = []
    def scenario(sid, member, title, predicate, condition, expected):
        o = next(o for o in orders if predicate(o))
        scenarios.append(dict(scenario_id=sid, member=member, business=title, order_key=o['integration_key'],
                              customer_id=o['customer_id'], skus=[it['sku'] for it in o['items']],
                              initial_conditions=condition, purpose=title, expected_result=expected))
    scenario('NGHI-01', 'Nghi', 'Đổi trả một phần / hoàn tiền toàn phần', lambda o: o['status'] == 'Completed' and len(o['items']) >= 3 and o['order_date'] >= '2026-10-20',
             'Completed + Paid; mốc demo 31/10/2026; cần đối chiếu chính sách đổi trả của nhóm.', 'Có đơn nhiều dòng để mở nghiệp vụ riêng; dataset không tạo Return/Refund.')
    scenario('NGHI-02', 'Nghi', 'Đơn cũ để kiểm tra thời hạn đổi trả', lambda o: o['status'] == 'Completed' and o['order_date'] < '2026-01',
             'Đối chiếu thời hạn chính sách thực tế.', 'Ứng dụng phụ trách quyết định còn/hết điều kiện.')
    scenario('TRAM-01', 'Trâm', 'POS hoàn thành và mua lặp lại', lambda o: o['source_channel'] == 'POS' and o['status'] == 'Completed' and cohort_map[o['customer_id']] == 'loyal',
             'Completed + Paid; loyalty_eligible=0; thiếu quy tắc phê duyệt.', 'Chỉ chuẩn bị giao dịch; không tự cộng điểm.')
    scenario('TRAM-02', 'Trâm', 'Đơn online không mặc định tích điểm', lambda o: o['source_channel'] == 'WooCommerce' and o['status'] == 'Completed',
             'loyalty_eligible=0.', 'Không tạo Loyalty Transaction.')
    scenario('TUONG-01', 'Tường', 'CLV/RFM/doanh thu', lambda o: cohort_map[o['customer_id']] == 'high_value' and o['status'] == 'Completed',
             'Chỉ Completed + Paid là doanh thu thực hiện.', 'Phân tích được doanh thu, tần suất, giá vốn; CAC/ABC cần dữ liệu chi phí riêng.')
    scenarios.append(dict(scenario_id='NHI-BLOCKED', member='Nhi', business='Bảo hành Havatek', order_key=None,
                          customer_id=None, skus=[], initial_conditions='Không có SKU Havatek trong 200 sản phẩm.',
                          purpose='Bảo hành còn hạn/hết hạn/POS/online/thiếu bằng chứng', expected_result='Blocked: nhóm cung cấp Master Data đã duyệt; không tự thêm sản phẩm.'))
    files = {'orders.json': orders, 'payments.json': payments, 'status_history.json': history,
             'demo_scenarios.json': scenarios, 'customer_cohorts.json': cohort_map}
    for filename, value in files.items():
        dump(filename, value)
    counts = Counter(o['customer_id'] for o in orders)
    realized = [o for o in orders if o['status'] == 'Completed']
    category_sales = Counter()
    sku_category = {p['product_code']: p['custom_product_category'] for p in products}
    for o in realized:
        for it in o['items']:
            category_sales[sku_category[it['sku']]] += it['line_total']
    checksums = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                 for name in [*files, 'master_snapshot.json', 'safety_policy.json']}
    manifest = dict(version='1.0', seed=SEED, simulated=True, currency='VND',
                    period=['2025-11-01', '2026-10-31'], historical_orders=0,
                    counts=dict(orders=len(orders), items=sum(len(o['items']) for o in orders), payments=len(payments),
                                business_status_events=sum(len(h['events']) for h in history), customers=len(counts)),
                    channels=dict(Counter(o['source_channel'] for o in orders)),
                    statuses=dict(Counter(o['status'] for o in orders)),
                    months=dict(sorted(Counter(o['order_date'][:7] for o in orders).items())),
                    total_value=sum(o['grand_total'] for o in orders),
                    realized_revenue=sum(o['grand_total'] for o in realized),
                    discounts=sum(o['discount_total'] for o in orders),
                    realized_cost=sum(it['qty'] * it['cost_price'] for o in realized for it in o['items']),
                    total_cost=sum(it['qty'] * it['cost_price'] for o in orders for it in o['items']),
                    repeat_purchase_rate=sum(n > 1 for n in counts.values()) / len(counts),
                    category_realized_sales=dict(category_sales), checksums=checksums,
                    mapping={'customer': 'Contact.custom_customer_id (exact, unique at runtime)',
                             'product': 'CRM Product.product_code (exact, unique at runtime)'},
                    limitations=['Dữ liệu giả lập đồ án, không phải số liệu nội bộ Hasaki.',
                                 'Không có SKU Havatek; không tạo đơn lịch sử hoặc phiếu bảo hành.',
                                 'Lịch sử nghiệp vụ riêng; audit trail database ghi thời điểm import thực.',
                                 'Giá bán/giá vốn snapshot được giả định cố định cả kỳ; chiết khấu 0/5/10/15%.',
                                 'Giữ loyalty_eligible=0 vì chưa có quy tắc nhóm được triển khai.',
                                 'Demo đổi trả tính tại 31/10/2026; không xác nhận đủ điều kiện tại ngày hiện tại.',
                                 'Ngày Completed online chỉ là ngày nhận giả lập trong JSON, không phải bằng chứng giao nhận.',
                                 'CAC/ABC cần dữ liệu chi phí; không tạo marketing cost hoặc voucher.'])
    manifest['average_order_value'] = round(manifest['total_value'] / len(orders), 2)
    manifest['gross_profit_before_other_costs'] = manifest['realized_revenue'] - manifest['realized_cost']
    dump('manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=True, indent=2))
