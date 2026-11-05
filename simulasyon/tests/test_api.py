"""REST API: okuma herkese açık, kaydetme/SIEM/geçmiş giriş ister, geçmiş kullanıcıya özeldir."""
import base64

from rest_framework.test import APIClient

from .. import models
from .yardimci import PAROLA, SENARYOLAR, SenaryolarYuklu


class OkumaTestleri(SenaryolarYuklu):
    def setUp(self):
        self.c = APIClient()

    def test_kok(self):
        r = self.c.get("/api/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("senaryolar", r.data)

    def test_senaryo_listesi(self):
        r = self.c.get("/api/senaryolar/")
        self.assertEqual([x["slug"] for x in r.data], list(SENARYOLAR))
        hastane = next(x for x in r.data if x["slug"] == "hastane")
        self.assertEqual((hastane["dugum"], hastane["kablo"], hastane["spof"]), (34, 56, 0))

    def test_senaryo_detayi(self):
        r = self.c.get("/api/senaryolar/ofis/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["cihazlar"]), 24)
        self.assertEqual(len(r.data["kablolar"]), 23)
        self.assertEqual(r.data["sorunlar"], [])

    def test_analiz(self):
        r = self.c.get("/api/senaryolar/ofis/analiz/")
        self.assertEqual(r.data["kontrol"], 42)
        self.assertEqual(len(r.data["spof"]), 9)
        self.assertEqual(len(r.data["yerel"]), 8)

    def test_diyagram(self):
        self.assertTrue(self.c.get("/api/senaryolar/ofis/diyagram/").data["mermaid"].startswith("flowchart TB"))

    def test_bilinmeyen_senaryo_404(self):
        for yol in ("", "analiz/", "diyagram/", "hata/", "izleme/", "erisim/"):
            with self.subTest(yol=yol):
                self.assertEqual(self.c.get(f"/api/senaryolar/yok/{yol}").status_code, 404)

    def test_hata_hesabi(self):
        r = self.c.get("/api/senaryolar/hastane/hata/", {"bozuk": ["core_1"]})
        self.assertEqual(r.data["kopan"], [])
        r = self.c.get("/api/senaryolar/hastane/hata/", {"bozuk": ["core_1", "core_2"]})
        self.assertEqual(len(r.data["kopan"]), 8)

    def test_hata_girdisi_dogrulanir(self):
        self.assertEqual(self.c.get("/api/senaryolar/hastane/hata/").status_code, 400)
        r = self.c.get("/api/senaryolar/hastane/hata/", {"bozuk": ["yok_boyle"]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("yok_boyle", str(r.data))

    def test_izleme(self):
        r = self.c.get("/api/senaryolar/ofis/izleme/", {"bozuk": ["core_1"]})
        self.assertEqual((r.data["up"], r.data["toplam"]), (0, 22))
        self.assertTrue(r.data["alarmlar"])
        self.assertEqual(self.c.get("/api/senaryolar/ofis/izleme/").data["up"], 22)

    def test_erisim_matrisi_ve_sorgu(self):
        self.assertIn("dmz", self.c.get("/api/senaryolar/universite/erisim/").data["zonlar"])
        engel = self.c.get("/api/senaryolar/universite/erisim/",
                           {"kaynak": "ogrenci_cihazi", "hedef": "ogrenci_isleri_db", "port": 3306})
        self.assertFalse(engel.data["sonuc"])
        self.assertTrue(engel.data["fiziksel_yol"])
        izin = self.c.get("/api/senaryolar/universite/erisim/",
                          {"kaynak": "ogrenci_isleri_pc", "hedef": "ogrenci_isleri_db", "port": 3306})
        self.assertTrue(izin.data["sonuc"])

    def test_erisim_girdisi_dogrulanir(self):
        for sorgu in ({"kaynak": "x", "hedef": "y"}, {"kaynak": "pc_k1"},
                      {"kaynak": "pc_k1", "hedef": "ad", "port": "abc"},
                      {"kaynak": "pc_k1", "hedef": "ad", "port": 0}):
            with self.subTest(sorgu=sorgu):
                self.assertEqual(self.c.get("/api/senaryolar/ofis/erisim/", sorgu).status_code, 400)


class YazmaVeYetkiTestleri(SenaryolarYuklu):
    def setUp(self):
        self.c = APIClient()

    def test_girissiz_kaydetme_ve_siem_ve_gecmis_reddedilir(self):
        self.assertIn(self.c.post("/api/senaryolar/hastane/hata/", {"bozuk": ["core_1"]}, format="json").status_code, (401, 403))
        self.assertIn(self.c.post("/api/siem/", {"log": "x"}, format="json").status_code, (401, 403))
        self.assertIn(self.c.get("/api/gecmis/").status_code, (401, 403))
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_basic_auth_ile_kaydetme(self):
        kimlik = base64.b64encode(f"ali:{PAROLA}".encode()).decode()
        r = self.c.post("/api/senaryolar/hastane/hata/", {"bozuk": ["core_1", "core_2"]}, format="json",
                        HTTP_AUTHORIZATION=f"Basic {kimlik}")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(models.Simulasyon.objects.get(pk=r.data["kayit_id"]).kullanici, self.ali)

    def test_yanlis_basic_parola(self):
        kimlik = base64.b64encode(b"ali:yanlis").decode()
        r = self.c.post("/api/senaryolar/hastane/hata/", {"bozuk": ["core_1"]}, format="json",
                        HTTP_AUTHORIZATION=f"Basic {kimlik}")
        self.assertIn(r.status_code, (401, 403))

    def test_hata_kaydi_sunucuda_hesaplanir(self):
        self.c.force_authenticate(self.ali)
        r = self.c.post("/api/senaryolar/hastane/hata/",
                        {"bozuk": ["core_1", "core_2"], "kopan": [], "sonuc": "uydurma"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data["kopan"]), 8)
        k = models.Simulasyon.objects.get(pk=r.data["kayit_id"])
        self.assertEqual(len(k.sonuc["kopan"]), 8)

    def test_yanlis_girdi_kayit_olusturmaz(self):
        self.c.force_authenticate(self.ali)
        for veri in ({"bozuk": ["yok_boyle"]}, {"bozuk": []}, {"bozuk": [1, 2]}, {}, [1, 2]):
            with self.subTest(veri=veri):
                self.assertEqual(self.c.post("/api/senaryolar/hastane/hata/", veri, format="json").status_code, 400)
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_izleme_ve_erisim_kaydi(self):
        self.c.force_authenticate(self.ali)
        self.assertEqual(self.c.post("/api/senaryolar/ofis/izleme/", {"bozuk": ["core_1"]}, format="json").status_code, 201)
        r = self.c.post("/api/senaryolar/universite/erisim/",
                        {"kaynak": "ogrenci_cihazi", "hedef": "ogrenci_isleri_db", "port": 3306}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["sonuc"])

    def test_siem(self):
        self.c.force_authenticate(self.ali)
        log = "\n".join(f"2026-11-05T14:00:0{i} fw_1 AUTH FAIL user=ali src=203.0.113.9" for i in range(6))
        r = self.c.post("/api/siem/", {"log": log, "kaynak": "deneme"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("BRUTE_FORCE", [a["kural"] for a in r.data["alarmlar"]])
        self.assertEqual(r.data["kaynak"], "deneme")

    def test_siem_girdi_denetimi(self):
        self.c.force_authenticate(self.ali)
        for veri in ({}, {"log": ""}, {"log": 5}, {"log": "x" * 1_100_000}, [1]):
            with self.subTest(veri=str(veri)[:20]):
                self.assertEqual(self.c.post("/api/siem/", veri, format="json").status_code, 400)


class GecmisTestleri(SenaryolarYuklu):
    def setUp(self):
        self.ali_c, self.veli_c = APIClient(), APIClient()
        self.ali_c.force_authenticate(self.ali)
        self.veli_c.force_authenticate(self.veli)
        self.kayit = self.ali_c.post("/api/senaryolar/hastane/hata/", {"bozuk": ["core_1"]}, format="json").data["kayit_id"]
        self.ali_c.post("/api/senaryolar/ofis/izleme/", {}, format="json")

    def test_kullanici_kendi_kayitlarini_gorur(self):
        r = self.ali_c.get("/api/gecmis/")
        self.assertEqual(len(r.data), 2)
        self.assertEqual({x["tur"] for x in r.data}, {"hata", "izleme"})
        self.assertEqual(r.data[0]["senaryo"], "ofis")  # en yeni başta

    def test_filtre(self):
        self.assertEqual(len(self.ali_c.get("/api/gecmis/", {"tur": "hata"}).data), 1)

    def test_baskasinin_kaydi_gorunmez_ve_silinemez(self):
        self.assertEqual(self.veli_c.get("/api/gecmis/").data, [])
        self.assertEqual(self.veli_c.get(f"/api/gecmis/{self.kayit}/").status_code, 404)
        self.assertEqual(self.veli_c.delete(f"/api/gecmis/{self.kayit}/").status_code, 404)
        self.assertTrue(models.Simulasyon.objects.filter(pk=self.kayit).exists())

    def test_detay_ve_silme(self):
        r = self.ali_c.get(f"/api/gecmis/{self.kayit}/")
        self.assertEqual(r.data["girdi"], {"bozuk": ["core_1"]})
        self.assertEqual(self.ali_c.delete(f"/api/gecmis/{self.kayit}/").status_code, 204)
        self.assertFalse(models.Simulasyon.objects.filter(pk=self.kayit).exists())

    def test_gecmis_salt_okunur_degil_degistirilemez(self):
        self.assertEqual(self.ali_c.put(f"/api/gecmis/{self.kayit}/", {"ozet": "x"}, format="json").status_code, 405)
        self.assertEqual(self.ali_c.post("/api/gecmis/", {"ozet": "x"}, format="json").status_code, 405)
