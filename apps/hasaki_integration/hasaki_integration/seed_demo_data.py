"""Opt-in ORM import. Never updates an existing demo transaction or master row."""
import hashlib
import json
from pathlib import Path

import frappe

from hasaki_integration.generate_demo_data import ROOT
from hasaki_integration.validate_demo_data import load, require, validate

MARKER = 'hasaki_demo_transactions_v1'
TARGETS = ('HSK Order', 'HSK Order Item', 'HSK Order Status History', 'HSK Payment')


def _digest():
    return hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest()


def _safety():
    policy = json.loads((ROOT / 'safety_policy.json').read_text(encoding='utf-8'))
    hooks = frappe.get_hooks('doc_events')
    relevant = {dt: hooks.get(dt, {}) for dt in ('*', *TARGETS)}
    require(relevant == policy['doc_events'], 'Document hooks changed: audit side effects before importing')
    overrides = frappe.get_hooks('override_doctype_class')
    require(not any(overrides.get(dt) for dt in TARGETS), 'Transaction controller override requires audit')
    package = Path(__file__).parent
    for filename, digest in policy['controllers'].items():
        require(hashlib.sha256((package / filename).read_text(encoding='utf-8').encode()).hexdigest() == digest,
                f'Controller changed, review required: {filename}')
    # Do not disable hooks. Reject active rules that could send or create business records.
    checks = [
        ('Notification', {'enabled': 1, 'document_type': ['in', TARGETS]}),
        ('Webhook', {'enabled': 1, 'webhook_doctype': ['in', TARGETS]}),
        ('Server Script', {'disabled': 0, 'reference_doctype': ['in', TARGETS]}),
        ('Workflow', {'is_active': 1, 'document_type': ['in', TARGETS]}),
        ('Assignment Rule', {'disabled': 0, 'document_type': ['in', TARGETS]}),
        ('Energy Point Rule', {'enabled': 1, 'reference_doctype': ['in', TARGETS]}),
        ('Milestone Tracker', {'disabled': 0, 'document_type': ['in', TARGETS]}),
    ]
    for dt, filters in checks:
        if not frappe.db.exists('DocType', dt):
            continue
        meta = frappe.get_meta(dt)
        require(all(meta.has_field(f) for f in filters), f'Safety metadata changed: {dt}')
        require(not frappe.db.exists(dt, filters), f'Active {dt} for transactions requires integration review')


def _schema():
    for dt in (*TARGETS, 'HSK Integration Event'):
        slug = dt.lower().replace(' ', '_')
        source = json.loads((Path(__file__).parent / 'hasaki_integration' / 'doctype' / slug / f'{slug}.json').read_text())
        require(frappe.db.exists('DocType', dt), f'Missing DocType {dt}; migrate schema first')
        meta = frappe.get_meta(dt)
        require(meta.autoname == source.get('autoname') and meta.istable == source['istable'], f'Naming/table mismatch {dt}')
        for field in source['fields']:
            actual = meta.get_field(field['fieldname'])
            require(actual is not None, f'Missing {dt}.{field["fieldname"]}')
            for prop in ('fieldtype', 'options', 'reqd', 'unique'):
                require((actual.get(prop) or 0) == (field.get(prop) or 0), f'Schema mismatch {dt}.{field["fieldname"]}.{prop}')


def _mapping(data):
    contacts, products = {}, {}
    for code in sorted({o['customer_id'] for o in data['orders']}):
        matches = frappe.get_all('Contact', filters={'custom_customer_id': code}, pluck='name')
        require(len(matches) == 1, f'Customer mapping must match exactly once: {code}')
        contacts[code] = matches[0]
    for sku in sorted({it['sku'] for o in data['orders'] for it in o['items']}):
        matches = frappe.get_all('CRM Product', filters={'product_code': sku}, fields=['name', 'disabled', 'custom_cost_price'])
        require(len(matches) == 1 and not matches[0].disabled, f'Product mapping missing/ambiguous/disabled: {sku}')
        require(matches[0].custom_cost_price and matches[0].custom_cost_price > 0, f'Missing master cost: {sku}')
        products[sku] = matches[0].name
    for category in {p['custom_product_category'] for p in data['master_snapshot']['products']}:
        require(category and frappe.db.exists('HSK Product Category', category), f'Missing category: {category}')
    return contacts, products


def status():
    data = load()
    keys = [o['integration_key'] for o in data['orders']]
    payment_keys = [p['payment_integration_key'] for p in data['payments']]
    order_count = frappe.db.count('HSK Order', {'integration_key': ['in', keys]})
    payment_count = frappe.db.count('HSK Payment', {'payment_integration_key': ['in', payment_keys]})
    raw = frappe.db.get_global(MARKER)
    marker = json.loads(raw) if raw else None
    return {'enabled': frappe.conf.get('hasaki_enable_demo_data') in (True, 1),
            'marker': marker, 'orders_present': order_count, 'payments_present': payment_count,
            'complete': bool(marker and marker.get('manifest_sha256') == _digest() and order_count == 1200 and payment_count == 1200),
            'note': 'Presence check only; edited transactions are preserved. Use reconcile for drift.'}


