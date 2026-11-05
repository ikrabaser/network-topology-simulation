"""Mini SIEM: logları toplar, ilişkilendirir (korelasyon), alarm üretir.

Log satırı biçimi:
    2026-11-05T03:12:44 fw_1 AUTH FAIL user=admin src=203.0.113.50
    2026-11-05T03:20:10 fw_1 FW DENY src=10.0.40.23 dst=10.0.60.10 dport=445 zone=misafir_wifi
    2026-11-05T03:25:00 fw_1 TRANSFER OK user=admin src=203.0.113.50 bytes=262144000

Kurallar:
  1. BRUTE_FORCE      : aynı kaynaktan kısa sürede çok sayıda başarısız giriş
  2. BASARILI_GIRIS   : brute force'un ardından aynı kaynaktan başarılı giriş   (olaylar ilişkilendirilir)
  3. VERI_SIZINTISI   : o başarılı girişten sonra büyük veri aktarımı           (olaylar ilişkilendirilir)
  4. PORT_TARAMA      : aynı kaynağın çok sayıda farklı porta engellenen denemesi
  5. MESAI_DISI_ADMIN : gece saatlerinde yönetici hesabıyla başarılı giriş
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

SATIR = re.compile(
    r"^(?P<zaman>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(?P<cihaz>\S+)\s+"
    r"(?P<tur>AUTH|FW|TRANSFER)\s+(?P<sonuc>\w+)\s*(?P<kalan>.*)$"
)
ALAN = re.compile(r"(\w+)=(\S+)")

SEVIYE_SIRASI = {"KRITIK": 0, "YUKSEK": 1, "ORTA": 2}


@dataclass
class Olay:
    zaman: datetime
    cihaz: str
    tur: str
    sonuc: str
    alanlar: dict = field(default_factory=dict)

    def al(self, ad, varsayilan=None):
        return self.alanlar.get(ad, varsayilan)


@dataclass
class Alarm:
    seviye: str
    kural: str
    aciklama: str
    zaman: datetime
    kanit: list = field(default_factory=list)


@dataclass
class Esikler:
    brute_adet: int = 5
    brute_aralik: int = 300          # aynı seri sayılması için olaylar arası en fazla saniye
    basari_pencere: int = 600        # son başarısız girişten sonra başarılı giriş için saniye
    sizinti_bayt: int = 500 * 1024 ** 2
    sizinti_pencere: int = 1800
    tarama_port: int = 8
    tarama_aralik: int = 120
    mesai_disi_baslangic: int = 0
    mesai_disi_bitis: int = 6
    yonetici_oneki: str = "admin"


def olaylari_oku(satirlar) -> tuple:
    """(olaylar, hatalı_satır_sayısı). Boş satır ve # yorumları atlanır."""
    olaylar, hatali = [], 0
    for ham in satirlar:
        ham = ham.strip()
        if not ham or ham.startswith("#"):
            continue
        m = SATIR.match(ham)
        if not m:
            hatali += 1
            continue
        olaylar.append(Olay(
            zaman=datetime.fromisoformat(m["zaman"]), cihaz=m["cihaz"], tur=m["tur"],
            sonuc=m["sonuc"], alanlar=dict(ALAN.findall(m["kalan"])),
        ))
    olaylar.sort(key=lambda o: o.zaman)
    return olaylar, hatali


def _seriler(olaylar: list, aralik: int) -> list:
    """Zamana göre sıralı olayları, ardışık olaylar arası boşluk <= aralik olacak şekilde gruplar."""
    seriler, mevcut = [], []
    for o in olaylar:
        if mevcut and (o.zaman - mevcut[-1].zaman).total_seconds() > aralik:
            seriler.append(mevcut)
            mevcut = []
        mevcut.append(o)
    if mevcut:
        seriler.append(mevcut)
    return seriler


def _kaynaga_gore(olaylar):
    gruplar = {}
    for o in olaylar:
        gruplar.setdefault(o.al("src"), []).append(o)
    return gruplar


