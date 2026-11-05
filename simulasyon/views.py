"""Django görünümleri: veritabanındaki senaryoları web sayfalarına bağlar.

Hesaplamalar `servis` modülündedir; burada sadece istek/yanıt ve yetki işleri var.
Geçmişe yazılan sonuç her zaman sunucuda yeniden hesaplanır.
"""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ag_motoru import ornek_log_uret

from . import models, servis


def _senaryo(slug):
    try:
        return servis.senaryo_getir(slug)
    except models.Senaryo.DoesNotExist:
        raise Http404("Senaryo bulunamadı")


def _secici(es, secili):
    return [{**e, "secili": e["ad"] in secili} for e in servis.secilebilir(es)]


def index(request):
    ozetler = []
    for obj in models.Senaryo.objects.all():
        try:
            ozetler.append(servis.ozet(obj, servis.senaryo_yukle(obj)))
        except Exception:  # yarım düzenlenmiş senaryo ana sayfayı bozmasın
            ozetler.append({"slug": obj.slug, "baslik": obj.baslik, "bozuk_senaryo": True})
    return render(request, "simulasyon/index.html", {"ozetler": ozetler})


def senaryo_detay(request, slug):
    obj, es = _senaryo(slug)
    a = servis.analiz(es)
    return render(request, "simulasyon/senaryo.html", {
        "s": obj, "sayfa": "senaryo", "diyagram": servis.diyagram(es), "kontrol": a["kontrol"],
        "spof": a["spof"], "yerel": a["yerel"], "gereksinimler": servis.gereksinim_listesi(es),
        "sorunlar": obj.sorunlar(),
    })


def hata(request, slug):
    obj, es = _senaryo(slug)
    bozuk = servis.bozuklari_ayikla(es, request.GET.getlist("bozuk"))
    sonuc = servis.hata(es, bozuk) if bozuk else None
    return render(request, "simulasyon/hata.html", {
        "s": obj, "sayfa": "hata", "secici": _secici(es, bozuk), "bozuk": bozuk, "sonuc": sonuc,
        "diyagram": servis.diyagram(es, bozuk=bozuk, olu=sonuc["olu"] if sonuc else ()),
    })


def erisim(request, slug):
    obj, es = _senaryo(slug)
    kaynak, hedef = request.GET.get("kaynak", ""), request.GET.get("hedef", "")
    port = request.GET.get("port", "").strip()
    sorgu = hata_mesaji = None
    if kaynak and hedef:
        try:
            sorgu = servis.erisim_sorgusu(es, kaynak, hedef, port)
        except servis.GirdiHatasi as e:
            hata_mesaji = str(e)
    tablo = servis.erisim_matrisi_tablosu(es)
    return render(request, "simulasyon/erisim.html", {
        "s": obj, "sayfa": "erisim", **tablo, "cihazlar": servis.erisim_cihazlari(es),
        "kaynak": kaynak, "hedef": hedef, "port": port, "sorgu": sorgu, "hata_mesaji": hata_mesaji,
    })


def izleme(request, slug):
    obj, es = _senaryo(slug)
    bozuk = servis.bozuklari_ayikla(es, request.GET.getlist("bozuk"))
    return render(request, "simulasyon/izleme.html", {
        "s": obj, "sayfa": "izleme", "secici": _secici(es, bozuk), "bozuk": bozuk,
        **{k: v for k, v in servis.izleme(es, bozuk).items() if k != "bozuk"},
    })


