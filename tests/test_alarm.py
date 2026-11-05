import pytest

from ag_motoru.alarm_yonetimi import desen_coz, kok_neden, seri_analizi, ust_dugumler
from ag_motoru.ag_modelleri import eticaret, hastane, ofis, tum_senaryolar, universite
from ag_motoru.mini_izleme import ag_izleme, UP


# ---- kök neden bastırma --------------------------------------------------------------------

def test_ofiste_core_dusunce_tek_kok_neden():
    s = ofis()
    k = kok_neden(s, ag_izleme(s, ("core_1",)))
    assert k["kokler"] == ["core_1"]
    assert len(k["bastirilan"]) == 21
    assert all(v == ["core_1"] for v in k["bastirilan"].values())


def test_firewall_dusunce_sadece_arkasindakiler_bastirilir():
    s = ofis()
    k = kok_neden(s, ag_izleme(s, ("fw_1",)))
    assert k["kokler"] == ["fw_1"]
    assert "kat1_sw" not in k["bastirilan"]  # firewall'ın arkasında değil, hâlâ UP


def test_iki_core_iki_kok_neden_ve_belirtiler_ikisine_baglanir():
    s = hastane()
    k = kok_neden(s, ag_izleme(s, ("core_1", "core_2")))
    assert k["kokler"] == ["core_1", "core_2"]
    assert k["bastirilan"]
    assert all(v == ["core_1", "core_2"] for v in k["bastirilan"].values())


def test_yedekli_agda_tek_core_dusunce_bastirilacak_bir_sey_yok():
    s = hastane()
    k = kok_neden(s, ag_izleme(s, ("core_1",)))
    assert k["kokler"] == ["core_1"] and k["bastirilan"] == {}


def test_saglam_ag_alarm_yok():
    s = ofis()
    assert kok_neden(s, ag_izleme(s)) == {"kokler": [], "bastirilan": {}, "izleme_kapali": False}


def test_izleme_dugumu_kapaliysa_ayirt_edilemez():
    s = ofis()
    k = kok_neden(s, ag_izleme(s, ("zabbix",)))
    assert k["izleme_kapali"] and k["kokler"] == []


@pytest.mark.parametrize("senaryo", tum_senaryolar(), ids=lambda s: s.ad)
def test_her_tekli_ve_ikili_arizada_kok_ve_belirti_ayrisir(senaryo):
    """UP olmayan her cihaz ya kök neden ya da bastırılan belirtidir; ikisi birden değil."""
    ustler, _ = ust_dugumler(senaryo)
    elemanlar = [n for n, d in senaryo.graf.nodes(data=True) if d["tur"] not in ("istemci", "internet")]
    for n in elemanlar:
        durum = ag_izleme(senaryo, (n,))
        k = kok_neden(senaryo, durum)
        down = {c for c, d in durum.items() if d != UP}
        if k["izleme_kapali"]:
            continue
        assert set(k["kokler"]) | set(k["bastirilan"]) == down
        assert not set(k["kokler"]) & set(k["bastirilan"])
        for c, koker in k["bastirilan"].items():
            assert koker and set(koker) <= set(k["kokler"])
        for r in k["kokler"]:  # kök nedenin en az bir üst komşusu sağlam
            assert not ustler.get(r) or any(u not in down for u in ustler[r])


def test_uc_senaryoda_bilinen_koklar():
    for s, ariza, beklenen in ((eticaret(), ("core_1",), ["core_1"]),
                               (universite(), ("fw_1",), ["fw_1"])):
        assert kok_neden(s, ag_izleme(s, ariza))["kokler"] == beklenen


# ---- desen ve parametre doğrulama ----------------------------------------------------------

def test_desen_cozme():
    assert desen_coz("0110") == [False, True, True, False]
    assert desen_coz(" 01 ") == [False, True]


@pytest.mark.parametrize("kotu", ["", "0", "01a", "0 1", "2", "01" * 100, None])
def test_gecersiz_desen(kotu):
    with pytest.raises(ValueError):
        desen_coz(kotu)


@pytest.mark.parametrize("ayar", [{"deneme": 0}, {"deneme": 11}, {"pencere": 2}, {"esik": 1},
                                  {"pencere": 5, "esik": 6}, {"aralik_sn": 0}, {"deneme": "3"}, {"deneme": True}])
def test_gecersiz_ayar(ayar):
    with pytest.raises(ValueError):
        seri_analizi(ofis(), ["core_1"], "0110", **ayar)


# ---- histerezis, dalgalanma, olaylar -------------------------------------------------------

def _bildirim_turleri(s):
    return [b["tur"] for b in s["bildirimler"]]


def test_hic_bozulmazsa_hicbir_sey_olmaz():
    s = seri_analizi(ofis(), ["core_1"], "0000000")
    assert s["bildirimler"] == [] and s["olaylar"] == [] and s["cihazlar"] == []
    assert s["ozet"]["ham_alarm"] == 0


def test_kisa_kesinti_histerezisle_elenir():
    """Üst üste 3 kontrolden kısa kesinti alarm üretmez."""
    s = seri_analizi(ofis(), ["core_1"], "0110000000", deneme=3)
    assert s["ozet"]["ham_alarm"] == 22 and s["ozet"]["onayli_alarm"] == 0
    assert s["ozet"]["gecici"] == 22
    assert s["bildirimler"] == []
    assert all(not o["onayli"] for o in s["olaylar"])