def analiz_et(olaylar: list, e: Esikler | None = None) -> list:
    e = e or Esikler()
    alarmlar = []

    # 1-3: giriş denemeleri ve ilişkilendirme
    basarisiz = [o for o in olaylar if o.tur == "AUTH" and o.sonuc == "FAIL"]
    basarili = [o for o in olaylar if o.tur == "AUTH" and o.sonuc == "SUCCESS"]
    aktarimlar = [o for o in olaylar if o.tur == "TRANSFER"]

    for src, liste in _kaynaga_gore(basarisiz).items():
        for seri in _seriler(liste, e.brute_aralik):
            if len(seri) < e.brute_adet:
                continue
            son = seri[-1].zaman
            hesaplar = sorted({o.al("user") for o in seri})
            alarmlar.append(Alarm(
                "YUKSEK", "BRUTE_FORCE",
                f"{src} adresinden {len(seri)} başarısız giriş (hesap: {', '.join(hesaplar)})",
                seri[0].zaman, seri))
            giris = next((o for o in basarili
                          if o.al("src") == src
                          and timedelta(0) < o.zaman - son <= timedelta(seconds=e.basari_pencere)),
                         None)
            if not giris:
                continue
            alarmlar.append(Alarm(
                "KRITIK", "BASARILI_GIRIS",
                f"{src}: {len(seri)} başarısız denemenin ardından {giris.al('user')} hesabıyla başarılı giriş",
                giris.zaman, seri + [giris]))
            sonraki = [a for a in aktarimlar
                       if a.al("user") == giris.al("user")
                       and timedelta(0) <= a.zaman - giris.zaman <= timedelta(seconds=e.sizinti_pencere)]
            toplam = sum(int(a.al("bytes", 0)) for a in sonraki)
            if toplam >= e.sizinti_bayt:
                alarmlar.append(Alarm(
                    "KRITIK", "VERI_SIZINTISI",
                    f"{giris.al('user')} girişinden sonra {toplam / 1024 ** 2:.0f} MB veri aktarıldı",
                    sonraki[0].zaman, [giris] + sonraki))

    # 4: port tarama
    engellenen = [o for o in olaylar if o.tur == "FW" and o.sonuc == "DENY"]
    for src, liste in _kaynaga_gore(engellenen).items():
        for seri in _seriler(liste, e.tarama_aralik):
            portlar = {o.al("dport") for o in seri}
            if len(portlar) >= e.tarama_port:
                alarmlar.append(Alarm(
                    "ORTA", "PORT_TARAMA",
                    f"{src} ({seri[0].al('zone', '?')}) {len(portlar)} farklı porta engellenen deneme yaptı",
                    seri[0].zaman, seri))

    # 5: mesai dışı yönetici girişi
    for o in basarili:
        if (o.al("user", "").startswith(e.yonetici_oneki)
                and e.mesai_disi_baslangic <= o.zaman.hour < e.mesai_disi_bitis):
            alarmlar.append(Alarm(
                "ORTA", "MESAI_DISI_ADMIN",
                f"{o.al('user')} gece {o.zaman:%H:%M}'de giriş yaptı (kaynak {o.al('src')})",
                o.zaman, [o]))

    alarmlar.sort(key=lambda a: (SEVIYE_SIRASI[a.seviye], a.zaman))
    return alarmlar


def rapor_metni(alarmlar: list, olay_sayisi: int = 0, hatali: int = 0) -> str:
    satirlar = [f"== Mini SIEM raporu: {olay_sayisi} olay, {len(alarmlar)} alarm"
                + (f", {hatali} okunamayan satır" if hatali else "") + " =="]
    for a in alarmlar:
        satirlar.append(f"[{a.seviye:6}] {a.zaman:%Y-%m-%d %H:%M:%S} {a.kural}: {a.aciklama}"
                        f"  ({len(a.kanit)} olay)")
    if not alarmlar:
        satirlar.append("Alarm yok.")
    return "\n".join(satirlar)
