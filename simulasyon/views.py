"""Django görünümleri: simülasyon motorunu (ag_motoru) web sayfalarına bağlar."""
from functools import lru_cache

from django.http import Http404
from django.shortcuts import render

from ag_motoru import (erisim_matrisi, hata_simulasyonu, mermaid_uret, mini_izleme,
                       mini_siem, ornek_log_uret)
from ag_motoru.ag_modelleri import SENARYOLAR, senaryo_al

MAKS_LOG_BAYT = 1_000_000


def _senaryo(ad):
    try:
        return senaryo_al(ad)
    except KeyError:
        raise Http404("Senaryo bulunamadı")


@lru_cache(maxsize=None)
def _ozet(ad):
    s = senaryo_al(ad)
    a = hata_simulasyonu.tek_hata_analizi(s)
    return {"ad": ad, "baslik": s.baslik, "dugum": s.graf.number_of_nodes(),
            "kablo": s.graf.number_of_edges(), "spof": len(a["spof"]),
            "yerel": len(a["yerel"]), "gereksinim": len(s.gereksinimler)}


def _liste(sonuclar):
    return [{"cesit": x["cesit"], "eleman": x["eleman"],
             "etki": hata_simulasyonu.etki_metni(x["etki"])} for x in sonuclar]


def _secili_bozuklar(request, senaryo):
    gecerli = {ad for ad, _, _ in hata_simulasyonu.secilebilir_elemanlar(senaryo)}
    return [b for b in request.GET.getlist("bozuk") if b in gecerli]


def _secici(senaryo, secili):
    return [{"ad": ad, "etiket": etiket, "cesit": cesit, "secili": ad in secili}
            for ad, etiket, cesit in hata_simulasyonu.secilebilir_elemanlar(senaryo)]


def index(request):
    return render(request, "simulasyon/index.html",
                  {"ozetler": [_ozet(ad) for ad in SENARYOLAR]})


def senaryo_detay(request, ad):
    s = _senaryo(ad)
    analiz = hata_simulasyonu.tek_hata_analizi(s)
    return render(request, "simulasyon/senaryo.html", {
        "s": s, "sayfa": "senaryo", "diyagram": mermaid_uret.mermaid(s),
        "kontrol": analiz["kontrol"], "spof": _liste(analiz["spof"]),
        "yerel": _liste(analiz["yerel"]), "gereksinimler": s.gereksinimler,
    })


def hata(request, ad):
    s = _senaryo(ad)
    bozuk = _secili_bozuklar(request, s)
    sonuc = hata_simulasyonu.coklu_hata(s, bozuk) if bozuk else None
    olu = sonuc["olu"] if sonuc else []
    return render(request, "simulasyon/hata.html", {
        "s": s, "sayfa": "hata", "secici": _secici(s, bozuk), "bozuk": bozuk,
        "sonuc": sonuc, "olu": olu,
        "guc_kapanan": [n for n in olu if n not in bozuk],
        "diyagram": mermaid_uret.mermaid(s, bozuk=bozuk, olu=olu),
    })


def erisim(request, ad):
    s = _senaryo(ad)
    zonlar = erisim_matrisi.bolgeler(s)
    m = erisim_matrisi.matris(s)
    satirlar = []
    for k in zonlar:
        hucreler = []
        for h in zonlar:
            durum = m[(k, h)]
            portlar = ""
            if durum == "kismi":
                portlar = ",".join(str(p) for p in sorted(erisim_matrisi.izinli_portlar(s, k, h)))
            hucreler.append({"durum": durum, "portlar": portlar})
        satirlar.append({"kaynak": k, "hucreler": hucreler})

    cihazlar = [n for n, d in s.graf.nodes(data=True) if d["bolge"]]
    sorgu = None
    hata_mesaji = None
    kaynak, hedef, port = (request.GET.get("kaynak", ""), request.GET.get("hedef", ""),
                           request.GET.get("port", "").strip())
    if kaynak and hedef:
        if kaynak not in cihazlar or hedef not in cihazlar:
            hata_mesaji = "Geçersiz cihaz seçimi."
        elif port and not port.isdigit():
            hata_mesaji = "Port sayı olmalı."
        else:
            sorgu = erisim_matrisi.uctan_uca(s, kaynak, hedef, int(port) if port else None)

    ihlaller = erisim_matrisi.engelleri_dogrula(s)
    return render(request, "simulasyon/erisim.html", {
        "s": s, "sayfa": "erisim", "zonlar": zonlar, "satirlar": satirlar,
        "engeller": s.engeller, "ihlaller": ihlaller, "cihazlar": cihazlar,
        "kaynak": kaynak, "hedef": hedef, "port": port, "sorgu": sorgu,
        "hata_mesaji": hata_mesaji,
    })


def izleme(request, ad):
    s = _senaryo(ad)
    bozuk = _secili_bozuklar(request, s)
    durumlar = mini_izleme.ag_izleme(s, bozuk)
    up = sum(1 for d in durumlar.values() if d == mini_izleme.UP)
    return render(request, "simulasyon/izleme.html", {
        "s": s, "sayfa": "izleme", "secici": _secici(s, bozuk), "bozuk": bozuk,
        "durumlar": [{"ad": n, "etiket": s.graf.nodes[n]["etiket"], "durum": d,
                      "ok": d == mini_izleme.UP} for n, d in durumlar.items()],
        "up": up, "toplam": len(durumlar), "izleyici": s.izleme_dugumu,
    })


def siem(request):
    log, hata_mesaji, kaynak_adi = "", None, ""
    if request.method == "POST":
        yuklenen = request.FILES.get("dosya")
        if yuklenen:
            if yuklenen.size > MAKS_LOG_BAYT:
                hata_mesaji = "Dosya en fazla 1 MB olabilir."
            else:
                log = yuklenen.read().decode("utf-8", errors="replace")
                kaynak_adi = yuklenen.name
        else:
            log = request.POST.get("log", "")
            kaynak_adi = "yapıştırılan metin"
            if len(log.encode("utf-8")) > MAKS_LOG_BAYT:
                hata_mesaji, log = "Metin en fazla 1 MB olabilir.", ""
    elif request.GET.get("ornek") in ("saldirili", "normal"):
        ornek = request.GET["ornek"]
        log = "\n".join(ornek_log_uret.uret(saldiri=ornek == "saldirili"))
        kaynak_adi = f"örnek {ornek} log"

    rapor = None
    if log.strip() and not hata_mesaji:
        olaylar, hatali = mini_siem.olaylari_oku(log.splitlines())
        alarmlar = mini_siem.analiz_et(olaylar)
        rapor = {"kaynak": kaynak_adi, "olay": len(olaylar), "hatali": hatali,
                 "alarmlar": [{"seviye": a.seviye, "kural": a.kural, "aciklama": a.aciklama,
                               "zaman": a.zaman, "kanit": len(a.kanit)} for a in alarmlar]}
    return render(request, "simulasyon/siem.html", {
        "rapor": rapor, "hata_mesaji": hata_mesaji, "sayfa": "siem",
        "log_onizleme": "\n".join(log.splitlines()[:200]) if rapor else "",
    })
