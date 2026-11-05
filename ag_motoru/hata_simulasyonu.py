"""Hata simülasyonu: bir cihaz, kablo ya da güç kaynağı bozulursa ne olur?

Adımlar (her hata için):
  1. Bozulan düğümleri (ve gücü kesilenleri) graftan çıkar, bozuk kabloları sil.
  2. Her gereksinim için, kaynaktan hedeflerden en az birine yol var mı diye bak.
  3. Yol yoksa gereksinim "kopmuş" sayılır.
Tek bir elemanın bozulması bir gereksinimi koparıyorsa o eleman tek hata noktasıdır (SPOF).
"""
from __future__ import annotations

from collections import deque

from .ag_modelleri import GECIS_TURLERI, Senaryo


def olu_dugumler(senaryo: Senaryo, bozuklar=()) -> set:
    """Bozulan düğümler + bütün güç kaynakları bozulduğu için kapanan düğümler."""
    g = senaryo.graf
    bozuklar = set(bozuklar)
    olu = {n for n in g if n in bozuklar}
    for n, d in g.nodes(data=True):
        if d["guc"] and all(k in bozuklar for k in d["guc"]):
            olu.add(n)
    return olu


def canli_graf(senaryo: Senaryo, bozuklar=(), kopuk_baglantilar=()):
    g = senaryo.graf.copy()
    g.remove_nodes_from(olu_dugumler(senaryo, bozuklar))
    g.remove_edges_from([tuple(e) for e in kopuk_baglantilar])
    return g


def ulasilabilir(g, kaynak: str, hedef: str) -> bool:
    """Genişlik öncelikli arama. Sunucu/istemci gibi uç cihazların içinden geçilmez."""
    if kaynak not in g or hedef not in g:
        return False
    gorulen = {kaynak}
    kuyruk = deque([kaynak])
    while kuyruk:
        n = kuyruk.popleft()
        if n == hedef:
            return True
        if n != kaynak and g.nodes[n]["tur"] not in GECIS_TURLERI:
            continue
        for m in g[n]:
            if m not in gorulen:
                gorulen.add(m)
                kuyruk.append(m)
    return False


def karsilanmayanlar(senaryo: Senaryo, bozuklar=(), kopuk_baglantilar=()) -> list:
    """Verilen hata durumunda kopan gereksinimler."""
    g = canli_graf(senaryo, bozuklar, kopuk_baglantilar)
    return [r for r in senaryo.gereksinimler
            if not any(ulasilabilir(g, r.kaynak, h) for h in r.hedefler)]


def _onemsiz(r, olu: set) -> bool:
    """Bozulan eleman gereksinimin kendi uç noktasıysa kopma anlamsızdır
    (örn. PC bozulunca 'PC internete çıkabilmeli' kopar, bu bir tasarım hatası değil)."""
    return r.kaynak in olu or (len(r.hedefler) == 1 and r.hedefler[0] in olu)


def _hata_sonucu(senaryo, cesit, eleman, bozuklar=(), kopuk=(), yerel=False) -> dict:
    olu = olu_dugumler(senaryo, bozuklar) | {n for e in kopuk for n in e}
    etki = [r for r in karsilanmayanlar(senaryo, bozuklar, kopuk) if not _onemsiz(r, olu)]
    return {"eleman": eleman, "cesit": cesit, "etki": etki, "yerel": yerel}


def tek_hata_analizi(senaryo: Senaryo, baglantilar: bool = True) -> dict:
    """Her cihazı, her güç kaynağını ve (istenirse) her kabloyu tek tek bozar."""
    g = senaryo.graf
    sonuclar = []
    for n, d in g.nodes(data=True):
        if d["tur"] in ("istemci", "internet"):
            continue
        sonuclar.append(_hata_sonucu(senaryo, "cihaz", n, bozuklar=(n,),
                                     yerel=d["katman"] == "erisim"))
    for kaynak in sorted({k for _, d in g.nodes(data=True) for k in d["guc"]}):
        sonuclar.append(_hata_sonucu(senaryo, "güç", kaynak, bozuklar=(kaynak,)))
    if baglantilar:
        for a, b in g.edges:
            yerel = any(g.nodes[x]["katman"] == "erisim" or g.nodes[x]["tur"] == "istemci"
                        for x in (a, b))
            sonuclar.append(_hata_sonucu(senaryo, "kablo", f"{a} - {b}",
                                         kopuk=((a, b),), yerel=yerel))
    return {
        "kontrol": len(sonuclar),
        "spof": [s for s in sonuclar if s["etki"] and not s["yerel"]],
        "yerel": [s for s in sonuclar if s["etki"] and s["yerel"]],
    }


def coklu_hata(senaryo: Senaryo, bozuklar=(), kopuk_baglantilar=()) -> dict:
    """Birden fazla hatayı aynı anda dene (örn. iki core birden)."""
    olu = olu_dugumler(senaryo, bozuklar)
    return {"olu": sorted(olu), "kopan": karsilanmayanlar(senaryo, bozuklar, kopuk_baglantilar)}


def etki_metni(etki) -> str:
    return "; ".join(f"{r.kaynak} -> {'/'.join(r.hedefler)}" for r in etki)


def rapor_metni(senaryo: Senaryo, baglantilar: bool = True) -> str:
    s = tek_hata_analizi(senaryo, baglantilar)
    g = senaryo.graf
    satirlar = [
        f"== {senaryo.baslik} ==",
        f"{g.number_of_nodes()} düğüm, {g.number_of_edges()} kablo; "
        f"{s['kontrol']} tek hata denendi.",
    ]
    if s["spof"]:
        satirlar.append(f"Merkezi tek hata noktası: {len(s['spof'])}")
        for x in s["spof"]:
            satirlar.append(f"  [!] {x['cesit']:5} {x['eleman']}: {etki_metni(x['etki'])}")
    else:
        satirlar.append("Merkezi tek hata noktası: YOK")
    if s["yerel"]:
        satirlar.append(f"Erişim katmanı (sadece o kat/bina etkilenir): {len(s['yerel'])}")
        for x in s["yerel"]:
            satirlar.append(f"  [~] {x['cesit']:5} {x['eleman']}: {etki_metni(x['etki'])}")
    return "\n".join(satirlar)


def secilebilir_elemanlar(senaryo: Senaryo) -> list:
    """Arayüzde bozulabilecek elemanlar: (ad, etiket, çeşit). İstemciler ve internet hariç."""
    g = senaryo.graf
    cihazlar = [(n, d["etiket"], "cihaz") for n, d in g.nodes(data=True)
                if d["tur"] not in ("istemci", "internet")]
    guc = [(k, f"Güç kaynağı: {k}", "güç")
           for k in sorted({k for _, d in g.nodes(data=True) for k in d["guc"]})]
    return cihazlar + guc
