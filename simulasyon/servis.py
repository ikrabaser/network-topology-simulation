"""Servis katmanı: motoru (ag_motoru) çağırır, sonuçları JSON'a uygun sözlüklere çevirir.

Web görünümleri, REST API ve geçmiş kaydı aynı fonksiyonları kullanır; böylece bir sonuç
hangi yoldan istenirse istensin aynıdır. Geçmişe yazılan veri istemciden gelen sonuç değil,
buradaki hesaplamanın çıktısıdır.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Avg, Count, Max, Q, Sum

from ag_motoru import (alarm_yonetimi, erisim_matrisi, hata_simulasyonu, mermaid_uret,
                       mini_izleme, mini_siem)

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
    kok = alarm_yonetimi.kok_neden(es, durumlar)
    up = sum(1 for d in durumlar.values() if d == mini_izleme.UP)

    def rol(n):
        if n in kok["kokler"]:
            return "kok"
        return "bastirilan" if n in kok["bastirilan"] else ""

    return {"bozuk": list(bozuk), "izleyici": es.izleme_dugumu, "up": up, "toplam": len(durumlar),
            "durumlar": [{"ad": n, "etiket": es.graf.nodes[n]["etiket"], "durum": d,
                          "ok": d == mini_izleme.UP, "alarm": rol(n),
                          "koker": kok["bastirilan"].get(n, [])} for n, d in durumlar.items()],
            "alarmlar": mini_izleme.alarmlar(durumlar),
            "kok_neden": {"kokler": kok["kokler"], "bastirilan": len(kok["bastirilan"]),
                          "izleme_kapali": kok["izleme_kapali"]}}


def izleme_ozeti(s: dict) -> str:
    return f"{s['up']}/{s['toplam']} cihaz UP" + (f" ({', '.join(s['bozuk'])} bozuk)" if s["bozuk"] else "")


# ---- alarm akışı (zaman çizelgesi) ---------------------------------------------------------

VARSAYILAN_AYAR = {"deneme": 3, "pencere": 10, "esik": 3, "aralik": 60}
ORNEK_DESENLER = [("Kısa kesinti", "0110000000"), ("Uzun kesinti", "0011111000"),
                  ("Dalgalanma", "0101010101"), ("Kesinti sonra dalgalanma", "0111110111")]


def _tam_sayi(deger, ad, varsayilan):
    if deger is None or str(deger).strip() == "":
        return varsayilan
    if isinstance(deger, bool) or not str(deger).strip().lstrip("-").isdigit():
        raise GirdiHatasi(f"{ad} bir tam sayı olmalı.")
    return int(str(deger).strip())


def zaman_girdisi(es, bozuk, desen, ayar, katı: bool = False) -> dict:
    """Formdan/API'den gelen değerleri doğrulayıp temiz bir girdi sözlüğü üretir."""
    bozuk = bozuklari_ayikla(es, bozuk, katı=katı)
    if not bozuk:
        raise GirdiHatasi("Bozulup onarılacak en az bir eleman seçin.")
    desen = (desen or "").strip()
    try:
        alarm_yonetimi.desen_coz(desen)
    except ValueError as e:
        raise GirdiHatasi(str(e))
    girdi = {"bozuk": bozuk, "desen": desen}
    for ad, varsayilan in VARSAYILAN_AYAR.items():
        girdi[ad] = _tam_sayi(ayar.get(ad), ad, varsayilan)
    return girdi


def zaman(es, girdi: dict) -> dict:
    try:
        return alarm_yonetimi.seri_analizi(
            es, girdi["bozuk"], girdi["desen"], deneme=girdi["deneme"], pencere=girdi["pencere"],
            esik=girdi["esik"], aralik_sn=girdi["aralik"])
    except ValueError as e:
        raise GirdiHatasi(str(e))


def zaman_ozeti(s: dict) -> str:
    o = s["ozet"]
    return (f"{', '.join(s['bozuk'])}: {o['adim']} kontrol, {o['ham_alarm']} ham alarm, "
            f"{o['bildirim']} bildirim")


@transaction.atomic
def kaydet_zaman(kullanici, obj, girdi: dict, sonuc: dict) -> models.Simulasyon:
    """Çalıştırmayı kaydeder; onaylanan arıza olaylarını ayrıca sorgulanabilir kayıt olarak yazar."""
    k = kaydet(kullanici, obj, models.Simulasyon.ZAMAN, girdi, sonuc, zaman_ozeti(sonuc))
    models.Ariza.objects.bulk_create([
        models.Ariza(simulasyon=k, kullanici=kullanici, senaryo=obj, cihaz=o["cihaz"],
                     baslangic=o["baslangic"], bitis=o["bitis"], sure=o["sure"], sure_sn=o["sure_sn"],
                     acik=o["acik"], kok_neden=bool(o["kok_neden"]), dalgali=o["dalgali"])
        for o in sonuc["olaylar"] if o["onayli"]])
    return k


def ariza_ozeti(kullanici, senaryo=None, belirtiler: bool = False) -> dict:
    """Kullanıcının kayıtlı arıza olaylarının özeti: cihaz başına sayı, toplam süre, ortalama onarım."""
    q = models.Ariza.objects.filter(kullanici=kullanici)
    if senaryo is not None:
        q = q.filter(senaryo=senaryo)
    if not belirtiler:
        q = q.filter(kok_neden=True)
    satirlar = (q.values("senaryo__slug", "cihaz")
                .annotate(sayi=Count("id"), toplam_sn=Sum("sure_sn"),
                          ortalama_onarim_sn=Avg("sure_sn", filter=Q(acik=False)),
                          dalgali=Count("id", filter=Q(dalgali=True)),
                          acik=Count("id", filter=Q(acik=True)), son=Max("zaman"))
                .order_by("-sayi", "-toplam_sn", "cihaz"))
    liste = [{"senaryo": r["senaryo__slug"], "cihaz": r["cihaz"], "sayi": r["sayi"],
              "toplam_sn": r["toplam_sn"], "acik": r["acik"], "dalgali": r["dalgali"],
              "ortalama_onarim_sn": None if r["ortalama_onarim_sn"] is None else round(r["ortalama_onarim_sn"]),
              "son": r["son"]} for r in satirlar]
    return {"olay": sum(r["sayi"] for r in liste), "cihaz": len(liste), "cihazlar": liste}


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
