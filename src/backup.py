"""Backup konfigurasi perangkat jaringan dan penyimpanan ke Git.

Koneksi SSH dibuat lewat fungsi yang bisa diganti (`connect`). Di lingkungan nyata, fungsi itu memakai Netmiko.
Dengan begitu logika backup dan Git bisa diuji tanpa perangkat asli.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# Perintah untuk mengambil konfigurasi berjalan, per tipe perangkat
SHOW_COMMANDS = {
    "cisco_ios": "show running-config",
    "mikrotik_routeros": "/export",
}

# Baris yang berubah setiap kali diambil, sehingga bukan perubahan nyata
NOISE_PREFIXES = (
    "! Last configuration change",
    "! NVRAM config last updated",
    "# ",  # header waktu pada /export RouterOS
    "# software",
)


@dataclass(frozen=True)
class Device:
    name: str
    device_type: str
    host: str
    password_env: str


class BackupError(Exception):
    pass


def load_devices(csv_path: str | Path) -> list[Device]:
    devices: list[Device] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("name") or not row.get("host"):
                raise BackupError(f"Baris tidak lengkap di {csv_path}: {row}")
            if row["device_type"] not in SHOW_COMMANDS:
                raise BackupError(f"Tipe perangkat tidak didukung: {row['device_type']}")
            devices.append(
                Device(
                    name=row["name"],
                    device_type=row["device_type"],
                    host=row["host"],
                    password_env=row["password_env"],
                )
            )
    return devices


def clean_config(text: str) -> str:
    """Menghapus baris yang berubah setiap pengambilan dan merapikan spasi di akhir baris."""
    lines = []
    for line in text.splitlines():
        if line.startswith(NOISE_PREFIXES):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def backup_device(
    device: Device,
    out_dir: Path,
    connect: Callable[[Device, str], str],
    password: str,
) -> bool:
    """Mengambil konfigurasi satu perangkat dan menyimpannya ke out_dir/<nama>.cfg.

    Mengembalikan True jika isi berubah dibanding sebelumnya.
    """
    try:
        raw = connect(device, password)
    except Exception as e:  # noqa: BLE001 - kegagalan koneksi apa pun dicatat per perangkat
        raise BackupError(f"{device.name}: {e}") from e

    new_text = clean_config(raw)
    target = out_dir / f"{device.name}.cfg"
    old_text = target.read_text(encoding="utf-8") if target.exists() else None
    if old_text == new_text:
        return False
    target.write_text(new_text, encoding="utf-8")
    return True


def run_backup(
    devices: list[Device],
    out_dir: Path,
    connect: Callable[[Device, str], str],
    get_password: Callable[[str], str] = lambda env: os.environ[env],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Menjalankan backup untuk semua perangkat.

    Mengembalikan (daftar perangkat yang berubah, daftar (perangkat, pesan galat)).
    Satu perangkat yang gagal tidak menghentikan perangkat lain.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    failed: list[tuple[str, str]] = []
    for d in devices:
        try:
            password = get_password(d.password_env)
            if backup_device(d, out_dir, connect, password):
                changed.append(d.name)
                log.info("%s: konfigurasi berubah", d.name)
            else:
                log.info("%s: tidak ada perubahan", d.name)
        except (BackupError, KeyError) as e:
            failed.append((d.name, str(e)))
            log.error("%s gagal: %s", d.name, e)
    return changed, failed


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BackupError(f"git {' '.join(args)} gagal: {result.stderr.strip()}")
    return result.stdout


def commit_changes(repo: Path, changed: list[str], when: dt.datetime | None = None) -> bool:
    """Commit hanya jika ada file yang berubah. Mengembalikan True jika commit dibuat."""
    if not changed:
        return False
    when = when or dt.datetime.now()
    git(repo, "add", "-A")
    if not git(repo, "status", "--porcelain").strip():
        return False
    names = ", ".join(sorted(changed))
    message = f"Backup otomatis {when:%Y-%m-%d %H:%M}: {names} berubah"
    git(repo, "commit", "-m", message)
    return True
