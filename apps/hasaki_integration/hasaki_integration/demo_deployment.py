"""Deployment evidence and read-only reconciliation; never exports customer details."""
import gzip
import hashlib
import json
import tarfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import frappe

from hasaki_integration.demo_audit import DOCTYPES
from hasaki_integration.demo_data_policy import allowed_runtime_changes
from hasaki_integration.seed_demo_data import dry_run, load, reconcile, status
from hasaki_integration.validate_demo_data import require

ROOT = Path(__file__).parent.parent


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _write(name, value):
    (ROOT / 'docs' / f'demo_deployment_{name}.json').write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8', newline='\n')
    return value


def verify_backup():
    prefix = '20261127_110325-crm_localhost-'
    folder = Path(frappe.get_site_path('private', 'backups'))
    files = [folder / (prefix + suffix) for suffix in
             ('site_config_backup.json', 'database.sql.gz', 'files.tar', 'private-files.tar')]
    require(all(p.is_file() and p.stat().st_size > 0 for p in files), 'Backup files missing/empty')
    with gzip.open(files[1], 'rb') as stream:
        size = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
    require(size > 100000, 'Database backup unexpectedly small')
    members = {}
    for path in files[2:]:
        with tarfile.open(path) as archive:
            count = 0
            for member in archive:
                if member.isfile():
                    stream = archive.extractfile(member)
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        pass
                count += 1
            members[path.name] = count
    config = json.loads(files[0].read_text())
    require('db_name' in config and 'db_password' in config, 'Backup config incomplete')
    evidence = {'verified': True, 'database_uncompressed_bytes': size, 'tar_members': members,
                'files': [{'path': str(p.resolve()), 'bytes': p.stat().st_size,
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
                'note': 'gzip CRC and tar payload read verified; no restore performed; config values omitted'}
    return _write('backup', evidence)


def _snapshot():
    doctypes = set(DOCTYPES) | {'Role'}
    pending = list(doctypes)
    while pending:
        dt = pending.pop()
        for field in frappe.get_meta(dt).fields:
            if field.fieldtype in ('Table', 'Table MultiSelect') and field.options not in doctypes:
                doctypes.add(field.options)
                pending.append(field.options)
    for dt in ('Email Queue', 'Communication', 'Notification Log', 'Webhook Request Log'):
        if frappe.db.exists('DocType', dt):
            doctypes.add(dt)
    tables = {}
    for dt in sorted(doctypes):
        rows = frappe.get_all(dt, fields=['*'], order_by='name')
        tables[dt] = {'count': len(rows), 'rows': {
            _hash(row.name): {'hash': _hash(row), 'fields': {key: _hash(value) for key, value in row.items()}}
            for row in rows}}
    config = json.loads(Path(frappe.get_site_path('site_config.json')).read_text())
    config.pop('hasaki_enable_demo_data', None)
    return {'site': frappe.local.site, 'checked_at': str(frappe.utils.now_datetime()),
            'tables': tables, 'site_config_except_demo_flag_sha256': _hash(config),
            'dataset': status()}


def baseline():
    backup = json.loads((ROOT / 'docs/demo_deployment_backup.json').read_text())
    require(backup['verified'], 'Backup not verified')
    require(not (ROOT / 'docs/demo_deployment_before.json').exists(), 'Baseline already exists; do not overwrite')
    result = _snapshot()
    _write('before', result)
    return {'counts': {dt: table['count'] for dt, table in result['tables'].items()}, 'snapshot_saved': True}


def preflight():
    from hasaki_integration.seed_demo_data import _safety
    result = dry_run()
    _safety()
    result['pending_patch'] = not bool(frappe.db.exists('Patch Log', {
        'patch': 'hasaki_integration.patches.seed_demo_transactions_v1', 'skipped': 0}))
    require(result['pending_patch'], 'Patch already logged; stop to avoid claiming patch import without evidence')
    result['installed_apps'] = frappe.get_installed_apps()
    return _write('preflight', result)


def compare(phase='after_import', reference='before'):
    old = json.loads((ROOT / 'docs' / f'demo_deployment_{reference}.json').read_text())
    current = _snapshot()
    changed, removed, added = {}, {}, {}
    for dt, table in old['tables'].items():
        now = current['tables'][dt]['rows']
        removed[dt] = len(set(table['rows']) - set(now))
        added[dt] = len(set(now) - set(table['rows']))
        differences = []
        for key, row in table['rows'].items():
            if key in now and row['hash'] != now[key]['hash']:
                fields = sorted(field for field in set(row['fields']) | set(now[key]['fields'])
                                if row['fields'].get(field) != now[key]['fields'].get(field))
                differences.append({'row_hash_id': key, 'fields': fields})
        if differences:
            changed[dt] = differences
    allowed_telemetry = allowed_runtime_changes(changed)
    config_unchanged = old['site_config_except_demo_flag_sha256'] == current['site_config_except_demo_flag_sha256']
    result = {'phase': phase, 'reference': reference, 'counts': {dt: t['count'] for dt, t in current['tables'].items()},
              'added': added, 'removed': removed, 'changed_existing_rows': changed,
              'old_business_rows_unchanged': not any(removed.values()) and allowed_telemetry,
              'site_config_except_demo_flag_unchanged': config_unchanged}
    _write(phase, current)
    _write(phase + '_comparison', result)
    require(result['old_business_rows_unchanged'] and config_unchanged, 'Existing data/config changed: inspect comparison')
    if phase in ('after_migrate2', 'after_seed'):
        # User.last_active is Frappe session telemetry; preserve strict checks for
        # every other field, every transaction, and all additions/deletions.
        require(not any(added.values()) and allowed_telemetry, 'Idempotency check: added/changed business rows')
    return result


def validate_import():
    result = reconcile()
    require(result['complete'] and result['matches_frozen_dataset'], 'Dataset reconciliation failed')
    data = load()
    orders = frappe.get_all('HSK Order', filters={'source_store': 'hasaki-demo-v1'}, fields=['name', 'integration_key', 'grand_total', 'status', 'payment_status', 'source_channel'])
    require(len(orders) == 1200, 'Expected exactly 1200 demo orders')
    names = [o.name for o in orders]
    require(frappe.db.count('HSK Payment', {'order': ['in', names]}) == 1200,
            'Unexpected extra or missing payment on demo orders')
    item_count = frappe.db.count('HSK Order Item', {'parent': ['in', names], 'parenttype': 'HSK Order', 'parentfield': 'items'})
    require(item_count == 3663, 'Expected 3663 demo items')
    history_count = 0
    for row in orders:
        doc = frappe.get_doc('HSK Order', row.name)
        require(len(doc.status_history) == 1, 'Expected one real import-time audit entry')
        entry = doc.status_history[0]
        require(entry.status == doc.status and entry.changed_at and entry.changed_by == 'Administrator', 'Audit status/user missing')
        require(entry.changed_at >= datetime(2026, 11, 27), 'Audit backdated')
        history_count += 1
    manifest = data['manifest']
    require(sum(float(o.grand_total) for o in orders) == manifest['total_value'], 'DB total value mismatch')
    require(sum(float(o.grand_total) for o in orders if o.status == 'Completed' and o.payment_status == 'Paid') == manifest['realized_revenue'], 'DB realized revenue mismatch')
    patch = frappe.db.get_value('Patch Log', {'patch': 'hasaki_integration.patches.seed_demo_transactions_v1'}, ['name', 'creation', 'skipped'], as_dict=True)
    require(patch and not patch.skipped, 'Migration Patch not successfully logged')
    scenarios = []
    for scenario in data['demo_scenarios']:
        row = dict(scenario)
        if row['order_key']:
            name = frappe.db.get_value('HSK Order', {'integration_key': row['order_key']}, 'name')
            row['document_name'] = name
            row['desk_path'] = f'/app/hsk-order/{name}'
            row['payment_names'] = frappe.get_all('HSK Payment', filters={'order': name}, pluck='name')
        scenarios.append(row)
    _write('scenarios', scenarios)
    return _write('validation', {'valid': True, 'orders': len(orders), 'items': item_count,
                  'payments': result['payments_present'], 'real_audit_entries': history_count,
                  'business_history_json_events': manifest['counts']['business_status_events'],
                  'total_value': manifest['total_value'], 'realized_revenue': manifest['realized_revenue'],
                  'statuses': dict(Counter(o.status for o in orders)),
                  'payment_statuses': dict(Counter(o.payment_status for o in orders)),
                  'channels': dict(Counter(o.source_channel for o in orders)), 'patch_log': patch,
                  'all_links_items_payments_match_frozen_dataset': True})


def run_regression():
    """Run with scoped cleanup rather than leaving HTTP test records behind."""
    from hasaki_integration.demo_regression import run
    return run()


def after_migrate2():
    return compare('after_migrate2', 'after_import')


def after_seed():
    return compare('after_seed', 'after_migrate2')


def after_regression():
    return compare('after_regression', 'before')


def regression_preservation():
    result = compare('regression_preservation', 'regression_before')
    require(not any(result['added'].values()), 'Regression left additional records')
    return result


def lifecycle_contract():
    """Read actual hook registration and installer ordering; never install an app."""
    import inspect
    from frappe import installer
    from hasaki_integration import hooks
    from hasaki_integration.seed_demo_data import automatic_seed
    target = 'hasaki_integration.seed_demo_data.automatic_seed'
    require(hooks.after_install == target and target in hooks.after_migrate, 'Lifecycle hooks not registered')
    actual = frappe.get_hooks(app_name='hasaki_integration')
    require(target in actual.after_install and target in actual.after_migrate, 'Runtime hooks differ from source')
    source = inspect.getsource(installer.install_app)
    require(source.index('set_all_patches_as_completed(name)') < source.index('for after_install in app_hooks.after_install'),
            'Installer ordering changed; review retry behavior')
    result = automatic_seed()
    require(result['state'] == 'already_imported', 'Existing-site lifecycle callback not idempotent')
    return _write('lifecycle', {'hook_registration': 'Passed', 'installer_order_source_check': 'Passed',
        'callback_on_existing_dataset': 'Passed', 'fresh_install_end_to_end': 'Not Tested',
        'reason': 'User forbids creating/installing/reinstalling App or replacing site',
        'callback_result': result})


def missing_master_checks():
    """Exercise fail-closed mapping against live DB using absent IDs; no master writes."""
    from hasaki_integration.seed_demo_data import _mapping
    missing_customer = 'DEMO-V1-ABSENT-CUSTOMER-FOR-TEST'
    missing_sku = 'DEMO-V1-ABSENT-SKU-FOR-TEST'
    require(not frappe.db.exists('Contact', {'custom_customer_id': missing_customer}), 'Test customer ID already exists')
    require(not frappe.db.exists('CRM Product', {'product_code': missing_sku}), 'Test SKU already exists')
    customer = load()['orders'][0]['customer_id']
    checks = [({'orders': [{'customer_id': missing_customer, 'items': []}]}, 'Customer mapping'),
              ({'orders': [{'customer_id': customer, 'items': [{'sku': missing_sku}]}]}, 'Product mapping')]
    outcomes = []
    for data, expected in checks:
        try:
            _mapping(data)
        except ValueError as exc:
            require(expected in str(exc), 'Unexpected mapping failure')
            outcomes.append({'case': expected, 'status': 'Passed', 'database_writes': 0})
        else:
            raise AssertionError('Missing master was not rejected')
    return _write('missing_master', {'results': outcomes, 'database_writes': 0})


def audit_release():
    """Check explicit release allowlist against live secrets in memory; never export them."""
    from frappe.utils.password import get_decrypted_password
    config = json.loads(Path(frappe.get_site_path('site_config.json')).read_text())
    values = set()
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in {'db_password', 'encryption_key', 'secret', 'api_key', 'api_secret', 'webhook_secret'} and isinstance(item, str):
                    values.add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(config)
    for user in frappe.get_all('User', fields=['name', 'api_key']):
        if user.api_key:
            values.add(user.api_key)
            secret = get_decrypted_password('User', user.name, 'api_secret', raise_exception=False)
            if secret:
                values.add(secret)
    candidates = (ROOT / 'docs/DEMO_DATA_FILES.txt').read_text().splitlines()
    checked = 0
    violations = []
    short_secrets = sum(0 < len(value) < 8 for value in values)
    for relative in candidates:
        path = ROOT / relative
        require(path.resolve().is_relative_to(ROOT.resolve()) and path.is_file(), 'Invalid release path')
        require(not any(part.lower() in {'.git', 'sites', 'backups', '.venv', 'env', '__pycache__'} for part in path.parts), 'Local/environment path in release')
        require(path.suffix not in {'.sql', '.gz', '.tar', '.dump', '.bak', '.key', '.pem', '.pyc'}, 'Prohibited release artifact')
        require(not path.name.startswith(('site_config', 'common_site_config', '.env')), 'Site/environment config in release')
        require(not (path.name.startswith('demo_deployment_') and path.name.endswith('.json') and
                    path.name in {'demo_deployment_before.json', 'demo_deployment_after_import.json',
                                  'demo_deployment_after_migrate2.json', 'demo_deployment_after_seed.json',
                                  'demo_deployment_after_regression.json', 'demo_deployment_regression_before.json',
                                  'demo_deployment_regression_preservation.json'}), 'Detailed fingerprint in release')
        text = path.read_text(encoding='utf-8')
        if any(value in text for value in values if len(value) >= 8):
            violations.append(relative)
        checked += 1
    master = load()['master_snapshot']
    require(all(set(row) == {'custom_customer_id'} for row in master['contacts']), 'Contact personal fields in snapshot')
    report = {'files_checked': checked, 'secret_matches': violations, 'short_secrets_not_scanned': short_secrets,
              'contact_export_fields': ['custom_customer_id'], 'forbidden_artifacts': 0,
              'detailed_row_fingerprints': 'Excluded from release and ignored in Git',
              'scope': 'Allowlist paths, frozen contact schema, and actual site/API secret values checked in memory',
              'passed': not violations and short_secrets == 0}
    _write('release_audit', report)
    require(report['passed'], 'Release audit failed; inspect filenames only, never print secret values')
    return report
