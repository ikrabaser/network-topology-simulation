"""Senaryo grafından Mermaid diyagramı üretir (GitHub README'lerinde doğrudan çizilir).

Diyagram modelden otomatik üretildiği için kod ile çizim hiçbir zaman birbirinden ayrılmaz.
"""
from __future__ import annotations

from .ag_modelleri import Senaryo, tum_senaryolar

# tur -> (açılış, kapanış, sınıf)
SEKILLER = {
    "internet": ("((", "))", "dis"),
    "dis": ("((", "))", "dis"),
    "hat": ("[", "]", "hat"),
    "router": ("[", "]", "hat"),
    "firewall": ("{{", "}}", "fw"),
    "core": ("[", "]", "core"),
    "switch": ("[", "]", "core"),
    "ap": ("([", "])", "core"),
    "sunucu": ("[(", ")]", "sunucu"),
    "yonetim": ("[(", ")]", "yonetim"),
    "istemci": ("(", ")", "istemci"),
}

SINIFLAR = """\
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
"""


def mermaid(senaryo: Senaryo, bozuk=(), olu=()) -> str:
    """bozuk: elle bozulan düğümler (kırmızı). olu: güç kesintisiyle kapananlar (turuncu)."""
    g = senaryo.graf
    bozuk, olu = set(bozuk), set(olu) - set(bozuk)
    satirlar = ["flowchart TB"]
    for n, d in g.nodes(data=True):
        ac, kapa, _ = SEKILLER[d["tur"]]
        satirlar.append(f'    {n}{ac}"{d["etiket"]}"{kapa}')
    for a, b in g.edges:
        satirlar.append(f"    {a} --- {b}")
    satirlar.append(SINIFLAR.rstrip("\n"))
    ozel = bozuk | olu
    for sinif in sorted({v[2] for v in SEKILLER.values()}):
        uyeler = [n for n, d in g.nodes(data=True)
                  if SEKILLER[d["tur"]][2] == sinif and n not in ozel]
        if uyeler:
            satirlar.append(f"    class {','.join(uyeler)} {sinif}")
    if bozuk & set(g.nodes):
        satirlar.append(f"    class {','.join(sorted(bozuk & set(g.nodes)))} bozuk")
    if olu:
        satirlar.append(f"    class {','.join(sorted(olu))} gucsuz")
    return "\n".join(satirlar)


def belge() -> str:
    """Tüm senaryoların diyagramlarını içeren markdown."""
    parcalar = ["# Ağ topolojileri",
                "",
                "Bu dosya `python main.py diyagram` komutuyla modelden otomatik üretilir.",
                "Yuvarlak: internet/dış, dörtgen: ağ cihazı, altıgen: firewall, silindir: sunucu, "
                "yuvarlak köşeli: uç cihaz.",
                ""]
    for s in tum_senaryolar():
        parcalar += [f"## {s.baslik}", "", "```mermaid", mermaid(s), "```", ""]
    return "\n".join(parcalar)
