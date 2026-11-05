"""Admin paneli: senaryoyu tek sayfadan düzenle (cihaz, kablo, gereksinim, kural, engel)."""
from django.contrib import admin
from django.utils.html import format_html

from ag_motoru import hata_simulasyonu

from . import models
from .yukle import senaryo_yukle


class SenaryoyaSinirli:
    """Inline'larda cihaz seçimlerini düzenlenen senaryonun cihazlarıyla sınırlar."""

    def _cihazlar(self, request):
        obj = getattr(request, "_senaryo", None)
        return models.Cihaz.objects.filter(senaryo=obj) if obj else models.Cihaz.objects.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.related_model is models.Cihaz:
            kwargs["queryset"] = self._cihazlar(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.related_model is models.Cihaz:
            kwargs["queryset"] = self._cihazlar(request)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class CihazInline(admin.TabularInline):
    model = models.Cihaz
    extra = 0
    fields = ("ad", "tur", "etiket", "bolge", "guc", "erisim_katmani")


class BaglantiInline(SenaryoyaSinirli, admin.TabularInline):
    model = models.Baglanti
    extra = 0
    verbose_name_plural = "bağlantılar (önce cihazları kaydedin, sonra kablo ekleyin)"


class GereksinimInline(SenaryoyaSinirli, admin.TabularInline):
    model = models.Gereksinim
    extra = 0
    verbose_name_plural = "gereksinimler (kaynak, hedeflerden en az birine ulaşabilmeli)"


class KuralInline(admin.TabularInline):
    model = models.Kural
    extra = 0


class EngelInline(admin.TabularInline):
    model = models.Engel
    extra = 0


@admin.register(models.Senaryo)
class SenaryoAdmin(admin.ModelAdmin):
    list_display = ("baslik", "slug", "cihaz_sayisi", "kablo_sayisi", "merkezi_spof", "sorun_sayisi", "guncellendi")
    search_fields = ("baslik", "slug")
    readonly_fields = ("analiz_ozeti", "sorun_listesi", "olusturuldu", "guncellendi")
    fields = ("slug", "baslik", "aciklama", "izleme_dugumu", "analiz_ozeti", "sorun_listesi",
              "olusturuldu", "guncellendi")
    inlines = [CihazInline, BaglantiInline, GereksinimInline, KuralInline, EngelInline]

    def get_form(self, request, obj=None, **kwargs):
        request._senaryo = obj
        return super().get_form(request, obj, **kwargs)

    def get_inlines(self, request, obj):
        # Kablo ve gereksinim için önce cihazların kayıtlı olması gerekir.
        return self.inlines if obj else [CihazInline, KuralInline, EngelInline]

    @admin.display(description="cihaz")
    def cihaz_sayisi(self, obj):
        return obj.cihazlar.count()

    @admin.display(description="kablo")
    def kablo_sayisi(self, obj):
        return obj.baglantilar.count()

    def _analiz(self, obj):
        try:
            return hata_simulasyonu.tek_hata_analizi(senaryo_yukle(obj))
        except Exception:  # bozuk senaryoda liste sayfası açılabilsin
            return None

    @admin.display(description="merkezi tek hata noktası")
    def merkezi_spof(self, obj):
        a = self._analiz(obj) if obj.cihazlar.exists() else None
        return "?" if a is None else len(a["spof"])

    @admin.display(description="sorun")
    def sorun_sayisi(self, obj):
        return len(obj.sorunlar())

    @admin.display(description="analiz özeti")
    def analiz_ozeti(self, obj):
        if not obj.pk or not obj.cihazlar.exists():
            return "Cihaz ekleyip kaydettikten sonra burada tek hata noktası özeti görünür."
        a = self._analiz(obj)
        if a is None:
            return "Analiz yapılamadı; senaryoyu kontrol edin."
        return (f"{obj.cihazlar.count()} cihaz, {obj.baglantilar.count()} kablo; {a['kontrol']} tek hata denendi. "
                f"Merkezi tek hata noktası: {len(a['spof'])}, erişim katmanında yerel etki: {len(a['yerel'])}.")

    @admin.display(description="tutarsızlıklar")
    def sorun_listesi(self, obj):
        if not obj.pk:
            return "-"
        s = obj.sorunlar()
        if not s:
            return "Sorun yok."
        return format_html("<br>".join(["{}"] * len(s)), *s)


@admin.register(models.Simulasyon)
class SimulasyonAdmin(admin.ModelAdmin):
    list_display = ("zaman", "kullanici", "tur", "senaryo", "ozet")
    list_filter = ("tur", "senaryo", "kullanici")
    date_hierarchy = "zaman"
    readonly_fields = ("kullanici", "senaryo", "tur", "zaman", "girdi", "sonuc", "ozet")

    def has_add_permission(self, request):
        return False


@admin.register(models.Ariza)
class ArizaAdmin(admin.ModelAdmin):
    list_display = ("zaman", "kullanici", "senaryo", "cihaz", "sure_sn", "acik", "kok_neden", "dalgali")
    list_filter = ("senaryo", "kok_neden", "acik", "dalgali")
    search_fields = ("cihaz", "kullanici__username")
    readonly_fields = [f.name for f in models.Ariza._meta.fields]

    def has_add_permission(self, request):
        return False
