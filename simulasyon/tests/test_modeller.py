"""Model doğrulamaları: hatalı topoloji veritabanına girmemeli."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .. import models
from .yardimci import SenaryolarYuklu


class CihazTestleri(SenaryolarYuklu):
    def setUp(self):
        self.ofis = models.Senaryo.objects.get(slug="ofis")

    def _yeni(self, **kw):
        return models.Cihaz(senaryo=self.ofis, **{"ad": "yeni_1", "tur": "switch", **kw})

    def test_gecerli_cihaz(self):
        self._yeni().full_clean()

    def test_gecersiz_adlar(self):
        for ad in ("Core1", "1core", "core-1", "core 1", "çekirdek"):
            with self.subTest(ad=ad), self.assertRaises(ValidationError):
                self._yeni(ad=ad).full_clean()

    def test_mermaid_ayrilmis_sozcukler_yasak(self):
        for ad in ("end", "graph", "class", "subgraph"):
            with self.subTest(ad=ad), self.assertRaises(ValidationError):
                self._yeni(ad=ad).full_clean()

    def test_etikette_tirnak_yasak(self):
        with self.assertRaises(ValidationError):
            self._yeni(etiket='bozuk "etiket"').full_clean()

    def test_ayni_senaryoda_ayni_ad_olmaz(self):
        with self.assertRaises(ValidationError):
            self._yeni(ad="core_1").full_clean()

    def test_baska_senaryoda_ayni_ad_olur(self):
        # core_1 hem ofiste hem hastanede var
        self.assertTrue(models.Cihaz.objects.filter(ad="core_1", senaryo__slug="hastane").exists())
        self.assertTrue(models.Cihaz.objects.filter(ad="core_1", senaryo__slug="ofis").exists())

    def test_guc_kaynagi_tekrari_yasak(self):
        with self.assertRaises(ValidationError):
            self._yeni(guc="sebeke,sebeke").full_clean()

    def test_guc_bicimi(self):
        with self.assertRaises(ValidationError):
            self._yeni(guc="Sebeke; jenerator").full_clean()


class BaglantiTestleri(SenaryolarYuklu):
    def setUp(self):
        self.c = {c.ad: c for c in models.Cihaz.objects.filter(senaryo__slug="ofis")}
        self.ofis = models.Senaryo.objects.get(slug="ofis")

    def test_kendine_baglanti_olmaz(self):
        with self.assertRaises(ValidationError):
            models.Baglanti(senaryo=self.ofis, kaynak=self.c["core_1"], hedef=self.c["core_1"]).full_clean()

    def test_baska_senaryonun_cihazina_baglanti_olmaz(self):
        yabanci = models.Cihaz.objects.filter(senaryo__slug="hastane").first()
        with self.assertRaises(ValidationError):
            models.Baglanti(senaryo=self.ofis, kaynak=self.c["core_1"], hedef=yabanci).full_clean()

    def test_ters_yonde_tekrar_olmaz(self):
        b = models.Baglanti.objects.filter(senaryo=self.ofis).first()
        with self.assertRaises(ValidationError):
            models.Baglanti(senaryo=self.ofis, kaynak=b.hedef, hedef=b.kaynak).full_clean()

    def test_ayni_yonde_tekrar_veritabaninda_reddedilir(self):
        b = models.Baglanti.objects.filter(senaryo=self.ofis).first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Baglanti.objects.create(senaryo=self.ofis, kaynak=b.kaynak, hedef=b.hedef)


class KuralTestleri(SenaryolarYuklu):
    def setUp(self):
        self.ofis = models.Senaryo.objects.get(slug="ofis")

    def test_port_bicimi_ve_araligi(self):
        for portlar in ("80;443", "abc", "70000", "0"):
            with self.subTest(portlar=portlar), self.assertRaises(ValidationError):
                models.Kural(senaryo=self.ofis, kaynak_bolge="a", hedef_bolge="b", portlar=portlar).full_clean()

    def test_bos_port_tum_portlar(self):
        k = models.Kural(senaryo=self.ofis, kaynak_bolge="a", hedef_bolge="b", portlar="")
        k.full_clean()
        self.assertIsNone(k.port_kumesi)

    def test_yildiz_bolge_kabul_edilir(self):
        models.Kural(senaryo=self.ofis, kaynak_bolge="*", hedef_bolge="b").full_clean()

    def test_engel_port_araligi(self):
        with self.assertRaises(ValidationError):
            models.Engel(senaryo=self.ofis, kaynak_bolge="a", hedef_bolge="b", port=70000, aciklama="x").full_clean()


class SorunlarTestleri(SenaryolarYuklu):
    def test_bagsiz_cihaz_ve_olmayan_bolge_bildirilir(self):
        ofis = models.Senaryo.objects.get(slug="ofis")
        models.Cihaz.objects.create(senaryo=ofis, ad="yalniz_1", tur="switch")
        models.Kural.objects.create(senaryo=ofis, kaynak_bolge="olmayan", hedef_bolge="*")
        metin = " ".join(ofis.sorunlar())
        self.assertIn("yalniz_1", metin)
        self.assertIn("olmayan", metin)

    def test_olmayan_izleme_dugumu_bildirilir(self):
        ofis = models.Senaryo.objects.get(slug="ofis")
        ofis.izleme_dugumu = "yok_boyle"
        self.assertTrue(any("yok_boyle" in s for s in ofis.sorunlar()))

    def test_bos_senaryo(self):
        bos = models.Senaryo.objects.create(slug="bos", baslik="Boş")
        self.assertEqual(len(bos.sorunlar()), 1)
