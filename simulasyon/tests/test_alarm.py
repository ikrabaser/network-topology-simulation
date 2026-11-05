"""Alarm akışı: web sayfası, geçmişe kayıt, arıza geçmişi ve API."""
from django.urls import reverse
from rest_framework.test import APIClient

from .. import models, servis
from .yardimci import SENARYOLAR, SenaryolarYuklu

DESEN = "0111110111"
FORM = {"bozuk": ["core_1"], "desen": DESEN, "deneme": "3", "pencere": "10", "esik": "3", "aralik": "60"}


class IzlemeKokNedenTestleri(SenaryolarYuklu):
    def test_izleme_sayfasi_kok_nedeni_ve_bastirilani_gosterir(self):
        r = self.client.get(reverse("izleme", args=["ofis"]), {"bozuk": ["core_1"]})
        self.assertContains(r, "1 kök neden")
        self.assertContains(r, "21 alarm bastırıldı")
        self.assertContains(r, "core_1 arkasında")

    def test_saglam_agda_kok_neden_yok(self):
        r = self.client.get(reverse("izleme", args=["ofis"]))
        self.assertNotContains(r, "kök neden")

    def test_izleme_dugumu_kapaliysa_uyarir(self):
        r = self.client.get(reverse("izleme", args=["ofis"]), {"bozuk": ["zabbix"]})
        self.assertContains(r, "İzleme düğümü kapalı")


