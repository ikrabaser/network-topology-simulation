"""Giriş, kayıt ve geçmiş: her kullanıcı yalnızca kendi kayıtlarını görür."""
from django.contrib.auth.models import User
from django.urls import reverse

from .. import models
from .yardimci import PAROLA, SenaryolarYuklu


class HesapTestleri(SenaryolarYuklu):
    def test_giris(self):
        r = self.client.post(reverse("giris"), {"username": "ali", "password": PAROLA})
        self.assertRedirects(r, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "ali")

    def test_yanlis_parola(self):
        r = self.client.post(reverse("giris"), {"username": "ali", "password": "yanlis"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_kayit_olur_ve_giris_yapar(self):
        r = self.client.post(reverse("kayit"), {"username": "yeni", "password1": PAROLA, "password2": PAROLA})
        self.assertRedirects(r, reverse("index"))
        self.assertTrue(User.objects.filter(username="yeni").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_kayitta_zayif_parola_reddedilir(self):
        r = self.client.post(reverse("kayit"), {"username": "yeni", "password1": "12345678", "password2": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="yeni").exists())

    def test_cikis_sadece_post(self):
        self.client.force_login(self.ali)
        self.assertEqual(self.client.get(reverse("cikis")).status_code, 405)
        self.client.post(reverse("cikis"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_girise_yonlendirmede_dis_adres_kabul_edilmez(self):
        r = self.client.post(reverse("giris") + "?next=https://kotu.example/",
                             {"username": "ali", "password": PAROLA})
        self.assertRedirects(r, reverse("index"))


class GecmisTestleri(SenaryolarYuklu):
    def _kaydet(self, kullanici, **veri):
        self.client.force_login(kullanici)
        return self.client.post(reverse("kaydet", args=["hastane", "hata"]), veri or {"bozuk": ["core_1", "core_2"]})

    def test_girissiz_gecmis_giris_ister(self):
        r = self.client.get(reverse("gecmis"))
        self.assertRedirects(r, reverse("giris") + "?next=" + reverse("gecmis"))

    def test_girissiz_kaydetme_olmaz(self):
        r = self.client.post(reverse("kaydet", args=["hastane", "hata"]), {"bozuk": ["core_1"]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_kaydetme_get_ile_olmaz(self):
        self.client.force_login(self.ali)
        self.assertEqual(self.client.get(reverse("kaydet", args=["hastane", "hata"])).status_code, 405)

    def test_hata_kaydi_sunucuda_yeniden_hesaplanir(self):
        r = self._kaydet(self.ali, bozuk=["core_1", "core_2"], kopan="uydurma", sonuc="uydurma")
        k = models.Simulasyon.objects.get(kullanici=self.ali)
        self.assertRedirects(r, reverse("gecmis_detay", args=[k.pk]))
        self.assertEqual(k.girdi, {"bozuk": ["core_1", "core_2"]})
        self.assertGreater(len(k.sonuc["kopan"]), 0)
        self.assertEqual(k.senaryo.slug, "hastane")
        self.assertIn("gereksinim koptu", k.ozet)

    def test_bos_hata_kaydi_olusmaz(self):
        self.client.force_login(self.ali)
        self.client.post(reverse("kaydet", args=["hastane", "hata"]), {"bozuk": ["yok_boyle"]})
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_izleme_ve_erisim_kaydi(self):
        self.client.force_login(self.ali)
        self.client.post(reverse("kaydet", args=["ofis", "izleme"]), {"bozuk": ["core_1"]})
        self.client.post(reverse("kaydet", args=["universite", "erisim"]),
                         {"kaynak": "ogrenci_cihazi", "hedef": "ogrenci_isleri_db", "port": "3306"})
        self.assertEqual(set(models.Simulasyon.objects.values_list("tur", flat=True)), {"izleme", "erisim"})
        erisim = models.Simulasyon.objects.get(tur="erisim")
        self.assertFalse(erisim.sonuc["sonuc"])
        self.assertIn("ENGEL", erisim.ozet)

    def test_gecersiz_erisim_kaydi_olusmaz(self):
        self.client.force_login(self.ali)
        self.client.post(reverse("kaydet", args=["ofis", "erisim"]), {"kaynak": "x", "hedef": "y"})
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_bilinmeyen_tur_404(self):
        self.client.force_login(self.ali)
        self.assertEqual(self.client.post(reverse("kaydet", args=["ofis", "siem"])).status_code, 404)

    def test_baska_kullanicinin_kaydi_gorunmez(self):
        self._kaydet(self.ali)
        k = models.Simulasyon.objects.get()
        self.client.force_login(self.veli)
        self.assertEqual(self.client.get(reverse("gecmis_detay", args=[k.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("gecmis_sil", args=[k.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("gecmis")), "core_1")
        self.assertTrue(models.Simulasyon.objects.filter(pk=k.pk).exists())

    def test_liste_detay_ve_silme(self):
        self._kaydet(self.ali)
        k = models.Simulasyon.objects.get()
        self.assertContains(self.client.get(reverse("gecmis")), "core_1")
        self.assertContains(self.client.get(reverse("gecmis_detay", args=[k.pk])), "gereksinim koptu")
        self.assertEqual(self.client.get(reverse("gecmis_sil", args=[k.pk])).status_code, 405)
        self.client.post(reverse("gecmis_sil", args=[k.pk]))
        self.assertFalse(models.Simulasyon.objects.exists())

    def test_tur_filtresi(self):
        self._kaydet(self.ali)
        self.client.post(reverse("kaydet", args=["ofis", "izleme"]), {})
        self.assertContains(self.client.get(reverse("gecmis"), {"tur": "izleme"}), "cihaz UP")
        self.assertNotContains(self.client.get(reverse("gecmis"), {"tur": "izleme"}), "core_1, core_2")

    def test_senaryo_silinince_kayit_da_silinir(self):
        self._kaydet(self.ali)
        models.Senaryo.objects.get(slug="hastane").delete()
        self.assertFalse(models.Simulasyon.objects.exists())
