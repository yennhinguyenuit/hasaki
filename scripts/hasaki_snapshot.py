#!/usr/bin/env python3
"""Encrypt/decrypt a Frappe bench backup as one portable Git artifact.
Run with the frappe bench Python interpreter where cryptography is installed.
"""
import argparse
import getpass
import hashlib
import json
import os
import pathlib
import secrets
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

MAGIC = b'HSK-SNAPSHOT-1\n'
BLOCK = 2 * 1024 * 1024
ITERATIONS = 600000

def key_for(password, salt):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=ITERATIONS).derive(password.encode('utf-8'))

def digest_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()

def backup_group(root):
    root = pathlib.Path(root)
    dbs = sorted(root.glob('*-database.sql.gz'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dbs:
        raise RuntimeError('No *-database.sql.gz found; first run bench --site crm.localhost backup --with-files --compress')
    latest = dbs[0]
    prefix = latest.name[:-len('-database.sql.gz')]
    files = sorted([p for p in root.iterdir() if p.is_file() and p.name.startswith(prefix + '-')])
    configs = [p for p in files if p.name.endswith('-site_config_backup.json')]
    if not configs:
        raise RuntimeError('Matching site_config_backup.json missing')
    print('Snapshot source group:', prefix)
    print('Including:', ', '.join(f.name for f in files))
    return files

def pack(args):
    files = backup_group(args.backups)
    password = getpass.getpass('Create snapshot password (send separately): ')
    confirm = getpass.getpass('Repeat snapshot password: ')
    if len(password) < 14 or password != confirm:
        raise RuntimeError('Passwords do not match or password is fewer than 14 characters')
    output = pathlib.Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError('Output already exists; choose a new filename')
    with tempfile.TemporaryDirectory(prefix='hsk-export-') as temp:
        archive = pathlib.Path(temp, 'snapshot.tar.gz')
        manifest = {'type':'frappe-full-site-backup', 'created_utc':datetime.now(timezone.utc).isoformat(),
                    'files':[{'name':f.name, 'sha256':digest_file(f), 'bytes':f.stat().st_size} for f in files]}
        manifest_path = pathlib.Path(temp, 'manifest.json')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(manifest_path, arcname='manifest.json')
            for f in files:
                tar.add(f, arcname=f.name)
        salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
        encryptor = Cipher(algorithms.AES(key_for(password, salt)), modes.GCM(iv)).encryptor()
        try:
            with open(archive, 'rb') as src, open(output, 'xb') as dst:
                dst.write(MAGIC + salt + iv)
                for block in iter(lambda: src.read(BLOCK), b''):
                    dst.write(encryptor.update(block))
                dst.write(encryptor.finalize())
                dst.write(encryptor.tag)
        except Exception:
            output.unlink(missing_ok=True)
            raise
    print('ENCRYPTED SNAPSHOT READY:', output)
    print('SHA256:', digest_file(output))
    print('IMPORTANT: NEVER commit the password, raw SQL backup, or site_config JSON.')

def unpack(args):
    src = pathlib.Path(args.input)
    dest = pathlib.Path(args.dest).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError('Destination exists and is not empty; use a new folder')
    password = getpass.getpass('Snapshot password: ')
    with tempfile.TemporaryDirectory(prefix='hsk-decrypt-') as temp:
        archive = pathlib.Path(temp, 'snapshot.tar.gz')
        with open(src, 'rb') as fh:
            if fh.read(len(MAGIC)) != MAGIC:
                raise RuntimeError('Unknown snapshot format')
            salt, iv = fh.read(16), fh.read(12)
            file_size = src.stat().st_size
            ciphertext_size = file_size - len(MAGIC) - 16 - 12 - 16
            if ciphertext_size < 1:
                raise RuntimeError('Truncated snapshot')
            fh.seek(file_size - 16)
            tag = fh.read(16)
            decryptor = Cipher(algorithms.AES(key_for(password, salt)), modes.GCM(iv, tag)).decryptor()
            fh.seek(len(MAGIC) + 16 + 12)
            with open(archive, 'wb') as out:
                left = ciphertext_size
                while left:
                    block = fh.read(min(BLOCK, left))
                    if not block:
                        raise RuntimeError('Truncated ciphertext')
                    out.write(decryptor.update(block))
                    left -= len(block)
                out.write(decryptor.finalize())
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            if any(not x.isfile() or pathlib.PurePosixPath(x.name).name != x.name for x in members):
                raise RuntimeError('Invalid archive members')
            dest.mkdir(parents=True, exist_ok=True)
            for member in members:
                target = dest / member.name
                with tar.extractfile(member) as inp, open(target, 'wb') as out:
                    shutil.copyfileobj(inp, out)
        manifest = json.loads((dest / 'manifest.json').read_text(encoding='utf-8'))
        for record in manifest['files']:
            if digest_file(dest / record['name']) != record['sha256']:
                raise RuntimeError('Checksum failed: ' + record['name'])
    print('SNAPSHOT DECRYPTED AND VERIFIED:', dest)
    for rec in manifest['files']:
        print(' ', rec['name'])
    print('WARNING: extracted files contain secrets. Do NOT commit the extracted folder.')

def copy_encryption_keys(args):
    """Apply the original encryption key while preserving new site's DB credentials."""
    backup_config = json.loads(pathlib.Path(args.backup_config).read_text(encoding='utf-8'))
    site_config_path = pathlib.Path(args.site_config)
    current_config = json.loads(site_config_path.read_text(encoding='utf-8'))
    for key in ('encryption_key', 'backup_encryption_key'):
        if key in backup_config:
            current_config[key] = backup_config[key]
    with tempfile.NamedTemporaryFile('w', dir=site_config_path.parent, delete=False) as f:
        json.dump(current_config, f, indent=2)
        tempname = f.name
    os.chmod(tempname, 0o600)
    os.replace(tempname, site_config_path)
    print('Encryption keys synchronized; new site DB credentials preserved.')

def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='command', required=True)
    a = subs.add_parser('pack')
    a.add_argument('--backups', required=True)
    a.add_argument('--out', required=True)
    b = subs.add_parser('unpack')
    b.add_argument('--input', required=True)
    b.add_argument('--dest', required=True)
    c = subs.add_parser('copy-keys')
    c.add_argument('--backup-config', required=True)
    c.add_argument('--site-config', required=True)
    args = parser.parse_args()
    {'pack':pack,'unpack':unpack,'copy-keys':copy_encryption_keys}[args.command](args)

if __name__ == '__main__':
    main()