class ZamanSayfasiTestleri(SenaryolarYuklu):
    def test_tum_senaryolarda_acilir(self):
        for ad in SENARYOLAR:
            with self.subTest(ad=ad):
                self.assertEqual(self.client.get(reverse("zaman", args=[ad])).status_code, 200)

    def test_bilinmeyen_senaryo_404(self):
        self.assertEqual(self.client.get(reverse("zaman", args=["yok"])).status_code, 404)

    def test_sonuc_gosterilir(self):
        r = self.client.get(reverse("zaman", args=["ofis"]), {k: v for k, v in FORM.items()})
        self.assertContains(r, "44 ham alarm")
        self.assertContains(r, "3 bildirim")
        self.assertContains(r, "DALGALANMA")
        self.assertContains(r, "kök neden")

    def test_sonuc_yokken_ornek_desenler_gorunur(self):
        r = self.client.get(reverse("zaman", args=["ofis"]))
        self.assertContains(r, "0101010101")
        self.assertNotContains(r, "ham alarm")

    def test_gecersiz_girdi_mesaji(self):
        url = reverse("zaman", args=["ofis"])
        self.assertContains(self.client.get(url, {"bozuk": ["core_1"], "desen": "01a"}), "0 ve 1")
        self.assertContains(self.client.get(url, {"desen": "0110"}), "en az bir eleman")
        self.assertContains(self.client.get(url, {**FORM, "deneme": "0"}), "deneme")
        self.assertContains(self.client.get(url, {**FORM, "deneme": "abc"}), "tam sayı")
        self.assertContains(self.client.get(url, {**FORM, "esik": "99"}), "esik")

    def test_bilinmeyen_eleman_yoksayilir(self):
        r = self.client.get(reverse("zaman", args=["ofis"]), {"bozuk": ["yok_boyle"], "desen": "0110"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "en az bir eleman")

    def test_kaydet_dugmesi_sadece_girisli_kullanicida(self):
        url = reverse("zaman", args=["ofis"])
        self.assertNotContains(self.client.get(url, FORM), "Geçmişe kaydet")
        self.client.force_login(self.ali)
        self.assertContains(self.client.get(url, FORM), "Geçmişe kaydet")


class ArizaKayitTestleri(SenaryolarYuklu):
    def _kaydet(self, kullanici=None, **degisim):
        self.client.force_login(kullanici or self.ali)
        return self.client.post(reverse("kaydet", args=["ofis", "zaman"]), {**FORM, **degisim})

    def test_kayit_simulasyon_ve_onayli_arizalari_yazar(self):
        r = self._kaydet()
        k = models.Simulasyon.objects.get(tur="zaman")
        self.assertRedirects(r, reverse("gecmis_detay", args=[k.pk]))
        self.assertEqual(k.girdi["desen"], DESEN)
        self.assertEqual(models.Ariza.objects.filter(simulasyon=k).count(), 44)
        self.assertEqual(models.Ariza.objects.filter(kok_neden=True).count(), 2)
        self.assertEqual(set(models.Ariza.objects.filter(kok_neden=True).values_list("cihaz", flat=True)), {"core_1"})

    def test_gecici_kesintiler_arizaya_yazilmaz(self):
        self._kaydet(desen="0110000000")
        self.assertEqual(models.Simulasyon.objects.filter(tur="zaman").count(), 1)
        self.assertEqual(models.Ariza.objects.count(), 0)

    def test_sonuc_sunucuda_hesaplanir(self):
        self._kaydet(ozet="uydurma", sonuc="uydurma", olaylar="uydurma")
        k = models.Simulasyon.objects.get(tur="zaman")
        self.assertEqual(k.sonuc["ozet"]["ham_alarm"], 44)

    def test_gecersiz_girdi_kayit_olusturmaz(self):
        for degisim in ({"desen": "01x"}, {"bozuk": ["yok_boyle"]}, {"deneme": "0"}, {"desen": ""}):
            with self.subTest(degisim=degisim):
                self._kaydet(**degisim)
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_girissiz_kayit_olmaz(self):
        self.client.post(reverse("kaydet", args=["ofis", "zaman"]), FORM)
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_gecmis_detayi_alarm_akisini_gosterir(self):
        self._kaydet()
        k = models.Simulasyon.objects.get()
        r = self.client.get(reverse("gecmis_detay", args=[k.pk]))
        self.assertContains(r, "44 ham alarm")
        self.assertContains(r, DESEN)

    def test_simulasyon_silinince_arizalari_da_silinir(self):
        self._kaydet()
        k = models.Simulasyon.objects.get()
        self.client.post(reverse("gecmis_sil", args=[k.pk]))
        self.assertEqual(models.Ariza.objects.count(), 0)

    def test_ariza_sayfasi_girissiz_giris_ister(self):
        self.assertEqual(self.client.get(reverse("ariza")).status_code, 302)

    def test_ariza_sayfasi_yalniz_kendi_kayitlarini_gosterir(self):
        self._kaydet(self.ali)
        self.assertContains(self.client.get(reverse("ariza")), "core_1")
        self.client.force_login(self.veli)
        r = self.client.get(reverse("ariza"))
        self.assertNotContains(r, "core_1")
        self.assertContains(r, "Henüz arıza kaydı yok")

    def test_iki_kullanici_birbirinin_olaylarini_gormez(self):
        self._kaydet(self.ali)  # ofis: core_1 ve 21 belirti (kamera_k3 ...)
        self.client.force_login(self.veli)
        # veli'nin tek olayı (hastanede tek core düşünce yalnız core_1): sayfaya sığdığı için sızıntı görünür olur
        self.client.post(reverse("kaydet", args=["hastane", "zaman"]),
                         {**FORM, "bozuk": ["core_1"], "desen": "0011100"})
        r = self.client.get(reverse("ariza"), {"belirti": "1"})
        self.assertContains(r, "hastane")
        self.assertNotContains(r, "kamera_k3")
        self.assertNotContains(r, "ofis")
        self.client.force_login(self.ali)
        r = self.client.get(reverse("ariza"), {"belirti": "1"})
        self.assertContains(r, "kamera_k3")
        self.assertNotContains(r, "hastane")

    def test_belirtiler_varsayilan_gizli_istenince_gorunur(self):
        self._kaydet()
        self.assertNotContains(self.client.get(reverse("ariza")), "fw_1")
        self.assertContains(self.client.get(reverse("ariza"), {"belirti": "1"}), "fw_1")

    def test_senaryo_filtresi(self):
        self._kaydet()
        self.assertContains(self.client.get(reverse("ariza"), {"senaryo": "ofis"}), "core_1")
        bos = self.client.get(reverse("ariza"), {"senaryo": "hastane"})
        self.assertNotContains(bos, "core_1")
        self.assertContains(bos, "Henüz arıza kaydı yok")

    def test_ariza_ozeti_sayilari(self):
        self._kaydet()
        self._kaydet()
        o = servis.ariza_ozeti(self.ali)
        self.assertEqual((o["olay"], o["cihaz"]), (4, 1))
        c = o["cihazlar"][0]
        self.assertEqual((c["cihaz"], c["sayi"], c["acik"], c["dalgali"]), ("core_1", 4, 2, 2))
        # her çalıştırmada biri kapanan (5 kontrol = 300 sn), biri açık (3 kontrol = 180 sn) olay
        self.assertEqual((c["toplam_sn"], c["ortalama_onarim_sn"]), (960, 300))

    def test_ariza_ozeti_belirtilerle(self):
        self._kaydet()
        o = servis.ariza_ozeti(self.ali, belirtiler=True)
        self.assertEqual((o["olay"], o["cihaz"]), (44, 22))


class ZamanApiTestleri(SenaryolarYuklu):
    def setUp(self):
        self.c = APIClient()

    def _json(self, **degisim):
        return {"bozuk": ["core_1"], "desen": DESEN, **degisim}

    def test_get_hesaplar(self):
        r = self.c.get("/api/senaryolar/ofis/zaman/", {"bozuk": ["core_1"], "desen": DESEN})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["ozet"]["ham_alarm"], 44)
        self.assertEqual([b["tur"] for b in r.data["bildirimler"]], ["ALARM", "KURTARMA", "DALGALANMA"])

    def test_ayarlar_uygulanir(self):
        r = self.c.get("/api/senaryolar/ofis/zaman/", {"bozuk": ["core_1"], "desen": "0110000000", "deneme": 2})
        self.assertEqual(r.data["ozet"]["onayli_alarm"], 22)

    def test_girdi_dogrulanir(self):
        for sorgu in ({"desen": DESEN}, {"bozuk": ["core_1"]}, {"bozuk": ["yok"], "desen": DESEN},
                      {"bozuk": ["core_1"], "desen": "012"}, {"bozuk": ["core_1"], "desen": DESEN, "deneme": 0},
                      {"bozuk": ["core_1"], "desen": DESEN, "pencere": "x"},
                      {"bozuk": ["core_1"], "desen": DESEN, "esik": 50}):
            with self.subTest(sorgu=sorgu):
                self.assertEqual(self.c.get("/api/senaryolar/ofis/zaman/", sorgu).status_code, 400)

    def test_girissiz_post_reddedilir(self):
        r = self.c.post("/api/senaryolar/ofis/zaman/", self._json(), format="json")
        self.assertIn(r.status_code, (401, 403))
        self.assertEqual(models.Ariza.objects.count(), 0)

    def test_post_kaydeder(self):
        self.c.force_authenticate(self.ali)
        r = self.c.post("/api/senaryolar/ofis/zaman/", self._json(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(models.Ariza.objects.filter(simulasyon_id=r.data["kayit_id"]).count(), 44)

    def test_post_girdi_hatasi_kayit_olusturmaz(self):
        self.c.force_authenticate(self.ali)
        for veri in ({"bozuk": ["core_1"], "desen": 5}, {"bozuk": [1], "desen": DESEN}, {}, [1],
                     self._json(deneme=True), self._json(deneme="3; drop")):
            with self.subTest(veri=str(veri)[:30]):
                self.assertEqual(self.c.post("/api/senaryolar/ofis/zaman/", veri, format="json").status_code, 400)
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_izleme_yanitinda_kok_neden(self):
        r = self.c.get("/api/senaryolar/ofis/izleme/", {"bozuk": ["core_1"]})
        self.assertEqual(r.data["kok_neden"], {"kokler": ["core_1"], "bastirilan": 21, "izleme_kapali": False})
        roller = {d["ad"]: d["alarm"] for d in r.data["durumlar"]}
        self.assertEqual((roller["core_1"], roller["fw_1"]), ("kok", "bastirilan"))


class ArizaApiTestleri(SenaryolarYuklu):
    def setUp(self):
        self.ali_c, self.veli_c = APIClient(), APIClient()
        self.ali_c.force_authenticate(self.ali)
        self.veli_c.force_authenticate(self.veli)
        self.ali_c.post("/api/senaryolar/ofis/zaman/", {"bozuk": ["core_1"], "desen": DESEN}, format="json")
        self.ali_c.post("/api/senaryolar/hastane/zaman/", {"bozuk": ["core_1", "core_2"], "desen": "0011100"}, format="json")

    def test_girissiz_reddedilir(self):
        for yol in ("/api/ariza/", "/api/ariza/ozet/"):
            self.assertIn(APIClient().get(yol).status_code, (401, 403))

    def test_liste_varsayilan_kok_nedenler(self):
        r = self.ali_c.get("/api/ariza/")
        self.assertTrue(r.data)
        self.assertTrue(all(x["kok_neden"] for x in r.data))
        self.assertEqual({x["senaryo"] for x in r.data}, {"ofis", "hastane"})

    def test_filtreler(self):
        self.assertEqual({x["senaryo"] for x in self.ali_c.get("/api/ariza/", {"senaryo": "ofis"}).data}, {"ofis"})
        self.assertEqual({x["cihaz"] for x in self.ali_c.get("/api/ariza/", {"cihaz": "core_2"}).data}, {"core_2"})
        self.assertTrue(all(x["acik"] for x in self.ali_c.get("/api/ariza/", {"acik": "1"}).data))
        self.assertGreater(len(self.ali_c.get("/api/ariza/", {"belirti": "1"}).data),
                           len(self.ali_c.get("/api/ariza/").data))

    def test_baskasinin_kayitlari_gorunmez(self):
        self.assertEqual(self.veli_c.get("/api/ariza/").data, [])
        self.assertEqual(self.veli_c.get("/api/ariza/ozet/").data["olay"], 0)

    def test_ozet(self):
        r = self.ali_c.get("/api/ariza/ozet/")
        self.assertEqual(r.status_code, 200)
        cihazlar = {(x["senaryo"], x["cihaz"]): x for x in r.data["cihazlar"]}
        self.assertEqual(cihazlar[("ofis", "core_1")]["sayi"], 2)
        self.assertEqual(cihazlar[("hastane", "core_2")]["sayi"], 1)
        self.assertEqual(self.ali_c.get("/api/ariza/ozet/", {"senaryo": "ofis"}).data["olay"], 2)
        self.assertEqual(self.ali_c.get("/api/ariza/ozet/", {"senaryo": "yok"}).status_code, 404)
