"""Web sayfaları (veritabanındaki senaryolarla)."""
from django.urls import reverse

from .yardimci import SENARYOLAR, SenaryolarYuklu


class SayfaTestleri(SenaryolarYuklu):
    def test_ana_sayfa_dort_senaryoyu_listeler(self):
        r = self.client.get(reverse("index"))
        self.assertEqual(r.status_code, 200)
        for ad in SENARYOLAR:
            self.assertContains(r, reverse("senaryo", args=[ad]))

    def test_tum_senaryo_sayfalari_acilir(self):
        for ad in SENARYOLAR:
            for sayfa in ("senaryo", "hata", "erisim", "izleme"):
                with self.subTest(ad=ad, sayfa=sayfa):
                    self.assertEqual(self.client.get(reverse(sayfa, args=[ad])).status_code, 200)

    def test_bilinmeyen_senaryo_404(self):
        for sayfa in ("senaryo", "hata", "erisim", "izleme"):
            with self.subTest(sayfa=sayfa):
                self.assertEqual(self.client.get(reverse(sayfa, args=["yok"])).status_code, 404)

    def test_diyagram_mermaid_icerir(self):
        r = self.client.get(reverse("senaryo", args=["hastane"]))
        self.assertContains(r, "flowchart TB")
        self.assertContains(r, "core_1")

    def test_ofiste_merkezi_spof_gosterilir(self):
        r = self.client.get(reverse("senaryo", args=["ofis"]))
        self.assertContains(r, "merkezi tek hata noktası")
        self.assertContains(r, "fw_1")

    def test_hastanede_spof_yok_gosterilir(self):
        r = self.client.get(reverse("senaryo", args=["hastane"]))
        self.assertContains(r, "Merkezi tek hata noktası yok")

    def test_bos_veritabaninda_yonlendirme_mesaji(self):
        from .. import models
        models.Senaryo.objects.all().delete()
        r = self.client.get(reverse("index"))
        self.assertContains(r, "seed_senaryolar")


class HataSimulasyonuTestleri(SenaryolarYuklu):
    def test_tek_core_dusunce_gereksinimler_karsilanir(self):
        r = self.client.get(reverse("hata", args=["hastane"]), {"bozuk": ["core_1"]})
        self.assertContains(r, "Tüm gereksinimler karşılanıyor")

    def test_iki_core_dusunce_gereksinimler_kopar(self):
        r = self.client.get(reverse("hata", args=["hastane"]), {"bozuk": ["core_1", "core_2"]})
        self.assertContains(r, "gereksinim koptu")
        self.assertContains(r, "acil_pc")

    def test_bozulan_cihaz_diyagramda_isaretlenir(self):
        r = self.client.get(reverse("hata", args=["ofis"]), {"bozuk": ["fw_1"]})
        self.assertContains(r, "class fw_1 bozuk")

    def test_gecersiz_cihaz_yoksayilir(self):
        r = self.client.get(reverse("hata", args=["ofis"]), {"bozuk": ["yok_boyle_cihaz"]})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "gereksinim koptu")

    def test_guc_kesintisi(self):
        r = self.client.get(reverse("hata", args=["ofis"]), {"bozuk": ["sebeke", "jenerator"]})
        self.assertContains(r, "Güç kaynağı kesildiği için kapanan cihazlar")

    def test_kaydet_dugmesi_sadece_girisli_kullanicida(self):
        url, bozuk = reverse("hata", args=["ofis"]), {"bozuk": ["fw_1"]}
        self.assertNotContains(self.client.get(url, bozuk), "Geçmişe kaydet")
        self.client.force_login(self.ali)
        self.assertContains(self.client.get(url, bozuk), "Geçmişe kaydet")


