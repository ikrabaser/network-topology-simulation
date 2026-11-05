"""Mini izleme (Zabbix mantığı).

İki parça var:
  1. ag_izleme(): topoloji modelinde izleme düğümünden (zabbix) her cihaza ulaşılıyor mu?
  2. tcp_kontrol(): gerçek bir host:port'a TCP bağlantısı kurmayı dener
     (ping ICMP için yönetici yetkisi gerektirdiği için TCP bağlantısı kullanılır).
"""
from __future__ import annotations

import socket
import time

from .ag_modelleri import Senaryo
from .hata_simulasyonu import canli_graf, olu_dugumler, ulasilabilir

UP, ARIZALI, GUCSUZ, ULASILAMIYOR, IZLEME_KAPALI = (
    "UP", "ARIZALI", "GÜÇSÜZ", "ULAŞILAMIYOR", "İZLEME KAPALI")


def ag_izleme(senaryo: Senaryo, bozuklar=()) -> dict:
    """cihaz -> durum. Zabbix'in her cihaza erişip erişemediğini simüle eder."""
    bozuklar = set(bozuklar)
    olu = olu_dugumler(senaryo, bozuklar)
    g = canli_graf(senaryo, bozuklar)
    izleyici = senaryo.izleme_dugumu
    sonuc = {}
    for n in senaryo.graf.nodes:
        if n == izleyici or senaryo.graf.nodes[n]["tur"] == "internet":
            continue
        if n in bozuklar:
            sonuc[n] = ARIZALI
        elif n in olu:
            sonuc[n] = GUCSUZ
        elif izleyici in olu:
            sonuc[n] = IZLEME_KAPALI
        elif ulasilabilir(g, izleyici, n):
            sonuc[n] = UP
        else:
            sonuc[n] = ULASILAMIYOR
    return sonuc


def alarmlar(durumlar: dict) -> list:
    """UP olmayan her cihaz için alarm satırı üretir."""
    return [f"ALARM: {cihaz} -> {durum}" for cihaz, durum in durumlar.items() if durum != UP]


def durum_degisimleri(onceki: dict, sonraki: dict) -> list:
    return [(c, onceki.get(c), d) for c, d in sonraki.items() if onceki.get(c) != d]


def izleme_metni(senaryo: Senaryo, bozuklar=()) -> str:
    durumlar = ag_izleme(senaryo, bozuklar)
    toplam = len(durumlar)
    up = sum(1 for d in durumlar.values() if d == UP)
    satirlar = [f"== {senaryo.baslik}: izleme ({senaryo.izleme_dugumu} gözüyle) ==",
                f"{up}/{toplam} cihaz UP"]
    satirlar += [f"  {a}" for a in alarmlar(durumlar)]
    return "\n".join(satirlar)


def tcp_kontrol(host: str, port: int, zaman_asimi: float = 1.0) -> tuple:
    """(ayakta_mi, gecikme_ms). Gerçek bir TCP bağlantısı dener."""
    baslangic = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=zaman_asimi):
            return True, round((time.perf_counter() - baslangic) * 1000, 2)
    except OSError:
        return False, None
