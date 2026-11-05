from datetime import datetime

from ag_motoru.mini_siem import Esikler, analiz_et, olaylari_oku, rapor_metni
from ag_motoru.ornek_log_uret import uret


def kurallar(alarmlar):
    return [a.kural for a in alarmlar]


def test_normal_gunde_alarm_yok():
    olaylar, hatali = olaylari_oku(uret(saldiri=False))
    assert hatali == 0
    assert analiz_et(olaylar) == []


def test_saldirili_gunde_beklenen_alarmlar():
    olaylar, _ = olaylari_oku(uret(saldiri=True))
    alarmlar = analiz_et(olaylar)
    assert set(kurallar(alarmlar)) == {
        "BRUTE_FORCE", "BASARILI_GIRIS", "VERI_SIZINTISI", "PORT_TARAMA", "MESAI_DISI_ADMIN"}
    assert kurallar(alarmlar).count("VERI_SIZINTISI") == 1


def test_alarmlar_seviyeye_gore_siralanir():
    olaylar, _ = olaylari_oku(uret(saldiri=True))
    sira = [a.seviye for a in analiz_et(olaylar)]
    assert sira == sorted(sira, key=["KRITIK", "YUKSEK", "ORTA"].index)
    assert sira[0] == "KRITIK"


def test_korelasyon_kanit_olaylari_birlestirir():
    olaylar, _ = olaylari_oku(uret(saldiri=True))
    a = next(x for x in analiz_et(olaylar) if x.kural == "VERI_SIZINTISI")
    turler = {o.tur for o in a.kanit}
    assert turler == {"AUTH", "TRANSFER"}  # farklı log türleri bir araya geldi
    assert "1000 MB" in a.aciklama


def test_az_sayida_basarisiz_giris_alarm_uretmez():
    satirlar = [f"2026-11-05T10:00:0{i} fw_1 AUTH FAIL user=ali src=10.0.10.5" for i in range(4)]
    olaylar, _ = olaylari_oku(satirlar)
    assert analiz_et(olaylar) == []


def test_brute_force_ama_giris_yok():
    satirlar = [f"2026-11-05T14:00:0{i} fw_1 AUTH FAIL user=ali src=203.0.113.9" for i in range(6)]
    alarmlar = analiz_et(olaylari_oku(satirlar)[0])
    assert kurallar(alarmlar) == ["BRUTE_FORCE"]


def test_esik_degisince_sonuc_degisir():
    satirlar = [f"2026-11-05T14:00:0{i} fw_1 AUTH FAIL user=ali src=203.0.113.9" for i in range(3)]
    olaylar = olaylari_oku(satirlar)[0]
    assert analiz_et(olaylar) == []
    assert kurallar(analiz_et(olaylar, Esikler(brute_adet=3))) == ["BRUTE_FORCE"]


def test_farkli_kaynaklar_birlesmez():
    satirlar = []
    for i in range(3):
        satirlar.append(f"2026-11-05T14:00:0{i} fw_1 AUTH FAIL user=ali src=1.1.1.1")
        satirlar.append(f"2026-11-05T14:00:0{i} fw_1 AUTH FAIL user=ali src=2.2.2.2")
    assert analiz_et(olaylari_oku(satirlar)[0]) == []  # her kaynakta 3 deneme: eşik altı


def test_hatali_satirlar_sayilir_ve_atlanir():
    olaylar, hatali = olaylari_oku(["# yorum", "", "bu bir log degil",
                                    "2026-11-05T10:00:00 fw_1 AUTH FAIL user=ali src=1.1.1.1"])
    assert len(olaylar) == 1 and hatali == 1


def test_ayrisma():
    olaylar, _ = olaylari_oku(["2026-11-05T03:20:10 fw_1 FW DENY src=10.0.40.23 dst=10.0.60.10 dport=445 zone=misafir_wifi"])
    o = olaylar[0]
    assert o.zaman == datetime(2026, 11, 5, 3, 20, 10)
    assert (o.cihaz, o.tur, o.sonuc) == ("fw_1", "FW", "DENY")
    assert o.al("dport") == "445" and o.al("zone") == "misafir_wifi"


def test_rapor_metni():
    olaylar, hatali = olaylari_oku(uret(saldiri=True))
    metin = rapor_metni(analiz_et(olaylar), len(olaylar), hatali)
    assert "KRITIK" in metin and "VERI_SIZINTISI" in metin
    assert "Alarm yok" in rapor_metni([], 0)


def test_uretici_deterministik():
    assert uret(True, tohum=1) == uret(True, tohum=1)
