"""Admin paneli: senaryoyu sayfadan düzenleme ve hatalı girdiyi reddetme."""
from django.contrib.auth.models import User
from django.urls import reverse

from .. import models
from .yardimci import PAROLA, SenaryolarYuklu


class AdminTestleri(SenaryolarYuklu):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.yonetici = User.objects.create_superuser("yonetici", password=PAROLA)

    def setUp(self):
        self.client.force_login(self.yonetici)

    def test_yetkisiz_kullanici_giremez(self):
        self.client.force_login(self.ali)
        r = self.client.get("/admin/simulasyon/senaryo/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/", r["Location"])

    def test_liste_ve_degistirme_sayfalari_acilir(self):
        self.assertEqual(self.client.get("/admin/simulasyon/senaryo/").status_code, 200)
        self.assertEqual(self.client.get("/admin/simulasyon/senaryo/add/").status_code, 200)
        self.assertEqual(self.client.get("/admin/simulasyon/simulasyon/").status_code, 200)
        for s in models.Senaryo.objects.all():
            r = self.client.get(reverse("admin:simulasyon_senaryo_change", args=[s.pk]))
            with self.subTest(slug=s.slug):
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "Merkezi tek hata noktası")

    def test_listede_tek_hata_noktasi_sayisi(self):
        r = self.client.get("/admin/simulasyon/senaryo/")
        self.assertContains(r, "Senaryo 4")  # hastane başlığı

    def test_yeni_senaryo_eklenir(self):
        r = self.client.post(reverse("admin:simulasyon_senaryo_add"), {
            "slug": "kucuk", "baslik": "Küçük", "aciklama": "", "izleme_dugumu": "zabbix",
            "cihazlar-TOTAL_FORMS": 0, "cihazlar-INITIAL_FORMS": 0,
            "kurallar-TOTAL_FORMS": 0, "kurallar-INITIAL_FORMS": 0,
            "engeller-TOTAL_FORMS": 0, "engeller-INITIAL_FORMS": 0,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(models.Senaryo.objects.filter(slug="kucuk").exists())

    def test_senaryo_degistirme_formu_cihaz_ekler(self):
        s = models.Senaryo.objects.get(slug="ofis")
        veri = self._form_verisi(s)
        n = int(veri["cihazlar-TOTAL_FORMS"])
        veri.update({"cihazlar-TOTAL_FORMS": n + 1, f"cihazlar-{n}-ad": "yeni_switch",
                     f"cihazlar-{n}-tur": "switch", f"cihazlar-{n}-senaryo": s.pk})
        r = self.client.post(reverse("admin:simulasyon_senaryo_change", args=[s.pk]), veri)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["errors"])
        self.assertTrue(models.Cihaz.objects.filter(senaryo=s, ad="yeni_switch").exists())

    def test_hatali_cihaz_adi_reddedilir(self):
        s = models.Senaryo.objects.get(slug="ofis")
        veri = self._form_verisi(s)
        n = int(veri["cihazlar-TOTAL_FORMS"])
        veri.update({"cihazlar-TOTAL_FORMS": n + 1, f"cihazlar-{n}-ad": "graph",
                     f"cihazlar-{n}-tur": "switch", f"cihazlar-{n}-senaryo": s.pk})
        r = self.client.post(reverse("admin:simulasyon_senaryo_change", args=[s.pk]), veri)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(models.Cihaz.objects.filter(senaryo=s, ad="graph").exists())

    def test_baglanti_secenekleri_sadece_ayni_senaryonun_cihazlari(self):
        ofis = models.Senaryo.objects.get(slug="ofis")
        r = self.client.get(reverse("admin:simulasyon_senaryo_change", args=[ofis.pk]))
        formset = [fs for fs in r.context["inline_admin_formsets"] if fs.opts.model is models.Baglanti][0]
        kaynak_alani = formset.formset.empty_form.fields["kaynak"]
        self.assertEqual(set(kaynak_alani.queryset.values_list("senaryo__slug", flat=True)), {"ofis"})

    def test_baska_senaryonun_cihaziyla_kablo_reddedilir(self):
        ofis = models.Senaryo.objects.get(slug="ofis")
        yabanci = models.Cihaz.objects.filter(senaryo__slug="hastane").first()
        icerde = models.Cihaz.objects.filter(senaryo=ofis).first()
        veri = self._form_verisi(ofis)
        n = int(veri["baglantilar-TOTAL_FORMS"])
        veri.update({"baglantilar-TOTAL_FORMS": n + 1, f"baglantilar-{n}-kaynak": icerde.pk,
                     f"baglantilar-{n}-hedef": yabanci.pk, f"baglantilar-{n}-senaryo": ofis.pk})
        sayi = models.Baglanti.objects.count()
        r = self.client.post(reverse("admin:simulasyon_senaryo_change", args=[ofis.pk]), veri)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(models.Baglanti.objects.count(), sayi)

    def test_simulasyon_kaydi_admin_de_eklenemez(self):
        self.assertEqual(self.client.get("/admin/simulasyon/simulasyon/add/").status_code, 403)

    # Admin formunun gerektirdiği yönetim alanlarıyla birlikte mevcut kayıtları aynen geri gönderir.
    def _form_verisi(self, s):
        r = self.client.get(reverse("admin:simulasyon_senaryo_change", args=[s.pk]))
        veri = {"slug": s.slug, "baslik": s.baslik, "aciklama": s.aciklama, "izleme_dugumu": s.izleme_dugumu}
        for fs in r.context["inline_admin_formsets"]:
            f = fs.formset
            veri[f"{f.prefix}-TOTAL_FORMS"] = f.total_form_count()
            veri[f"{f.prefix}-INITIAL_FORMS"] = f.initial_form_count()
            for form in f.forms:
                for ad, alan in form.fields.items():
                    deger = form[ad].value()
                    if isinstance(deger, (list, tuple)):
                        veri[form.add_prefix(ad)] = list(deger)
                    elif deger not in (None, False):
                        veri[form.add_prefix(ad)] = deger
        return veri
