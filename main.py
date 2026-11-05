"""Komut satırı arayüzü.

Örnekler:
    python main.py hata hastane
    python main.py hata hepsi --kablosuz-yok
    python main.py hata hastane --bozuk core_1,core_2
    python main.py erisim universite
    python main.py erisim universite --sorgu ogrenci_cihazi ogrenci_isleri_db 3306
    python main.py siem ornek_loglar/saldirili.log
    python main.py izleme ofis --bozuk core_1
    python main.py alarm ofis --bozuk core_1 --desen 0111110111
    python main.py diyagram > docs/topolojiler.md
"""
from __future__ import annotations

import argparse
import sys

from ag_motoru import (alarm_yonetimi, erisim_matrisi, hata_simulasyonu, mermaid_uret, mini_izleme,
                       mini_siem, ornek_log_uret)
from ag_motoru.ag_modelleri import SENARYOLAR, senaryo_al, tum_senaryolar


def _senaryolar(ad: str) -> list:
    return tum_senaryolar() if ad == "hepsi" else [senaryo_al(ad)]


def komut_hata(a) -> None:
    for s in _senaryolar(a.senaryo):
        if a.bozuk:
            bozuklar = a.bozuk.split(",")
            sonuc = hata_simulasyonu.coklu_hata(s, bozuklar)
            print(f"== {s.baslik}: {', '.join(bozuklar)} bozuk ==")
            print("Kapanan cihazlar:", ", ".join(sonuc["olu"]) or "-")
            if sonuc["kopan"]:
                for r in sonuc["kopan"]:
                    print(f"  [!] KOPTU: {r.aciklama}")
            else:
                print("Tüm gereksinimler karşılanıyor.")
        else:
            print(hata_simulasyonu.rapor_metni(s))
        print()


def komut_erisim(a) -> None:
    s = senaryo_al(a.senaryo)
    if a.sorgu:
        kaynak, hedef = a.sorgu[0], a.sorgu[1]
        port = int(a.sorgu[2]) if len(a.sorgu) > 2 else None
        r = erisim_matrisi.uctan_uca(s, kaynak, hedef, port)
        print(f"{kaynak} ({r['kaynak_bolge']}) -> {hedef} ({r['hedef_bolge']})"
              + (f" port {port}" if port else ""))
        print(f"  fiziksel yol : {'VAR' if r['fiziksel_yol'] else 'YOK'}")
        print(f"  politika izni: {'VAR' if r['politika_izni'] else 'YOK'}")
        print(f"  sonuç        : {'İZİN' if r['sonuc'] else 'ENGEL'}")
        return
    print(erisim_matrisi.matris_metni(s))
    ihlal = erisim_matrisi.engelleri_dogrula(s)
    print()
    print(f"Beklenen {len(s.engeller)} engel kontrol edildi: "
          + ("hepsi engelleniyor." if not ihlal else f"{len(ihlal)} İHLAL var!"))
    for e in ihlal:
        print(f"  [!] {e.kaynak} -> {e.hedef} {e.port or ''}: {e.aciklama}")


def komut_siem(a) -> None:
    with open(a.dosya, encoding="utf-8") as f:
        olaylar, hatali = mini_siem.olaylari_oku(f)
    alarmlar = mini_siem.analiz_et(olaylar)
    print(mini_siem.rapor_metni(alarmlar, len(olaylar), hatali))


def komut_izleme(a) -> None:
    bozuklar = a.bozuk.split(",") if a.bozuk else ()
    for s in _senaryolar(a.senaryo):
        print(mini_izleme.izleme_metni(s, bozuklar))
        print(alarm_yonetimi.kok_neden_metni(s, mini_izleme.ag_izleme(s, bozuklar)))
        print()


def komut_alarm(a) -> None:
    s = senaryo_al(a.senaryo)
    bozuklar = a.bozuk.split(",") if a.bozuk else []
    gecerli = {ad for ad, _, _ in hata_simulasyonu.secilebilir_elemanlar(s)}
    yanlis = [b for b in bozuklar if b not in gecerli]
    if yanlis:
        sys.exit("Bilinmeyen eleman: " + ", ".join(yanlis))
    try:
        print(alarm_yonetimi.seri_metni(s, bozuklar, a.desen, deneme=a.deneme,
                                        pencere=a.pencere, esik=a.esik, aralik_sn=a.aralik))
    except ValueError as e:
        sys.exit(str(e))


def komut_diyagram(a) -> None:
    print(mermaid_uret.belge())


def komut_log_uret(a) -> None:
    for yol in ornek_log_uret.yaz(a.klasor):
        print("yazıldı:", yol)


def ana() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    secenekler = list(SENARYOLAR) + ["hepsi"]
    p = argparse.ArgumentParser(description="Ağ topolojisi simülasyonu")
    alt = p.add_subparsers(dest="komut", required=True)

    h = alt.add_parser("hata", help="tek hata noktası analizi / çoklu hata denemesi")
    h.add_argument("senaryo", choices=secenekler)
    h.add_argument("--bozuk", help="virgülle ayrılmış bozuk cihazlar/güç kaynakları")
    h.set_defaults(fn=komut_hata)

    e = alt.add_parser("erisim", help="VLAN erişim matrisi ve sorgu")
    e.add_argument("senaryo", choices=list(SENARYOLAR))
    e.add_argument("--sorgu", nargs="+", metavar=("KAYNAK", "HEDEF"),
                   help="KAYNAK HEDEF [PORT] cihaz adlarıyla uçtan uca sorgu")
    e.set_defaults(fn=komut_erisim)

    s = alt.add_parser("siem", help="log dosyasını analiz et")
    s.add_argument("dosya")
    s.set_defaults(fn=komut_siem)

    i = alt.add_parser("izleme", help="izleme düğümü gözüyle cihaz durumu")
    i.add_argument("senaryo", choices=secenekler)
    i.add_argument("--bozuk", help="virgülle ayrılmış bozuk cihazlar")
    i.set_defaults(fn=komut_izleme)

    al = alt.add_parser("alarm", help="zaman içinde alarm akışı: kök neden, histerezis, dalgalanma")
    al.add_argument("senaryo", choices=list(SENARYOLAR))
    al.add_argument("--bozuk", required=True, help="virgülle ayrılmış bozulup onarılan elemanlar")
    al.add_argument("--desen", required=True, help="her kontrol için 1 (bozuk) / 0 (sağlam), örn. 0111010111")
    al.add_argument("--deneme", type=int, default=3, help="alarm için üst üste başarısız kontrol sayısı")
    al.add_argument("--pencere", type=int, default=10, help="dalgalanma için bakılan son kontrol sayısı")
    al.add_argument("--esik", type=int, default=3, help="penceredeki durum değişikliği eşiği")
    al.add_argument("--aralik", type=int, default=60, help="iki kontrol arası saniye")
    al.set_defaults(fn=komut_alarm)

    d = alt.add_parser("diyagram", help="Mermaid diyagramlarını yazdır")
    d.set_defaults(fn=komut_diyagram)

    u = alt.add_parser("log-uret", help="örnek log dosyalarını üret")
    u.add_argument("--klasor", default="ornek_loglar")
    u.set_defaults(fn=komut_log_uret)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    ana()