def dry_run():
    data = load()
    result = validate(data)
    _schema()
    _safety()
    contacts, products = _mapping(data)
    current = status()
    if not current['marker']:
        require(current['orders_present'] == 0 and current['payments_present'] == 0,
                'Reserved demo keys already exist without completion marker; do not overwrite')
        transactions = [p['transaction_id'] for p in data['payments']]
        require(not frappe.db.exists('HSK Payment', {'transaction_id': ['in', transactions]}), 'Transaction ID collision')
        identities = [o['external_order_id'] for o in data['orders']]
        require(not frappe.db.exists('HSK Order', {'source_store': 'hasaki-demo-v1', 'external_order_id': ['in', identities]}), 'Source identity collision')
    else:
        require(current['marker']['manifest_sha256'] == _digest(), 'Installed dataset differs from package; do not overwrite')
    return {**result, 'mapped_contacts': len(contacts), 'mapped_products': len(products),
            'current': current, 'database_writes': 0}


def seed():
    """Called by patch, after_install, after_migrate, or explicit bench execute.

    Operator must enable only on a confirmed demo site after backup and dry-run.
    No commit here: caller (patch/install/migrate/bench execute) owns the transaction.
    """
    if frappe.conf.get('hasaki_enable_demo_data') not in (True, 1):
        return {'state': 'disabled', 'imported': False}
    from frappe.utils.synchronization import filelock

    with filelock('hasaki-demo-v1', timeout=1):
        report = dry_run()
        if report['current']['marker']:
            # A user may edit/delete demo documents. Never restore their old state.
            return {'state': 'already_imported', **report['current']}
        data = load()
        contacts, products = _mapping(data)
        payments = {p['order_key']: p for p in data['payments']}
        frappe.db.savepoint('hasaki_demo_v1')
        try:
            for row in data['orders']:
                values = {k: v for k, v in row.items() if k not in ('customer_id', 'items')}
                values.update(doctype='HSK Order', customer=contacts[row['customer_id']],
                              items=[dict(it, product=products[it['sku']]) for it in row['items']])
                order = frappe.get_doc(values).insert()
                p = {k: v for k, v in payments[row['integration_key']].items() if k != 'order_key'}
                frappe.get_doc(dict(p, doctype='HSK Payment', order=order.name)).insert()
                require(frappe.db.get_value('HSK Order', order.name, 'payment_status') == p['status'], 'Controller payment mismatch')
            frappe.db.set_global(MARKER, json.dumps({'version': '1.0', 'manifest_sha256': _digest()}))
            return {'state': 'imported', **status()}
        except Exception:
            frappe.db.rollback(save_point='hasaki_demo_v1')
            raise


def automatic_seed():
    """Retry after schema sync, including when disabled patch was previously logged."""
    return seed()


def reconcile():
    """Read-only dataset/database comparison; reports edits without undoing them."""
    data = load()
    contacts, products = _mapping(data)
    differences = []
    for row in data['orders']:
        name = frappe.db.get_value('HSK Order', {'integration_key': row['integration_key']}, 'name')
        if not name:
            differences.append({'key': row['integration_key'], 'difference': 'missing_order'})
            continue
        doc = frappe.get_doc('HSK Order', name)
        fields = [k for k in row if k not in ('items', 'customer_id')]
        drift = [k for k in fields if str(doc.get(k)) != str(row[k]) and not
                 (k in ('grand_total', 'discount_total', 'shipping_total') and float(doc.get(k)) == row[k])]
        if doc.customer != contacts[row['customer_id']]:
            drift.append('customer')
        if len(doc.items) != len(row['items']):
            drift.append('items.length')
        else:
            for actual, expected in zip(doc.items, row['items']):
                if actual.product != products[expected['sku']] or any(actual.get(k) != v for k, v in expected.items()):
                    drift.append('items')
                    break
        expected_p = next(p for p in data['payments'] if p['order_key'] == row['integration_key'])
        payment_name = frappe.db.get_value('HSK Payment', {'payment_integration_key': expected_p['payment_integration_key']}, 'name')
        if not payment_name:
            drift.append('missing_payment')
        else:
            p = frappe.get_doc('HSK Payment', payment_name)
            if p.order != name or any(str(p.get(k)) != str(v) for k, v in expected_p.items()
                                     if k not in ('order_key', 'amount', 'paid_at')) or float(p.amount) != expected_p['amount'] or str(p.paid_at) != str(expected_p['paid_at']):
                drift.append('payment')
        if doc.payment_status != expected_p['status']:
            drift.append('payment_status')
        if drift:
            differences.append({'key': row['integration_key'], 'difference': drift})
    return {**status(), 'differences': differences, 'matches_frozen_dataset': not differences}
