from ag_motoru.ag_modelleri import eticaret, hastane, ofis, universite
from ag_motoru.hata_simulasyonu import (coklu_hata, karsilanmayanlar, tek_hata_analizi,
                                        ulasilabilir, canli_graf)


def spof_adlari(s):
    return {x["eleman"] for x in tek_hata_analizi(s)["spof"]}


def test_saglam_ag_hicbir_sey_kopmaz():
    for s in (ofis(), eticaret(), universite(), hastane()):
        assert karsilanmayanlar(s) == []


def test_ofis_tek_hata_noktalari():
    assert {"hat_1", "router_1", "fw_1", "core_1", "dmz_sw"} <= spof_adlari(ofis())


def test_universite_tek_hata_noktalari():
    assert {"hat_1", "router_1", "fw_1", "core_1"} <= spof_adlari(universite())


def test_yedekli_senaryolarda_merkezi_spof_yok():
    assert spof_adlari(eticaret()) == set()
    assert spof_adlari(hastane()) == set()


def test_jeneratorsuz_ofiste_sebeke_spof():
    assert "sebeke" not in spof_adlari(ofis(jenerator=True))
    assert "sebeke" in spof_adlari(ofis(jenerator=False))


def test_hastane_tek_core_dusunce_calismaya_devam_eder():
    s = hastane()
    assert karsilanmayanlar(s, bozuklar=("core_1",)) == []
    assert karsilanmayanlar(s, bozuklar=("core_2",)) == []


def test_hastane_iki_core_birden_dusunce_kopar():
    sonuc = coklu_hata(hastane(), bozuklar=("core_1", "core_2"))
    assert sonuc["kopan"], "iki core birden düşünce sunucu odasına erişim kopmalı"


def test_hastane_iki_hat_birden_dusunce_internet_kopar():
    kopan = karsilanmayanlar(hastane(), bozuklar=("hat_1", "hat_2"))
    assert any(r.kaynak == "hasta_telefonu" for r in kopan)
    # ama iç sistemler (hekim -> HBYS) etkilenmez
    assert not any(r.kaynak == "acil_pc" for r in kopan)


def test_ofis_firewall_dusunce_internet_kopar():
    kopan = karsilanmayanlar(ofis(), bozuklar=("fw_1",))
    assert {r.kaynak for r in kopan} >= {"pc_k1", "misafir_k2", "internet"}


def test_guc_kaynagi_bozulunca_bagli_cihazlar_kapanir():
    s = ofis(jenerator=False)
    g = canli_graf(s, bozuklar=("sebeke",))
    assert "core_1" not in g and "router_1" not in g


def test_sunucu_icinden_gecis_yok():
    """Sunucu uç cihazdır: core_1 sadece sunuculara bağlı kalırsa, sunucular üzerinden
    core_2'ye köprü kurup internete ulaşamaz."""
    s = hastane()
    g = canli_graf(s)
    for komsu in list(g["core_1"]):
        if g.nodes[komsu]["tur"] != "sunucu" and g.nodes[komsu]["tur"] != "yonetim":
            g.remove_edge("core_1", komsu)
    assert set(g["core_1"])  # hâlâ sunuculara bağlı
    assert not ulasilabilir(g, "core_1", "internet")
    assert ulasilabilir(g, "core_2", "internet")


def test_coklu_hata_guc_ve_cihaz():
    s = hastane()
    # üç güç kaynağı da gidince tüm altyapı kapanır
    sonuc = coklu_hata(s, bozuklar=("sebeke_1", "sebeke_2", "jenerator"))
    assert "core_1" in sonuc["olu"] and "core_2" in sonuc["olu"]
    assert sonuc["kopan"]