class ErisimTestleri(SenaryolarYuklu):
    def test_matris_ve_engeller(self):
        r = self.client.get(reverse("erisim", args=["universite"]))
        self.assertContains(r, "engelin hepsi çalışıyor")
        self.assertContains(r, "ogrenci_isleri")

    def test_sorgu_politika_engeller(self):
        r = self.client.get(reverse("erisim", args=["universite"]),
                            {"kaynak": "ogrenci_cihazi", "hedef": "ogrenci_isleri_db", "port": "3306"})
        self.assertContains(r, "ENGEL")
        self.assertContains(r, "Fiziksel yol")

    def test_sorgu_izin(self):
        r = self.client.get(reverse("erisim", args=["universite"]),
                            {"kaynak": "ogrenci_isleri_pc", "hedef": "ogrenci_isleri_db", "port": "3306"})
        self.assertContains(r, "İZİN")

    def test_gecersiz_sorgu(self):
        r = self.client.get(reverse("erisim", args=["ofis"]), {"kaynak": "yok", "hedef": "pc_k1"})
        self.assertContains(r, "Geçersiz cihaz seçimi")
        r = self.client.get(reverse("erisim", args=["ofis"]), {"kaynak": "pc_k1", "hedef": "ad", "port": "abc"})
        self.assertContains(r, "Port 1-65535")
        r = self.client.get(reverse("erisim", args=["ofis"]), {"kaynak": "pc_k1", "hedef": "ad", "port": "99999"})
        self.assertContains(r, "Port 1-65535")


class IzlemeTestleri(SenaryolarYuklu):
    def test_saglam_ag(self):
        self.assertContains(self.client.get(reverse("izleme", args=["ofis"])), "cihaz UP")

    def test_ariza_alarm_uretir(self):
        r = self.client.get(reverse("izleme", args=["ofis"]), {"bozuk": ["core_1"]})
        self.assertContains(r, "ARIZALI")
        self.assertContains(r, "ULAŞILAMIYOR")


class SiemTestleri(SenaryolarYuklu):
    def test_bos_sayfa(self):
        self.assertEqual(self.client.get(reverse("siem")).status_code, 200)

    def test_ornek_saldirili_girissiz_acilir(self):
        r = self.client.get(reverse("siem"), {"ornek": "saldirili"})
        self.assertContains(r, "VERI_SIZINTISI")
        self.assertContains(r, "KRITIK")

    def test_ornek_normal_alarm_yok(self):
        self.assertContains(self.client.get(reverse("siem"), {"ornek": "normal"}), "Alarm yok")

    def test_ornek_log_gecmise_yazilmaz(self):
        from .. import models
        self.client.force_login(self.ali)
        self.client.get(reverse("siem"), {"ornek": "saldirili"})
        self.assertEqual(models.Simulasyon.objects.count(), 0)

    def test_girissiz_log_analizi_reddedilir(self):
        log = "2026-11-05T14:00:00 fw_1 AUTH FAIL user=ali src=203.0.113.9"
        r = self.client.post(reverse("siem"), {"log": log})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "giriş yapın", status_code=403)

    def test_yapistirilan_log_analiz_edilir_ve_kaydedilir(self):
        from .. import models
        self.client.force_login(self.ali)
        log = "\n".join(f"2026-11-05T14:00:0{i} fw_1 AUTH FAIL user=ali src=203.0.113.9" for i in range(6))
        r = self.client.post(reverse("siem"), {"log": log})
        self.assertContains(r, "BRUTE_FORCE")
        k = models.Simulasyon.objects.get(kullanici=self.ali, tur="siem")
        self.assertEqual(k.girdi["satir"], 6)
        self.assertNotIn("AUTH FAIL", str(k.girdi))  # logun kendisi saklanmaz

    def test_cok_buyuk_log_reddedilir(self):
        self.client.force_login(self.ali)
        r = self.client.post(reverse("siem"), {"log": "x" * 1_100_000})
        self.assertContains(r, "en fazla 1 MB")

    def test_log_html_kacirilir(self):
        self.client.force_login(self.ali)
        r = self.client.post(reverse("siem"), {"log": "<script>alert(1)</script>"})
        self.assertNotContains(r, "<script>alert(1)</script>")
