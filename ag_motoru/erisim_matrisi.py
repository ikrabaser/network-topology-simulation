"""VLAN / bölge erişim matrisi.

Mantık "varsayılan red"dir: bir kural açıkça izin vermiyorsa trafik engellenir.
Aynı bölge içindeki trafik serbesttir. Fiziksel yol (kablo) ile politika (kural)
ayrı şeylerdir: öğrenci cihazından veritabanına kablo yolu olabilir ama kural engeller.
"""
from __future__ import annotations

from .ag_modelleri import Senaryo
from .hata_simulasyonu import canli_graf, olu_dugumler, ulasilabilir


def bolgeler(senaryo: Senaryo) -> list:
    """Grafta geçen bölgeler, ilk görülme sırasıyla."""
    sonuc = []
    for _, d in senaryo.graf.nodes(data=True):
        if d["bolge"] and d["bolge"] not in sonuc:
            sonuc.append(d["bolge"])
    return sonuc


def izin_var_mi(senaryo: Senaryo, kaynak: str, hedef: str, port: int | None = None) -> bool:
    """port=None ise 'en az bir portta izin var mı?' diye sorar."""
    if kaynak == hedef:
        return True
    for k in senaryo.kurallar:
        if k.kaynak not in (kaynak, "*") or k.hedef not in (hedef, "*"):
            continue
        if k.portlar is None or port is None or port in k.portlar:
            return True
    return False


def izinli_portlar(senaryo: Senaryo, kaynak: str, hedef: str):
    """None -> tüm portlar, boş küme -> hiç izin yok, aksi halde port kümesi."""
    if kaynak == hedef:
        return None
    portlar = set()
    for k in senaryo.kurallar:
        if k.kaynak not in (kaynak, "*") or k.hedef not in (hedef, "*"):
            continue
        if k.portlar is None:
            return None
        portlar |= k.portlar
    return portlar


def matris(senaryo: Senaryo) -> dict:
    """(kaynak, hedef) -> 'tum' | 'kismi' | 'yok'"""
    z = bolgeler(senaryo)
    sonuc = {}
    for k in z:
        for h in z:
            p = izinli_portlar(senaryo, k, h)
            sonuc[(k, h)] = "tum" if p is None else ("kismi" if p else "yok")
    return sonuc


def matris_metni(senaryo: Senaryo) -> str:
    z = bolgeler(senaryo)
    m = matris(senaryo)
    genislik = max(len(x) for x in z) + 2
    simge = {"tum": "TÜM", "kismi": "kısmi", "yok": "-"}
    satirlar = [f"== {senaryo.baslik}: erişim matrisi (satır -> sütun) =="]
    satirlar.append(" " * genislik + "".join(f"{h[:genislik - 1]:<{genislik}}" for h in z))
    for k in z:
        satirlar.append(f"{k:<{genislik}}" + "".join(f"{simge[m[(k, h)]]:<{genislik}}" for h in z))
    satirlar.append("")
    satirlar.append("Kısmi izinler (sadece listelenen portlar):")
    for k in z:
        for h in z:
            if m[(k, h)] == "kismi":
                portlar = ",".join(str(p) for p in sorted(izinli_portlar(senaryo, k, h)))
                satirlar.append(f"  {k} -> {h}: {portlar}")
    return "\n".join(satirlar)


def engelleri_dogrula(senaryo: Senaryo) -> list:
    """Reddedilmesi gereken ama izin verilen erişimleri döndürür (boş liste = sorun yok)."""
    return [e for e in senaryo.engeller
            if izin_var_mi(senaryo, e.kaynak, e.hedef, e.port)]


def uctan_uca(senaryo: Senaryo, kaynak: str, hedef: str, port: int | None = None,
              bozuklar=()) -> dict:
    """İki cihaz arasında hem kablo yolu hem politika izni var mı?"""
    g = canli_graf(senaryo, bozuklar)
    fiziksel = ulasilabilir(g, kaynak, hedef)
    bk = senaryo.graf.nodes[kaynak]["bolge"]
    bh = senaryo.graf.nodes[hedef]["bolge"]
    politika = izin_var_mi(senaryo, bk, bh, port)
    return {"fiziksel_yol": fiziksel, "politika_izni": politika,
            "sonuc": fiziksel and politika, "kaynak_bolge": bk, "hedef_bolge": bh}