def test_uzun_kesinti_tek_alarm_ve_kurtarma():
    s = seri_analizi(ofis(), ["core_1"], "0011111000", deneme=3)
    assert _bildirim_turleri(s) == ["ALARM", "KURTARMA"]
    alarm, kurtarma = s["bildirimler"]
    assert alarm["cihaz"] == "core_1" and alarm["adim"] == 5  # 3. üst üste başarısız kontrol
    assert kurtarma["adim"] == 8
    assert s["ozet"]["kok_bastirilan"] == 21


def test_deneme_1_ilk_basarisizlikta_alarm_verir():
    s = seri_analizi(ofis(), ["core_1"], "0110", deneme=1)
    assert s["bildirimler"][0]["adim"] == 2


def test_olay_suresi_ve_acik_olay():
    s = seri_analizi(ofis(), ["core_1"], "0001111", deneme=3, aralik_sn=30)
    o = next(x for x in s["olaylar"] if x["cihaz"] == "core_1")
    assert (o["baslangic"], o["sure"], o["acik"], o["bitis"], o["sure_sn"]) == (4, 4, True, None, 120)
    assert o["kok_neden"] is True
    belirti = next(x for x in s["olaylar"] if x["cihaz"] == "fw_1")
    assert belirti["kok_neden"] is False


def test_kapanan_olayin_bitisi_kurtarma_adimidir():
    s = seri_analizi(ofis(), ["core_1"], "0110000")
    o = next(x for x in s["olaylar"] if x["cihaz"] == "core_1")
    assert (o["baslangic"], o["bitis"], o["acik"]) == (2, 4, False)


def test_dalgalanan_cihaz_tek_bildirim_alir():
    s = seri_analizi(ofis(), ["core_1"], "0101010101", deneme=2, pencere=10, esik=3)
    turler = _bildirim_turleri(s)
    assert turler.count("DALGALANMA") == 1
    assert next(b for b in s["bildirimler"] if b["tur"] == "DALGALANMA")["cihaz"] == "core_1"
    assert "ALARM" not in turler  # 1'er kontrollük kesintiler deneme=2'yi geçemez
    assert s["ozet"]["dalgali_cihaz"] == 22


def test_dalgalanma_baslayinca_sonraki_alarm_bastirilir():
    s = seri_analizi(ofis(), ["core_1"], "0111110111", deneme=3, pencere=10, esik=3)
    assert _bildirim_turleri(s) == ["ALARM", "KURTARMA", "DALGALANMA"]
    assert s["ozet"]["dalgalanma_bastirilan"] == 1  # 10. kontrolde core_1 alarmı


def test_belirtiler_icin_ayri_dalgalanma_bildirimi_yok():
    s = seri_analizi(ofis(), ["core_1"], "0101010101", deneme=2)
    assert {b["cihaz"] for b in s["bildirimler"] if b["tur"] == "DALGALANMA"} == {"core_1"}


def test_esigin_altinda_dalgalanma_yok():
    s = seri_analizi(ofis(), ["core_1"], "0111100000", deneme=3, esik=3)  # 2 geçiş
    assert s["ozet"]["dalgali_cihaz"] == 0


def test_kullanilabilirlik():
    s = seri_analizi(ofis(), ["core_1"], "0111110111")
    core = next(c for c in s["cihazlar"] if c["ad"] == "core_1")
    assert core["kullanilabilirlik"] == 20.0 and core["ham_alarm"] == 2 and core["gecis"] == 3


def test_yedekli_agda_tek_core_bozulunca_yalniz_core_gorunur():
    s = seri_analizi(hastane(), ["core_1"], "0011100")
    assert [c["ad"] for c in s["cihazlar"]] == ["core_1"]
    assert _bildirim_turleri(s) == ["ALARM", "KURTARMA"]


def test_sayilar_tutarli():
    for desen in ("0111110111", "0101010101", "0011000110", "1111111111"):
        s = seri_analizi(hastane(), ["core_1", "core_2"], desen)
        o = s["ozet"]
        assert o["ham_alarm"] >= o["onayli_alarm"] and o["gecici"] == o["ham_alarm"] - o["onayli_alarm"]
        assert o["bildirim"] == len(s["bildirimler"])
        assert len(s["adimlar"]) == len(desen) == o["adim"]
        for o_ in s["olaylar"]:
            assert o_["sure"] >= 1 and (o_["bitis"] is None) == o_["acik"]


def test_ayni_girdi_ayni_sonuc():
    a = seri_analizi(ofis(), ["core_1"], "0111010111")
    b = seri_analizi(ofis(), ["core_1"], "0111010111")
    assert a == b


def test_izleme_dugumu_kapaliyken_alarm_uretilmez():
    s = seri_analizi(ofis(), ["zabbix"], "0111110")
    assert s["bildirimler"] == []  # izleme körleşti: hiçbir şey bildirilemez


def test_ust_komsularindan_biri_saglamsa_cihaz_kendi_basina_kok_nedendir():
    """fw_1'in iki üst komşusu var (core_1 düşük, core_2 sağlam): fw_1 de bozulduysa o da köktür."""
    s = hastane()
    assert set(ust_dugumler(s)[0]["fw_1"]) == {"core_1", "core_2"}
    k = kok_neden(s, ag_izleme(s, ("core_1", "fw_1")))
    assert k["kokler"] == ["core_1", "fw_1"]
    assert "fw_1" not in k["bastirilan"]


def test_firewall_bastirilanlar_tam_liste():
    s = ofis()
    assert sorted(kok_neden(s, ag_izleme(s, ("fw_1",)))["bastirilan"]) == [
        "dmz_sw", "eposta", "hat_1", "router_1", "web_sunucu"]
