import pytest

from ag_motoru.ag_modelleri import SENARYOLAR, tum_senaryolar, universite, hastane, eticaret, ofis
from ag_motoru.erisim_matrisi import (engelleri_dogrula, izin_var_mi, izinli_portlar, matris,
                                      uctan_uca)


@pytest.mark.parametrize("s", tum_senaryolar(), ids=list(SENARYOLAR))
def test_beklenen_engellerin_hepsi_engelleniyor(s):
    assert engelleri_dogrula(s) == []


def test_varsayilan_red():
    s = universite()
    assert not izin_var_mi(s, "ogrenci", "ogrenci_isleri")
    assert not izin_var_mi(s, "ogrenci", "yonetim", 22)


def test_ayni_bolge_serbest():
    assert izin_var_mi(universite(), "ogrenci", "ogrenci")


def test_port_bazli_izin():
    s = eticaret()
    assert izin_var_mi(s, "dmz", "sunucu", 3306)
    assert not izin_var_mi(s, "dmz", "sunucu", 389)
    assert not izin_var_mi(s, "dmz", "sunucu", 22)
    assert izinli_portlar(s, "dmz", "sunucu") == {3306}


def test_yonetim_her_yere_erisir():
    s = hastane()
    assert izin_var_mi(s, "yonetim", "sunucu", 22)
    assert izin_var_mi(s, "yonetim", "hasta_wifi")
    assert not izin_var_mi(s, "hasta_wifi", "yonetim")


def test_matris_tutarli():
    s = ofis()
    m = matris(s)
    assert m[("misafir_wifi", "internet")] == "kismi"
    assert m[("misafir_wifi", "sunucu")] == "yok"
    assert m[("yonetim", "pc")] == "tum"
    assert m[("pc", "pc")] == "tum"


def test_kablo_yolu_var_ama_politika_engeller():
    """Öğrenci cihazından veritabanına kablo yolu vardır, ama kural engeller."""
    r = uctan_uca(universite(), "ogrenci_cihazi", "ogrenci_isleri_db", 3306)
    assert r["fiziksel_yol"] is True
    assert r["politika_izni"] is False
    assert r["sonuc"] is False


def test_yetkili_personel_veritabanina_erisir():
    r = uctan_uca(universite(), "ogrenci_isleri_pc", "ogrenci_isleri_db", 3306)
    assert r["sonuc"] is True


def test_yetkisiz_personel_veritabanina_erisemez():
    r = uctan_uca(universite(), "personel_pc", "ogrenci_isleri_db", 3306)
    assert r["fiziksel_yol"] and not r["politika_izni"]


def test_uctan_uca_cihaz_arizasinda_fiziksel_yol_gider():
    r = uctan_uca(universite(), "ogrenci_isleri_pc", "ogrenci_isleri_db", 3306, bozuklar=("core_1",))
    assert r["politika_izni"] is True
    assert r["fiziksel_yol"] is False
    assert r["sonuc"] is False


def test_hastane_tibbi_cihaz_internete_cikamaz():
    s = hastane()
    assert not izin_var_mi(s, "tibbi_cihaz", "internet", 443)
    assert izin_var_mi(s, "tibbi_cihaz", "sunucu", 104)
