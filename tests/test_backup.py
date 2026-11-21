import datetime as dt
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import backup as bk  # noqa: E402


def write_csv(path, rows):
    header = "name,device_type,host,password_env\n"
    body = "".join(f"{r[0]},{r[1]},{r[2]},{r[3]}\n" for r in rows)
    path.write_text(header + body, encoding="utf-8")


def make_connect(outputs):
    """Membuat fungsi koneksi palsu. outputs: dict nama -> teks, atau Exception untuk gagal."""

    def connect(device, password):
        result = outputs[device.name]
        if isinstance(result, Exception):
            raise result
        return result

    return connect


def dev(name="SW1", device_type="cisco_ios", host="10.0.0.2", env="SW_PASS"):
    return bk.Device(name=name, device_type=device_type, host=host, password_env=env)


def test_load_devices(tmp_path):
    csv_path = tmp_path / "devices.csv"
    write_csv(csv_path, [("SW1", "cisco_ios", "10.0.0.2", "SW_PASS")])
    devices = bk.load_devices(csv_path)
    assert devices == [bk.Device("SW1", "cisco_ios", "10.0.0.2", "SW_PASS")]


def test_load_devices_rejects_unknown_type(tmp_path):
    csv_path = tmp_path / "devices.csv"
    write_csv(csv_path, [("X", "juniper_junos", "10.0.0.9", "P")])
    with pytest.raises(bk.BackupError):
        bk.load_devices(csv_path)


def test_clean_config_removes_timestamp_noise():
    raw = "! Last configuration change at 10:00:01\nhostname SW1  \ninterface Gi0/1\n"
    assert bk.clean_config(raw) == "hostname SW1\ninterface Gi0/1\n"


def test_clean_config_same_output_when_only_noise_differs():
    a = "! Last configuration change at 10:00:01\nhostname SW1\n"
    b = "! Last configuration change at 12:45:59\nhostname SW1\n"
    assert bk.clean_config(a) == bk.clean_config(b)


def test_backup_reports_change_only_when_content_differs(tmp_path):
    d = dev()
    connect = make_connect({"SW1": "hostname SW1\n"})
    assert bk.backup_device(d, tmp_path, connect, "x") is True   # file baru
    assert bk.backup_device(d, tmp_path, connect, "x") is False  # sama
    connect2 = make_connect({"SW1": "hostname SW1\nvlan 30\n"})
    assert bk.backup_device(d, tmp_path, connect2, "x") is True  # berubah


def test_run_backup_continues_after_one_failure(tmp_path):
    devices = [dev("SW1"), dev("R1", "mikrotik_routeros", "192.168.88.1", "MT_PASS")]
    connect = make_connect({"SW1": RuntimeError("timeout"), "R1": "/ip address\n"})
    changed, failed = bk.run_backup(devices, tmp_path, connect, get_password=lambda env: "x")
    assert changed == ["R1"]
    assert failed and failed[0][0] == "SW1"
    assert (tmp_path / "R1.cfg").exists()


def test_run_backup_reports_missing_password_env(tmp_path):
    devices = [dev("SW1", env="TIDAK_ADA")]
    connect = make_connect({"SW1": "hostname SW1\n"})
    changed, failed = bk.run_backup(devices, tmp_path, connect, get_password=lambda env: os.environ[env])
    assert changed == []
    assert failed[0][0] == "SW1"


def git_available():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@pytest.mark.skipif(not git_available(), reason="git tidak tersedia")
def test_commit_only_when_changed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bk.git(repo, "init", "-q")
    bk.git(repo, "config", "user.email", "lab@example.com")
    bk.git(repo, "config", "user.name", "Lab")

    (repo / "SW1.cfg").write_text("hostname SW1\n", encoding="utf-8")
    assert bk.commit_changes(repo, ["SW1"], dt.datetime(2026, 11, 21, 9, 0)) is True
    log_text = bk.git(repo, "log", "--format=%s")
    assert "SW1 berubah" in log_text

    # Tidak ada perubahan: tidak boleh commit
    assert bk.commit_changes(repo, []) is False
    assert len(bk.git(repo, "log", "--oneline").splitlines()) == 1
