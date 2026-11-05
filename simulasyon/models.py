"""Topoloji, kurallar ve simülasyon geçmişi için veritabanı modelleri.

Motor (ag_motoru/) Django'dan bağımsızdır; bu modeller `yukle.senaryo_yukle()` ile
motorun beklediği `Senaryo` nesnesine çevrilir.
"""
from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator, validate_slug
from django.db import models

TURLER = [
    ("internet", "İnternet"),
    ("hat", "Hat"),
    ("router", "Router / ONT"),
    ("firewall", "Firewall"),
    ("core", "Core switch"),
    ("switch", "Switch"),
    ("ap", "Wi-Fi erişim noktası"),
    ("sunucu", "Sunucu"),
    ("yonetim", "Yönetim / izleme"),
    ("istemci", "İstemci"),
    ("dis", "Dış sistem (bulut, DR sitesi)"),
]

# Mermaid düğüm kimliği olarak kullanıldığı için bu sözcükler cihaz adı olamaz.
YASAK_AD = {"end", "graph", "flowchart", "subgraph", "class", "classdef", "style", "click",
            "default", "direction", "linkstyle", "callback", "href"}

ad_dogrulayici = RegexValidator(
    r"^[a-z][a-z0-9_]*$", "Küçük harfle başlamalı; sadece küçük harf, rakam ve alt çizgi içermeli.")
bolge_dogrulayici = RegexValidator(
    r"^[a-z][a-z0-9_]*$", "Bölge adı küçük harfle başlamalı; sadece küçük harf, rakam ve alt çizgi içermeli.")
guc_dogrulayici = RegexValidator(
    r"^[a-z][a-z0-9_]*(,[a-z][a-z0-9_]*)*$", "Virgülle ayrılmış güç kaynağı adları (örn. sebeke,jenerator).")
port_listesi_dogrulayici = RegexValidator(
    r"^[0-9]{1,5}(,[0-9]{1,5})*$", "Virgülle ayrılmış port numaraları (örn. 80,443). Tüm portlar için boş bırakın.")


def etiket_dogrula(deger: str):
    if '"' in deger or "\n" in deger:
        raise ValidationError("Etiket çift tırnak veya satır sonu içeremez.")


def port_numarasi_dogrula(deger: str):
    for p in deger.split(","):
        if not p.isdigit():
            return  # biçim hatasını port_listesi_dogrulayici bildirir
        if not 1 <= int(p) <= 65535:
            raise ValidationError(f"Geçersiz port: {p} (1-65535 arası olmalı).")


class Senaryo(models.Model):
    slug = models.SlugField("kısa ad", max_length=40, unique=True, validators=[validate_slug],
                            help_text="URL'de kullanılır (örn. hastane).")
    baslik = models.CharField("başlık", max_length=120)
    aciklama = models.TextField("açıklama", blank=True)
    izleme_dugumu = models.CharField(
        "izleme düğümü", max_length=40, default="zabbix", validators=[ad_dogrulayici],
        help_text="İzleme sayfasında her cihaza ulaşmayı deneyen cihazın adı.")
    olusturuldu = models.DateTimeField(auto_now_add=True)
    guncellendi = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "senaryo"
        verbose_name_plural = "senaryolar"

    def __str__(self):
        return self.baslik

    def sorunlar(self) -> list:
        """Tutarsızlıkları metin olarak döndürür (boş liste = sorun yok)."""
        sorunlar = []
        cihazlar = list(self.cihazlar.all())
        adlar = {c.ad for c in cihazlar}
        bolgeler = {c.bolge for c in cihazlar if c.bolge}
        if not cihazlar:
            return ["Senaryoda hiç cihaz yok."]
        if self.izleme_dugumu not in adlar:
            sorunlar.append(f"İzleme düğümü '{self.izleme_dugumu}' cihazlar arasında yok.")
        for k in self.kurallar.all():
            for b in (k.kaynak_bolge, k.hedef_bolge):
                if b != "*" and b not in bolgeler:
                    sorunlar.append(f"Kural '{k.kaynak_bolge} -> {k.hedef_bolge}': '{b}' bölgesinde cihaz yok.")
        for e in self.engeller.all():
            for b in (e.kaynak_bolge, e.hedef_bolge):
                if b not in bolgeler:
                    sorunlar.append(f"Engel '{e.kaynak_bolge} -> {e.hedef_bolge}': '{b}' bölgesinde cihaz yok.")
        bagli = set()
        for b in self.baglantilar.select_related("kaynak", "hedef"):
            bagli.update((b.kaynak.ad, b.hedef.ad))
        yalniz = sorted(adlar - bagli)
        if yalniz and len(adlar) > 1:
            sorunlar.append("Hiçbir kabloya bağlı olmayan cihazlar: " + ", ".join(yalniz))
        return list(dict.fromkeys(sorunlar))


