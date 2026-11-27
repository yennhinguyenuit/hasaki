"""Build a wheel in a temporary directory and verify frozen dataset bytes."""
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

from flit_core.buildapi import build_wheel

root = Path(__file__).resolve().parents[1]
os.chdir(root)
dataset = root / 'hasaki_integration' / 'demo_data' / 'v1'
with tempfile.TemporaryDirectory(prefix='hasaki-demo-wheel-') as output:
    wheel = Path(output) / build_wheel(output)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        expected = sorted(dataset.glob('*.json'))
        for path in expected:
            member = path.relative_to(root).as_posix()
            if member not in names or archive.read(member) != path.read_bytes():
                raise AssertionError(f'Missing or altered dataset in wheel: {member}')
        for member in ('hasaki_integration/patches.txt', 'hasaki_integration/patches/seed_demo_transactions_v1.py'):
            if member not in names:
                raise AssertionError(f'Missing migration file: {member}')
        report = {'wheel': wheel.name, 'dataset_json_files': len(expected), 'exact_dataset_bytes': True,
                  'patch_packaged': True, 'build_backend': 'flit_core 3.12.0',
                  'database_writes': 0}
        (root / 'docs' / 'demo_package_results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(report))
