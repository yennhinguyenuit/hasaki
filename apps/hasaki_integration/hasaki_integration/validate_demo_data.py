"""Strict offline validation, also called before any database operation."""
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal

from hasaki_integration.generate_demo_data import ROOT


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    names = ['manifest', 'master_snapshot', 'orders', 'payments', 'status_history', 'demo_scenarios', 'customer_cohorts']
    return {name: json.loads((ROOT / f'{name}.json').read_text(encoding='utf-8')) for name in names}


def validate(data=None):
    data = data or load()
    m = data['manifest']
    for name, digest in m['checksums'].items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f'Checksum mismatch: {name}')
    orders, payments = data['orders'], data['payments']
    require(len(orders) == 1200, 'Order count')
    require(3000 <= sum(len(o['items']) for o in orders) <= 4000, 'Item count')
    require(Counter(o['source_channel'] for o in orders) == {'WooCommerce': 660, 'POS': 480, 'Manual': 60}, 'Channels')
    require(Counter(o['status'] for o in orders) == {'Completed': 1020, 'Cancelled': 72, 'Shipping': 48, 'Processing': 36, 'Pending': 24}, 'Statuses')
    products = {p['product_code']: p for p in data['master_snapshot']['products']}
    customers = {c['custom_customer_id'] for c in data['master_snapshot']['contacts'] if c['custom_customer_id']}
    keys = [o['integration_key'] for o in orders]
    require(len(set(keys)) == len(keys), 'Duplicate order key')
    by_key = {o['integration_key']: o for o in orders}
    for o in orders:
        require(o['customer_id'] in customers, 'Unknown customer')
        require('2025-11-01' <= o['order_date'] <= '2026-10-31 23:59:59', 'Date range')
        require(o['currency'] == 'VND', 'Currency')
        require(o['source_store'] == 'hasaki-demo-v1', 'Namespace')
        if o['source_channel'] == 'WooCommerce':
            require(o['integration_key'] == f"woo:{o['source_store']}:{o['external_order_id']}", 'Woo key')
        else:
            require(o['integration_key'] == f"demo:v1:{o['source_channel'].lower()}:{o['external_order_id']}", 'POS/Manual key')
        if o['source_channel'] == 'POS':
            require(o['shipping_total'] == 0 and o['status'] != 'Shipping', 'POS shipping')
        require('payment_status' not in o and 'status_history' not in o, 'Controller-owned fields')
        for it in o['items']:
            p = products[it['sku']]
            require(it['qty'] > 0 and it['unit_price'] == p['standard_rate'] and it['cost_price'] == p['custom_cost_price'] > 0, 'Price/cost')
            require(0 <= it['discount_amount'] <= it['qty'] * it['unit_price'], 'Discount')
            require(it['line_total'] == it['qty'] * it['unit_price'] - it['discount_amount'], 'Line total')
            require(it['loyalty_eligible'] == 0, 'Unapproved loyalty eligibility')
        require(o['discount_total'] == sum(it['discount_amount'] for it in o['items']), 'Discount total')
        require(o['grand_total'] == sum(it['line_total'] for it in o['items']) + o['shipping_total'], 'Grand total')
    require(len(payments) == len(orders), 'Payment count')
    for field in ('payment_integration_key', 'transaction_id', 'order_key'):
        require(len({p[field] for p in payments}) == len(payments), f'Duplicate payment {field}')
    histories = {h['integration_key']: h['events'] for h in data['status_history']}
    require(set(histories) == set(keys), 'History links')
    for p in payments:
        o = by_key[p['order_key']]
        require(p['amount'] == o['grand_total'], 'Payment amount')
        require(p['transaction_id'].startswith('SIMULATED-'), 'Transaction namespace')
        require(p['status'] in ('Paid', 'Pending'), 'Refund excluded')
        require(o['status'] != 'Completed' or p['status'] == 'Paid', 'Completed unpaid')
        require(o['status'] not in ('Pending', 'Cancelled') or p['status'] == 'Pending', 'Pending/cancelled paid')
        require(not (p['payment_method'] == 'cod' and o['status'] != 'Completed' and p['status'] == 'Paid'), 'Uncollected COD')
        require((p['paid_at'] is not None) == (p['status'] == 'Paid'), 'Payment date')
        if p['paid_at']:
            require(o['order_date'] <= p['paid_at'] <= '2026-10-31 23:59:59', 'Payment chronology')
        events = histories[o['integration_key']]
        require(events[0]['status'] == 'Pending' and events[-1]['status'] == o['status'], 'Lifecycle')
        require([e['business_at'] for e in events] == sorted(e['business_at'] for e in events), 'History chronology')
        require(events[-1]['business_at'] <= '2026-10-31 23:59:59', 'History range')
    for s in data['demo_scenarios']:
        if s['order_key']:
            o = by_key[s['order_key']]
            require(s['customer_id'] == o['customer_id'] and s['skus'] == [it['sku'] for it in o['items']], 'Scenario mapping')
    completed = [o for o in orders if o['status'] == 'Completed']
    expected_counts = {'orders': len(orders), 'items': sum(len(o['items']) for o in orders),
                       'payments': len(payments), 'customers': len({o['customer_id'] for o in orders}),
                       'business_status_events': sum(len(h['events']) for h in data['status_history'])}
    require(m['counts'] == expected_counts, 'Manifest counts')
    require(m['channels'] == Counter(o['source_channel'] for o in orders), 'Manifest channels')
    require(m['statuses'] == Counter(o['status'] for o in orders), 'Manifest statuses')
    require(m['months'] == Counter(o['order_date'][:7] for o in orders), 'Manifest months')
    for field, expected in [('total_value', sum(o['grand_total'] for o in orders)),
                            ('realized_revenue', sum(o['grand_total'] for o in completed)),
                            ('discounts', sum(o['discount_total'] for o in orders)),
                            ('realized_cost', sum(it['qty'] * it['cost_price'] for o in completed for it in o['items'])),
                            ('total_cost', sum(it['qty'] * it['cost_price'] for o in orders for it in o['items']))]:
        require(m[field] == expected, f'Manifest {field}')
    return {'valid': True, **m['counts']}


if __name__ == '__main__':
    print(json.dumps(validate()))