class Cihaz(models.Model):
    senaryo = models.ForeignKey(Senaryo, on_delete=models.CASCADE, related_name="cihazlar")
    ad = models.CharField("ad", max_length=40, validators=[ad_dogrulayici],
                          help_text="Benzersiz kimlik (örn. core_1).")
    tur = models.CharField("tür", max_length=10, choices=TURLER)
    etiket = models.CharField("etiket", max_length=80, blank=True, validators=[etiket_dogrula],
                              help_text="Diyagramda görünen ad. Boşsa ad kullanılır.")
    bolge = models.CharField("bölge (VLAN)", max_length=40, blank=True, validators=[bolge_dogrulayici],
                             help_text="Sunucu ve istemciler için güvenlik bölgesi.")
    guc = models.CharField("güç kaynakları", max_length=120, blank=True, validators=[guc_dogrulayici],
                           help_text="Cihazın çalışması için bu kaynaklardan biri yeter (örn. sebeke,jenerator).")
    erisim_katmani = models.BooleanField(
        "erişim katmanı", default=False,
        help_text="Kat/bina switch'i ve Wi-Fi AP için işaretleyin: arızası sadece o kat/binayı etkiler.")

    class Meta:
        ordering = ["id"]
        verbose_name = "cihaz"
        verbose_name_plural = "cihazlar"
        constraints = [models.UniqueConstraint(fields=["senaryo", "ad"], name="cihaz_ad_senaryoda_benzersiz")]

    def __str__(self):
        return f"{self.ad} ({self.get_tur_display()})"

    @property
    def guc_listesi(self) -> tuple:
        return tuple(k for k in self.guc.split(",") if k)

    def clean(self):
        if self.ad in YASAK_AD:
            raise ValidationError({"ad": f"'{self.ad}' ayrılmış bir sözcük, başka bir ad seçin."})
        if self.guc:
            ayni = [k for k in self.guc_listesi if self.guc_listesi.count(k) > 1]
            if ayni:
                raise ValidationError({"guc": "Aynı güç kaynağı birden fazla yazılmış."})


