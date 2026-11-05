"""Servis katmanı: motoru (ag_motoru) çağırır, sonuçları JSON'a uygun sözlüklere çevirir.

Web görünümleri, REST API ve geçmiş kaydı aynı fonksiyonları kullanır; böylece bir sonuç
hangi yoldan istenirse istensin aynıdır. Geçmişe yazılan veri istemciden gelen sonuç değil,
buradaki hesaplamanın çıktısıdır.
"""
from __future__ import annotations

from ag_motoru import erisim_matrisi, hata_simulasyonu, mermaid_uret, mini_izleme, mini_siem

from . import models
from .yukle import senaryo_yukle

MAKS_LOG_BAYT = 1_000_000


class GirdiHatasi(ValueError):
    """Kullanıcının verdiği girdi geçersiz (web'de mesaj, API'de 400)."""


def senaryo_getir(slug: str):
    """(veritabanı nesnesi, motor senaryosu). Yoksa Senaryo.DoesNotExist fırlatır."""
    obj = models.Senaryo.objects.get(slug=slug)
    return obj, senaryo_yukle(obj)


# ---- genel bakış ---------------------------------------------------------------------------

def _etkiler(sonuclar) -> list:
    return [{"cesit": x["cesit"], "eleman": x["eleman"],
             "etki": hata_simulasyonu.etki_metni(x["etki"])} for x in sonuclar]


def analiz(es) -> dict:
    a = hata_simulasyonu.tek_hata_analizi(es)
    return {"kontrol": a["kontrol"], "spof": _etkiler(a["spof"]), "yerel": _etkiler(a["yerel"])}


def ozet(obj, es) -> dict:
    a = analiz(es)
    return {"slug": obj.slug, "baslik": obj.baslik, "dugum": es.graf.number_of_nodes(),
            "kablo": es.graf.number_of_edges(), "spof": len(a["spof"]), "yerel": len(a["yerel"]),
            "gereksinim": len(es.gereksinimler)}


def diyagram(es, bozuk=(), olu=()) -> str:
    return mermaid_uret.mermaid(es, bozuk=bozuk, olu=olu)


def gereksinim_listesi(es) -> list:
    return [{"kaynak": r.kaynak, "hedefler": list(r.hedefler), "aciklama": r.aciklama}
            for r in es.gereksinimler]


# ---- hata simülasyonu ----------------------------------------------------------------------

def secilebilir(es) -> list:
    return [{"ad": ad, "etiket": etiket, "cesit": cesit}
            for ad, etiket, cesit in hata_simulasyonu.secilebilir_elemanlar(es)]


def bozuklari_ayikla(es, istenen, katı: bool = False) -> list:
    """Geçerli eleman adlarını (sırayı koruyarak, tekrarsız) döndürür.

    katı=True ise bilinmeyen ad GirdiHatasi verir (API); değilse yoksayılır (web formu).
    """
    gecerli = {s["ad"] for s in secilebilir(es)}
    temiz = list(dict.fromkeys(istenen))
    yanlis = [b for b in temiz if b not in gecerli]
    if yanlis and katı:
        raise GirdiHatasi("Bilinmeyen eleman: " + ", ".join(yanlis))
    return [b for b in temiz if b in gecerli]


def hata(es, bozuk) -> dict:
    sonuc = hata_simulasyonu.coklu_hata(es, bozuk)
    olu = sonuc["olu"]
    return {"bozuk": list(bozuk), "olu": olu, "guc_kapanan": [n for n in olu if n not in bozuk],
            "kopan": [{"kaynak": r.kaynak, "hedefler": list(r.hedefler), "aciklama": r.aciklama}
                      for r in sonuc["kopan"]]}


def hata_ozeti(s: dict) -> str:
    if not s["bozuk"]:
        return "Hiçbir eleman bozulmadı"
    return f"{', '.join(s['bozuk'])} bozuk: " + (
        f"{len(s['kopan'])} gereksinim koptu" if s["kopan"] else "tüm gereksinimler karşılanıyor")


# ---- izleme --------------------------------------------------------------------------------

