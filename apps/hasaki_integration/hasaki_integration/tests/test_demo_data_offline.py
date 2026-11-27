"""Offline dataset tests and a transaction harness. No connection to any site.

The harness verifies seeder orchestration, not real Frappe ORM/controllers.
"""
import copy
import importlib
import json
import sys
import types
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from hasaki_integration.generate_demo_data import ROOT, generate
from hasaki_integration.validate_demo_data import load, validate


class DatasetTests(unittest.TestCase):
    def test_preservation_exception_is_only_user_last_active(self):
        from hasaki_integration.demo_data_policy import allowed_runtime_changes
        self.assertTrue(allowed_runtime_changes({}))
        self.assertTrue(allowed_runtime_changes({'User': [{'fields': ['last_active']}]}))
        for changes in ({'User': [{'fields': ['api_key']}]},
                        {'User': [{'fields': ['last_active', 'modified']}]},
                        {'User': [{'fields': ['last_active']}, {'fields': ['enabled']}]},
                        {'Contact': [{'fields': ['last_active']}]},
                        {'HSK Order': [{'fields': ['status']}]}) :
            self.assertFalse(allowed_runtime_changes(changes))

    def test_frozen_dataset(self):
        self.assertTrue(validate()['valid'])

    def test_deterministic_generation(self):
        before = {p.name: p.read_bytes() for p in ROOT.glob('*.json')}
        generate()
        self.assertEqual(before, {p.name: p.read_bytes() for p in ROOT.glob('*.json')})

    def test_corrupt_total_rejected(self):
        data = load()
        data['orders'][0]['grand_total'] += 1
        with self.assertRaisesRegex(ValueError, 'Grand total'):
            validate(data)

    def test_uncollected_cod_rejected(self):
        data = load()
        p = next(p for p in data['payments'] if p['status'] == 'Pending')
        p.update(status='Paid', payment_method='cod', paid_at='2026-10-31 12:00:00')
        with self.assertRaises(ValueError):
            validate(data)

    def test_six_customer_cohorts(self):
        data = load()
        self.assertEqual(len(set(data['customer_cohorts'].values())), 6)
        for customer, cohort in data['customer_cohorts'].items():
            rows = [o for o in data['orders'] if o['customer_id'] == customer]
            if cohort == 'lapsed':
                self.assertTrue(all(o['order_date'] < '2026-03' for o in rows))
            if cohort == 'new':
                self.assertEqual(len(rows), 1)


class FakeDB:
    def __init__(self):
        self.rows = []
        self.globals = {}

    def savepoint(self, name):
        self.snapshot = copy.deepcopy((self.rows, self.globals))

    def rollback(self, save_point):
        self.rows, self.globals = self.snapshot

    def set_global(self, key, value):
        self.globals[key] = value

    def get_value(self, dt, name, field):
        return next(row[field] for row in self.rows if row['doctype'] == dt and row['name'] == name)


class SeederHarnessTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        fake = types.ModuleType('frappe')
        fake.conf = {'hasaki_enable_demo_data': 1}
        fake.db = self.db
        fake.get_doc = self.get_doc
        sync = types.ModuleType('frappe.utils.synchronization')
        sync.filelock = lambda *a, **kw: nullcontext()
        self.modules = patch.dict(sys.modules, {'frappe': fake, 'frappe.utils.synchronization': sync})
        self.modules.start()
        # Load a private instance so tests never contaminate a live bench import.
        spec = importlib.util.spec_from_file_location('_demo_seeder_harness', ROOT.parent.parent / 'seed_demo_data.py')
        self.seed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.seed)
        self.fake = fake
        self.data = load()
        self.data['orders'] = self.data['orders'][:3]
        self.data['payments'] = self.data['payments'][:3]
        self.contacts = {o['customer_id']: f'contact-{o["customer_id"]}' for o in self.data['orders']}
        self.products = {i['sku']: f'product-{i["sku"]}' for o in self.data['orders'] for i in o['items']}
        self.patches = [patch.object(self.seed, 'dry_run', side_effect=lambda: {'current': {'marker': self.db.globals.get(self.seed.MARKER)}}),
                        patch.object(self.seed, 'load', return_value=self.data),
                        patch.object(self.seed, '_mapping', return_value=(self.contacts, self.products)),
                        patch.object(self.seed, 'status', return_value={'complete': True})]
        for p in self.patches:
            p.start()
        self.fail_at = None

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.modules.stop()

    def get_doc(self, values):
        harness = self
        class Doc:
            def insert(self):
                if harness.fail_at == len(harness.db.rows):
                    raise RuntimeError('injected failure')
                row = copy.deepcopy(values)
                row['name'] = f'row-{len(harness.db.rows)}'
                if row['doctype'] == 'HSK Order':
                    assert 'payment_status' not in row and 'status_history' not in row
                    assert 'customer_id' not in row
                    assert all('product' in it for it in row['items'])
                    row['payment_status'] = 'Pending'
                else:
                    order = next(o for o in harness.db.rows if o['name'] == row['order'])
                    order['payment_status'] = row['status']
                harness.db.rows.append(row)
                self.name = row['name']
                return self
        return Doc()

    def test_import_and_second_run_preserves_edits(self):
        self.assertEqual(self.seed.seed()['state'], 'imported')
        self.assertEqual(len(self.db.rows), 6)
        self.db.rows[0]['status'] = 'Cancelled'
        before = copy.deepcopy(self.db.rows)
        self.assertEqual(self.seed.seed()['state'], 'already_imported')
        self.assertEqual(before, self.db.rows)

    def test_failure_rolls_back_every_insert_and_marker(self):
        self.fail_at = 3
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            self.seed.seed()
        self.assertEqual(self.db.rows, [])
        self.assertEqual(self.db.globals, {})

    def test_disabled_does_not_read_or_write(self):
        self.fake.conf = {}
        self.assertEqual(self.seed.seed()['state'], 'disabled')
        self.seed.dry_run.assert_not_called()
        self.assertEqual(self.db.rows, [])

    def test_missing_master_fails_before_writes(self):
        self.seed._mapping.side_effect = ValueError('Customer mapping must match exactly once')
        with self.assertRaisesRegex(ValueError, 'mapping'):
            self.seed.seed()
        self.assertEqual(self.db.rows, [])

    def test_after_install_and_after_migrate_share_seeder(self):
        self.assertEqual(self.seed.automatic_seed()['state'], 'imported')
        self.assertEqual(self.seed.automatic_seed()['state'], 'already_imported')

    def test_disabled_install_then_enable_migrate_retries(self):
        self.fake.conf = {}
        self.assertEqual(self.seed.automatic_seed()['state'], 'disabled')
        self.assertEqual(self.db.globals, {})
        self.fake.conf = {'hasaki_enable_demo_data': 1}
        self.assertEqual(self.seed.automatic_seed()['state'], 'imported')
        self.assertEqual(self.seed.automatic_seed()['state'], 'already_imported')

    def test_missing_master_callback_can_retry_without_completion_marker(self):
        self.seed._mapping.side_effect = ValueError('missing master')
        with self.assertRaisesRegex(ValueError, 'missing master'):
            self.seed.automatic_seed()
        self.assertEqual(self.db.globals, {})
        self.assertEqual(self.db.rows, [])
        self.seed._mapping.side_effect = None
        self.assertEqual(self.seed.automatic_seed()['state'], 'imported')

    def test_non_boolean_demo_flag_does_not_enable_dataset(self):
        self.fake.conf = {'hasaki_enable_demo_data': 'false'}
        self.assertEqual(self.seed.automatic_seed()['state'], 'disabled')
        self.seed.dry_run.assert_not_called()

    def test_lifecycle_hook_and_post_model_patch_registration(self):
        import ast
        import configparser
        tree = ast.parse((ROOT.parent.parent / 'hooks.py').read_text())
        assignments = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
        target = 'hasaki_integration.seed_demo_data.automatic_seed'
        self.assertEqual(assignments['after_install'], target)
        self.assertIn(target, assignments['after_migrate'])
        parser = configparser.ConfigParser(allow_no_value=True, delimiters='\n')
        parser.read(ROOT.parent.parent / 'patches.txt')
        self.assertIn('hasaki_integration.patches.seed_demo_transactions_v1', parser['post_model_sync'])

    def test_existing_records_untouched_on_failure(self):
        original = {'doctype': 'HSK Order', 'name': 'existing-a48', 'status': 'Completed'}
        self.db.rows = [copy.deepcopy(original)]
        self.fail_at = 4
        with self.assertRaises(RuntimeError):
            self.seed.seed()
        self.assertEqual(self.db.rows, [original])


if __name__ == '__main__':
    unittest.main()
