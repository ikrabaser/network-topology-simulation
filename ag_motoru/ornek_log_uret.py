"""Örnek log üretici: normal gün içi trafik + isteğe bağlı gece saldırısı.

Kullanım:
    python ornek_log_uret.py            # ornek_loglar/ klasörüne iki dosya yazar
Saldırı IP'leri 203.0.113.0/24 (belgelendirme için ayrılmış örnek blok), iç ağ adresleri örnektir.
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta

GUN = datetime(2026, 11, 5)
KULLANICILAR = ["ali", "ayse", "mehmet", "zeynep", "admin_can"]


def _satir(zaman, cihaz, tur, sonuc, **alanlar):
    kalan = " ".join(f"{k}={v}" for k, v in alanlar.items())
    return zaman, f"{zaman:%Y-%m-%dT%H:%M:%S} {cihaz} {tur} {sonuc} {kalan}".rstrip()


def uret(saldiri: bool = True, tohum: int = 42) -> list:
    rnd = random.Random(tohum)
    kayitlar = []

    # Normal gün içi trafik: 09:00-17:00 arası girişler, ara sıra yanlış şifre, web trafiği
    for _ in range(60):
        z = GUN + timedelta(hours=9, seconds=rnd.randrange(8 * 3600))
        kul = rnd.choice(KULLANICILAR)
        src = f"10.0.{rnd.choice([10, 30])}.{rnd.randrange(2, 200)}"
        if rnd.random() < 0.12:  # tek tük yanlış şifre
            kayitlar.append(_satir(z, "fw_1", "AUTH", "FAIL", user=kul, src=src))
            z += timedelta(seconds=rnd.randrange(5, 40))
        kayitlar.append(_satir(z, "fw_1", "AUTH", "SUCCESS", user=kul, src=src))
        kayitlar.append(_satir(z + timedelta(seconds=3), "fw_1", "FW", "ALLOW",
                               src=src, dst="10.0.60.10", dport=rnd.choice([443, 88, 53]),
                               zone="personel_wifi"))
        kayitlar.append(_satir(z + timedelta(seconds=30), "fw_1", "TRANSFER", "OK",
                               user=kul, src=src, bytes=rnd.randrange(10_000, 40_000_000),
                               dst="dosya_sunucu"))

    if saldiri:
        # (a) Misafir ağından port tarama (03:10)
        t = GUN + timedelta(hours=3, minutes=10)
        portlar = [21, 22, 23, 25, 53, 80, 135, 139, 389, 443, 445, 1433, 3306, 3389]
        for i, p in enumerate(portlar):
            kayitlar.append(_satir(t + timedelta(seconds=3 * i), "fw_1", "FW", "DENY",
                                   src="10.0.40.23", dst="10.0.60.10", dport=p,
                                   zone="misafir_wifi"))
        # (b) Dışarıdan brute force (03:12), ardından başarılı giriş
        t = GUN + timedelta(hours=3, minutes=12)
        for i in range(7):
            kayitlar.append(_satir(t + timedelta(seconds=2 * i), "fw_1", "AUTH", "FAIL",
                                   user="admin_can", src="203.0.113.50"))
        giris = t + timedelta(seconds=45)
        kayitlar.append(_satir(giris, "fw_1", "AUTH", "SUCCESS",
                               user="admin_can", src="203.0.113.50"))
        # (c) Girişten sonra toplam 1000 MB veri çekilmesi
        for i in range(4):
            kayitlar.append(_satir(giris + timedelta(minutes=2 + 4 * i), "fw_1", "TRANSFER", "OK",
                                   user="admin_can", src="203.0.113.50",
                                   bytes=250 * 1024 ** 2, dst="veritabani"))

    kayitlar.sort(key=lambda x: x[0])
    return [satir for _, satir in kayitlar]


def yaz(klasor: str = "ornek_loglar") -> list:
    os.makedirs(klasor, exist_ok=True)
    dosyalar = []
    for ad, saldiri in (("normal.log", False), ("saldirili.log", True)):
        yol = os.path.join(klasor, ad)
        with open(yol, "w", encoding="utf-8") as f:
            f.write("\n".join(uret(saldiri)) + "\n")
        dosyalar.append(yol)
    return dosyalar


if __name__ == "__main__":
    for yol in yaz():
        print("yazıldı:", yol)