class Baglanti(models.Model):
    senaryo = models.ForeignKey(Senaryo, on_delete=models.CASCADE, related_name="baglantilar")
    kaynak = models.ForeignKey(Cihaz, on_delete=models.CASCADE, related_name="+")
    hedef = models.ForeignKey(Cihaz, on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["id"]
        verbose_name = "bağlantı (kablo)"
        verbose_name_plural = "bağlantılar (kablolar)"
        constraints = [models.UniqueConstraint(fields=["kaynak", "hedef"], name="baglanti_benzersiz")]

    def __str__(self):
        return f"{self.kaynak.ad} - {self.hedef.ad}"

    def clean(self):
        if not (self.kaynak_id and self.hedef_id):
            return
        if self.kaynak_id == self.hedef_id:
            raise ValidationError("Bir cihaz kendine bağlanamaz.")
        if self.kaynak.senaryo_id != self.senaryo_id or self.hedef.senaryo_id != self.senaryo_id:
            raise ValidationError("Her iki cihaz da bu senaryoya ait olmalı.")
        ters = Baglanti.objects.filter(kaynak_id=self.hedef_id, hedef_id=self.kaynak_id).exclude(pk=self.pk)
        if ters.exists():
            raise ValidationError("Bu iki cihaz zaten ters yönde bağlı (kablolar yönsüzdür).")


class Gereksinim(models.Model):
    senaryo = models.ForeignKey(Senaryo, on_delete=models.CASCADE, related_name="gereksinimler")
    kaynak = models.ForeignKey(Cihaz, on_delete=models.CASCADE, related_name="+")
    hedefler = models.ManyToManyField(
        Cihaz, related_name="+", help_text="Birden fazla seçilirse küme demektir: birine ulaşmak yeter.")
    aciklama = models.CharField("açıklama", max_length=200)

    class Meta:
        ordering = ["id"]
        verbose_name = "gereksinim"
        verbose_name_plural = "gereksinimler"

    def __str__(self):
        return self.aciklama

    def clean(self):
        if self.kaynak_id and self.kaynak.senaryo_id != self.senaryo_id:
            raise ValidationError({"kaynak": "Kaynak cihaz bu senaryoya ait olmalı."})


class Kural(models.Model):
    senaryo = models.ForeignKey(Senaryo, on_delete=models.CASCADE, related_name="kurallar")
    kaynak_bolge = models.CharField("kaynak bölge", max_length=40)
    hedef_bolge = models.CharField("hedef bölge", max_length=40)
    portlar = models.CharField("portlar", max_length=120, blank=True,
                               validators=[port_listesi_dogrulayici, port_numarasi_dogrula],
                               help_text="Virgülle ayrılmış (örn. 80,443). Boş = tüm portlar.")
    aciklama = models.CharField("açıklama", max_length=200, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "izin kuralı"
        verbose_name_plural = "izin kuralları"

    def __str__(self):
        return f"{self.kaynak_bolge} -> {self.hedef_bolge} ({self.portlar or 'tüm portlar'})"

    @property
    def port_kumesi(self):
        return frozenset(int(p) for p in self.portlar.split(",")) if self.portlar else None

    def clean(self):
        for alan in ("kaynak_bolge", "hedef_bolge"):
            d = getattr(self, alan)
            if d != "*" and not re.fullmatch(r"[a-z][a-z0-9_]*", d or ""):
                raise ValidationError({alan: "Bölge adı küçük harf/rakam/alt çizgi olmalı ya da * yazılmalı."})


class Engel(models.Model):
    """Politikanın kesinlikle reddetmesi gereken erişim (otomatik doğrulanır)."""
    senaryo = models.ForeignKey(Senaryo, on_delete=models.CASCADE, related_name="engeller")
    kaynak_bolge = models.CharField("kaynak bölge", max_length=40, validators=[bolge_dogrulayici])
    hedef_bolge = models.CharField("hedef bölge", max_length=40, validators=[bolge_dogrulayici])
    port = models.PositiveIntegerField("port", null=True, blank=True,
                                       validators=[MinValueValidator(1), MaxValueValidator(65535)],
                                       help_text="Boş = herhangi bir portta erişim olmamalı.")
    aciklama = models.CharField("açıklama", max_length=200)

    class Meta:
        ordering = ["id"]
        verbose_name = "beklenen engel"
        verbose_name_plural = "beklenen engeller"

    def __str__(self):
        return f"{self.kaynak_bolge} -/-> {self.hedef_bolge}"


class Simulasyon(models.Model):
    """Bir kullanıcının çalıştırıp kaydettiği simülasyon."""
    HATA, IZLEME, ERISIM, SIEM = "hata", "izleme", "erisim", "siem"
    TURLER = [(HATA, "Hata simülasyonu"), (IZLEME, "İzleme"), (ERISIM, "Erişim sorgusu"), (SIEM, "SIEM analizi")]

    kullanici = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="simulasyonlar")
    senaryo = models.ForeignKey(Senaryo, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="simulasyonlar", help_text="SIEM analizinde boştur.")
    tur = models.CharField(max_length=10, choices=TURLER)
    zaman = models.DateTimeField(auto_now_add=True)
    girdi = models.JSONField(default=dict)
    sonuc = models.JSONField(default=dict)
    ozet = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-zaman", "-id"]
        verbose_name = "simülasyon kaydı"
        verbose_name_plural = "simülasyon kayıtları"

    def __str__(self):
        return f"{self.get_tur_display()}: {self.ozet}"
