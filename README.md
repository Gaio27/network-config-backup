# Network Config Backup

Skrip yang mencadangkan konfigurasi perangkat jaringan setiap hari lewat SSH, lalu menyimpan setiap perubahan ke Git. Dengan begitu, riwayat perubahan konfigurasi tercatat dan bisa dipulihkan.

## Masalah

Konfigurasi perangkat sering berubah tanpa catatan. Saat ada masalah, tidak jelas siapa mengubah apa dan kapan. Backup manual mudah terlewat.

## Pendekatan

- Python dengan Netmiko untuk masuk ke perangkat lewat SSH dan mengambil konfigurasi.
- Setiap perangkat disimpan sebagai file teks di folder `backup/`.
- Git mencatat perubahan. Commit hanya dibuat jika isi konfigurasi berubah.
- Kata sandi diambil dari variabel lingkungan, tidak pernah ditulis di kode.
- Dijadwalkan dengan systemd timer atau cron.

## Fitur

- Daftar perangkat dibaca dari `devices.csv` (nama, tipe perangkat, alamat, dan nama variabel kata sandi).
- Mendukung Cisco IOS dan MikroTik RouterOS.
- Logging ke file, dengan status setiap perangkat (berhasil atau gagal).
- Commit otomatis dengan pesan berisi tanggal dan daftar perangkat yang berubah.

## Arsitektur

```
src/
  backup.py       # koneksi Netmiko, pengambilan konfigurasi
  git_store.py    # commit ke repositori backup
  cli.py          # argparse dan logging
configs/
  devices.example.csv   # contoh, tanpa alamat asli
tests/
  test_backup.py
```

## Cara menjalankan

```bash
git clone https://github.com/Gaio27/network-config-backup.git
cd network-config-backup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Atur kata sandi di lingkungan, jangan di file
export ROUTER_PASS='isi-di-terminal-saja'

# Salin contoh dan isi perangkat Anda
cp configs/devices.example.csv configs/devices.csv

# Jalankan backup
python3 src/cli.py --devices configs/devices.csv --out backup/
```

## Contoh riwayat Git

```
a1b2c3d 2026-11-21 Backup otomatis: SW1, R1 berubah
e4f5a6b 2026-11-20 Backup otomatis: R1 berubah
9c8d7e6 2026-11-20 Backup awal
```

## Hasil

- [ ] Jumlah perangkat lab yang dicadangkan: (isi setelah pengujian)
- [ ] Uji pemulihan (restore) dari salah satu commit: (isi setelah pengujian)

## Yang saya pelajari dan akan saya perbaiki

- Tantangan utama adalah membedakan perubahan nyata dari data yang berubah sendiri, seperti waktu atau nomor urut.
- Rencana berikutnya: menghapus baris yang tidak relevan sebelum commit, dan memberi peringatan jika ada perangkat yang gagal dua kali berturut-turut.

## Catatan keamanan

Jangan pernah meng-commit `devices.csv` yang berisi alamat asli atau kata sandi. Repositori ini memakai `.gitignore` untuk file tersebut.

## Lisensi

MIT
