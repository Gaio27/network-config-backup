"""Antarmuka baris perintah untuk backup konfigurasi perangkat."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import backup as bk


def netmiko_connect(device: bk.Device, password: str) -> str:
    """Mengambil konfigurasi lewat SSH memakai Netmiko. Butuh paket netmiko terpasang."""
    from netmiko import ConnectHandler  # impor di sini agar modul lain tetap bisa diuji tanpa netmiko

    params = {
        "device_type": device.device_type,
        "host": device.host,
        "username": os.environ.get("ROUTER_USER", "admin"),
        "password": password,
        "timeout": 20,
    }
    with ConnectHandler(**params) as conn:
        return conn.send_command(bk.SHOW_COMMANDS[device.device_type])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backup konfigurasi perangkat jaringan")
    p.add_argument("--devices", required=True, help="file CSV daftar perangkat")
    p.add_argument("--out", required=True, help="folder tujuan file konfigurasi")
    p.add_argument("--commit", action="store_true", help="commit perubahan ke Git di folder --out")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("backup.log", encoding="utf-8")],
    )
    try:
        devices = bk.load_devices(args.devices)
    except (bk.BackupError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    out = Path(args.out)
    changed, failed = bk.run_backup(devices, out, netmiko_connect)
    if args.commit:
        bk.commit_changes(out, changed)
    print(f"Berubah: {len(changed)}, gagal: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
