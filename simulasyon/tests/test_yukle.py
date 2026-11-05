"""Veritabanı <-> motor dönüşümü: veritabanından gelen senaryo, kodla yazılanla aynı sonucu vermeli."""
from io import StringIO

from django.core.management import call_command

from ag_motoru import erisim_matrisi, hata_simulasyonu, mermaid_uret
from ag_motoru.ag_modelleri import senaryo_al

from .. import models
from ..yukle import ice_aktar, senaryo_yukle
from .yardimci import SENARYOLAR, SenaryolarYuklu


def _kablolar(es):
    return {frozenset(e) for e in es.graf.edges}


def _dugumler(es):
    return {n: dict(d) for n, d in es.graf.nodes(data=True)}


class GidisDonusTestleri(SenaryolarYuklu):
    def test_dort_senaryo_yuklenir(self):
        self.assertEqual(set(models.Senaryo.objects.values_list("slug", flat=True)), set(SENARYOLAR))

    def test_veritabani_senaryosu_kodla_yazilanla_ayni(self):
        for ad in SENARYOLAR:
            with self.subTest(ad=ad):
                kod = senaryo_al(ad)
                db = senaryo_yukle(models.Senaryo.objects.get(slug=ad))
                self.assertEqual(_dugumler(db), _dugumler(kod))
                self.assertEqual(_kablolar(db), _kablolar(kod))
                self.assertEqual(db.gereksinimler, kod.gereksinimler)
                self.assertEqual(db.kurallar, kod.kurallar)
                self.assertEqual(db.engeller, kod.engeller)
                self.assertEqual(db.izleme_dugumu, kod.izleme_dugumu)

    def test_analiz_ve_diyagram_ayni(self):
        for ad in SENARYOLAR:
            with self.subTest(ad=ad):
                kod = senaryo_al(ad)
                db = senaryo_yukle(models.Senaryo.objects.get(slug=ad))
                a, b = hata_simulasyonu.tek_hata_analizi(kod), hata_simulasyonu.tek_hata_analizi(db)
                self.assertEqual(a["kontrol"], b["kontrol"])
                self.assertEqual([x["eleman"] for x in a["spof"]], [x["eleman"] for x in b["spof"]])
                self.assertEqual([x["eleman"] for x in a["yerel"]], [x["eleman"] for x in b["yerel"]])
                self.assertEqual(mermaid_uret.mermaid(kod), mermaid_uret.mermaid(db))
                self.assertEqual(erisim_matrisi.matris(kod), erisim_matrisi.matris(db))

    def test_senaryolarda_tutarsizlik_yok(self):
        for s in models.Senaryo.objects.all():
            with self.subTest(slug=s.slug):
                self.assertEqual(s.sorunlar(), [])

    def test_bilinen_sayilar(self):
        beklenen = {"ofis": (24, 23, 9, 8), "eticaret": (29, 46, 0, 4),
                    "universite": (24, 23, 9, 8), "hastane": (34, 56, 0, 6)}
        for ad, (dugum, kablo, spof, yerel) in beklenen.items():
            with self.subTest(ad=ad):
                es = senaryo_yukle(models.Senaryo.objects.get(slug=ad))
                a = hata_simulasyonu.tek_hata_analizi(es)
                self.assertEqual((es.graf.number_of_nodes(), es.graf.number_of_edges(),
                                  len(a["spof"]), len(a["yerel"])), (dugum, kablo, spof, yerel))


class SeedTestleri(SenaryolarYuklu):
    def test_ikinci_calistirma_bir_sey_degistirmez(self):
        sayi = models.Cihaz.objects.count()
        cikti = StringIO()
        call_command("seed_senaryolar", stdout=cikti)
        self.assertEqual(models.Cihaz.objects.count(), sayi)
        self.assertIn("zaten var", cikti.getvalue())

    def test_elle_yapilan_degisiklik_korunur(self):
        models.Cihaz.objects.filter(senaryo__slug="ofis", ad="pc_k1").update(etiket="Benim bilgisayarım")
        call_command("seed_senaryolar", stdout=StringIO())
        self.assertEqual(models.Cihaz.objects.get(senaryo__slug="ofis", ad="pc_k1").etiket, "Benim bilgisayarım")

    def test_yenile_degisiklikleri_sifirlar_ama_gecmisi_korur(self):
        ofis = models.Senaryo.objects.get(slug="ofis")
        models.Cihaz.objects.filter(senaryo=ofis, ad="pc_k1").update(etiket="Benim bilgisayarım")
        kayit = models.Simulasyon.objects.create(kullanici=self.ali, senaryo=ofis, tur="hata", ozet="x")
        call_command("seed_senaryolar", "ofis", "--yenile", stdout=StringIO())
        self.assertNotEqual(models.Cihaz.objects.get(senaryo__slug="ofis", ad="pc_k1").etiket, "Benim bilgisayarım")
        self.assertTrue(models.Simulasyon.objects.filter(pk=kayit.pk).exists())
        self.assertEqual(models.Senaryo.objects.get(slug="ofis").pk, ofis.pk)

    def test_ice_aktar_yeni_senaryo_yazar(self):
        models.Senaryo.objects.filter(slug="hastane").delete()
        _, yazildi = ice_aktar(senaryo_al("hastane"))
        self.assertTrue(yazildi)
        self.assertEqual(models.Cihaz.objects.filter(senaryo__slug="hastane").count(), 34)