@login_required
@require_POST
def kaydet(request, slug, tur):
    """Geçmişe kaydet: girdiyi formdan al, sonucu sunucuda yeniden hesapla."""
    obj, es = _senaryo(slug)
    if tur == models.Simulasyon.HATA:
        bozuk = servis.bozuklari_ayikla(es, request.POST.getlist("bozuk"))
        if not bozuk:
            messages.error(request, "Kaydetmek için en az bir eleman seçin.")
            return redirect("hata", slug=slug)
        sonuc = servis.hata(es, bozuk)
        k = servis.kaydet(request.user, obj, tur, {"bozuk": bozuk}, sonuc, servis.hata_ozeti(sonuc))
    elif tur == models.Simulasyon.IZLEME:
        bozuk = servis.bozuklari_ayikla(es, request.POST.getlist("bozuk"))
        sonuc = servis.izleme(es, bozuk)
        k = servis.kaydet(request.user, obj, tur, {"bozuk": bozuk}, sonuc, servis.izleme_ozeti(sonuc))
    elif tur == models.Simulasyon.ERISIM:
        girdi = {"kaynak": request.POST.get("kaynak", ""), "hedef": request.POST.get("hedef", ""),
                 "port": request.POST.get("port", "").strip()}
        try:
            sonuc = servis.erisim_sorgusu(es, **girdi)
        except servis.GirdiHatasi as e:
            messages.error(request, str(e))
            return redirect("erisim", slug=slug)
        k = servis.kaydet(request.user, obj, tur, girdi, sonuc, servis.erisim_ozeti(sonuc))
    else:
        raise Http404("Bilinmeyen simülasyon türü")
    messages.success(request, "Geçmişe kaydedildi.")
    return redirect("gecmis_detay", pk=k.pk)


def siem(request):
    log, hata_mesaji, kaynak_adi, durum = "", None, "", 200
    kaydedilen = None
    if request.method == "POST":
        if not request.user.is_authenticated:
            hata_mesaji, durum = "Kendi logunuzu analiz etmek için giriş yapın.", 403
        else:
            yuklenen = request.FILES.get("dosya")
            if yuklenen:
                if yuklenen.size > servis.MAKS_LOG_BAYT:
                    hata_mesaji = "Dosya en fazla 1 MB olabilir."
                else:
                    log = yuklenen.read().decode("utf-8", errors="replace")
                    kaynak_adi = yuklenen.name
            else:
                log, kaynak_adi = request.POST.get("log", ""), "yapıştırılan metin"
    elif request.GET.get("ornek") in ("saldirili", "normal"):
        ornek = request.GET["ornek"]
        log = "\n".join(ornek_log_uret.uret(saldiri=ornek == "saldirili"))
        kaynak_adi = f"örnek {ornek} log"

    rapor = None
    if log.strip() and not hata_mesaji:
        try:
            rapor = servis.siem(log, kaynak_adi)
        except servis.GirdiHatasi as e:
            hata_mesaji, log = str(e).replace("Log", "Metin"), ""
    if rapor and request.method == "POST":
        kaydedilen = servis.kaydet(
            request.user, None, models.Simulasyon.SIEM,
            {"kaynak": kaynak_adi, "satir": len(log.splitlines())}, rapor, servis.siem_ozeti(rapor))
    return render(request, "simulasyon/siem.html", {
        "rapor": rapor, "hata_mesaji": hata_mesaji, "sayfa": "siem", "kaydedilen": kaydedilen,
        "log_onizleme": "\n".join(log.splitlines()[:200]) if rapor else "",
    }, status=durum)


# ---- hesap ---------------------------------------------------------------------------------

def kayit(request):
    if request.user.is_authenticated:
        return redirect("index")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("index")
    return render(request, "simulasyon/kayit.html", {"form": form})


# ---- geçmiş --------------------------------------------------------------------------------

@login_required
def gecmis(request):
    kayitlar = models.Simulasyon.objects.filter(kullanici=request.user).select_related("senaryo")
    tur = request.GET.get("tur", "")
    if tur in dict(models.Simulasyon.TURLER):
        kayitlar = kayitlar.filter(tur=tur)
    sayfa = Paginator(kayitlar, 20).get_page(request.GET.get("sayfa"))
    return render(request, "simulasyon/gecmis.html", {
        "sayfa_nesnesi": sayfa, "turler": models.Simulasyon.TURLER, "tur": tur})


@login_required
def gecmis_detay(request, pk):
    k = get_object_or_404(models.Simulasyon, pk=pk, kullanici=request.user)
    return render(request, "simulasyon/gecmis_detay.html", {"k": k, "sonuc": k.sonuc, "girdi": k.girdi})


@login_required
@require_POST
def gecmis_sil(request, pk):
    k = get_object_or_404(models.Simulasyon, pk=pk, kullanici=request.user)
    k.delete()
    messages.success(request, "Kayıt silindi.")
    return redirect("gecmis")