def izleme(es, bozuk) -> dict:
    durumlar = mini_izleme.ag_izleme(es, bozuk)
    up = sum(1 for d in durumlar.values() if d == mini_izleme.UP)
    return {"bozuk": list(bozuk), "izleyici": es.izleme_dugumu, "up": up, "toplam": len(durumlar),
            "durumlar": [{"ad": n, "etiket": es.graf.nodes[n]["etiket"], "durum": d,
                          "ok": d == mini_izleme.UP} for n, d in durumlar.items()],
            "alarmlar": mini_izleme.alarmlar(durumlar)}


def izleme_ozeti(s: dict) -> str:
    return f"{s['up']}/{s['toplam']} cihaz UP" + (f" ({', '.join(s['bozuk'])} bozuk)" if s["bozuk"] else "")


# ---- erişim --------------------------------------------------------------------------------

def erisim_cihazlari(es) -> list:
    return [n for n, d in es.graf.nodes(data=True) if d["bolge"]]


def erisim_matrisi_tablosu(es) -> dict:
    zonlar = erisim_matrisi.bolgeler(es)
    m = erisim_matrisi.matris(es)
    satirlar = []
    for k in zonlar:
        hucreler = []
        for h in zonlar:
            durum = m[(k, h)]
            portlar = ""
            if durum == "kismi":
                portlar = ",".join(str(p) for p in sorted(erisim_matrisi.izinli_portlar(es, k, h)))
            hucreler.append({"hedef": h, "durum": durum, "portlar": portlar})
        satirlar.append({"kaynak": k, "hucreler": hucreler})
    ihlaller = erisim_matrisi.engelleri_dogrula(es)
    return {"zonlar": zonlar, "satirlar": satirlar,
            "engeller": [{"kaynak": e.kaynak, "hedef": e.hedef, "port": e.port, "aciklama": e.aciklama}
                         for e in es.engeller],
            "ihlaller": [{"kaynak": e.kaynak, "hedef": e.hedef, "port": e.port, "aciklama": e.aciklama}
                         for e in ihlaller]}


def port_coz(deger) -> int | None:
    if deger is None or str(deger).strip() == "":
        return None
    d = str(deger).strip()
    if not d.isdigit() or not 1 <= int(d) <= 65535:
        raise GirdiHatasi("Port 1-65535 arasında bir sayı olmalı.")
    return int(d)


def erisim_sorgusu(es, kaynak: str, hedef: str, port=None) -> dict:
    cihazlar = erisim_cihazlari(es)
    if kaynak not in cihazlar or hedef not in cihazlar:
        raise GirdiHatasi("Geçersiz cihaz seçimi.")
    p = port_coz(port)
    s = erisim_matrisi.uctan_uca(es, kaynak, hedef, p)
    return {"kaynak": kaynak, "hedef": hedef, "port": p, **s}


def erisim_ozeti(s: dict) -> str:
    port = f":{s['port']}" if s["port"] else ""
    if s["sonuc"]:
        karar = "İZİN"
    elif not s["politika_izni"]:
        karar = "ENGEL (politika)"
    else:
        karar = "ULAŞILAMIYOR (fiziksel yol yok)"
    return f"{s['kaynak']} -> {s['hedef']}{port}: {karar}"


# ---- SIEM ----------------------------------------------------------------------------------

def siem(log: str, kaynak_adi: str) -> dict:
    if len(log.encode("utf-8")) > MAKS_LOG_BAYT:
        raise GirdiHatasi("Log en fazla 1 MB olabilir.")
    olaylar, hatali = mini_siem.olaylari_oku(log.splitlines())
    alarmlar = mini_siem.analiz_et(olaylar)
    return {"kaynak": kaynak_adi, "olay": len(olaylar), "hatali": hatali,
            "alarmlar": [{"seviye": a.seviye, "kural": a.kural, "aciklama": a.aciklama,
                          "zaman": a.zaman.strftime("%Y-%m-%d %H:%M:%S"), "kanit": len(a.kanit)} for a in alarmlar]}


def siem_ozeti(s: dict) -> str:
    return f"{s['olay']} olay, {len(s['alarmlar'])} alarm"


# ---- geçmiş --------------------------------------------------------------------------------

def kaydet(kullanici, obj, tur: str, girdi: dict, sonuc: dict, ozet_metni: str) -> models.Simulasyon:
    return models.Simulasyon.objects.create(
        kullanici=kullanici, senaryo=obj, tur=tur, girdi=girdi, sonuc=sonuc, ozet=ozet_metni[:200])
