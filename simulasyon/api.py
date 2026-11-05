"""REST API (Django REST framework).

Okuma ve hesaplama uçları herkese açıktır; sonucu geçmişe kaydetmek ve SIEM analizi giriş ister.
Geçmiş yalnızca isteği yapan kullanıcının kayıtlarını gösterir.
"""
from django.http import Http404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import models, servis


def _senaryo(slug):
    try:
        return servis.senaryo_getir(slug)
    except models.Senaryo.DoesNotExist:
        raise Http404("Senaryo bulunamadı")


def _girdi_hatasi(e):
    return ValidationError({"detay": str(e)})


class SenaryoListesi(APIView):
    def get(self, request):
        return Response([servis.ozet(o, servis.senaryo_yukle(o)) for o in models.Senaryo.objects.all()])


class SenaryoDetay(APIView):
    def get(self, request, slug):
        obj, es = _senaryo(slug)
        return Response({
            **servis.ozet(obj, es), "aciklama": obj.aciklama, "izleme_dugumu": obj.izleme_dugumu,
            "cihazlar": [{"ad": n, **{k: d[k] for k in ("tur", "etiket", "bolge", "katman")}, "guc": list(d["guc"])}
                         for n, d in es.graf.nodes(data=True)],
            "kablolar": [list(e) for e in es.graf.edges],
            "gereksinimler": servis.gereksinim_listesi(es),
            "sorunlar": obj.sorunlar(),
        })


class Analiz(APIView):
    def get(self, request, slug):
        return Response(servis.analiz(_senaryo(slug)[1]))


class Diyagram(APIView):
    def get(self, request, slug):
        return Response({"mermaid": servis.diyagram(_senaryo(slug)[1])})


class _KayitliHesap(APIView):
    """GET: hesapla. POST: aynı hesabı yapıp geçmişe kaydet (giriş ister)."""
    tur = ""

    def girdi(self, es, veri):
        raise NotImplementedError

    def hesapla(self, es, girdi):
        raise NotImplementedError

    def ozet_metni(self, sonuc):
        raise NotImplementedError

    def calistir(self, request, slug, veri, kaydet):
        obj, es = _senaryo(slug)
        if not hasattr(veri, "get"):
            raise _girdi_hatasi(servis.GirdiHatasi("İstek gövdesi bir JSON nesnesi olmalı."))
        try:
            girdi = self.girdi(es, veri)
            sonuc = self.hesapla(es, girdi)
        except servis.GirdiHatasi as e:
            raise _girdi_hatasi(e)
        if kaydet:
            if not request.user.is_authenticated:
                raise NotAuthenticated()
            k = servis.kaydet(request.user, obj, self.tur, girdi, sonuc, self.ozet_metni(sonuc))
            return Response({**sonuc, "kayit_id": k.pk}, status=201)
        return Response(sonuc)

    def get(self, request, slug):
        return self.calistir(request, slug, request.query_params, kaydet=False)

    def post(self, request, slug):
        return self.calistir(request, slug, request.data, kaydet=True)


def _liste(veri, anahtar):
    if hasattr(veri, "getlist"):
        return veri.getlist(anahtar)
    d = veri.get(anahtar, [])
    if isinstance(d, str):
        return [d]
    if not isinstance(d, list) or not all(isinstance(x, str) for x in d):
        raise servis.GirdiHatasi(f"'{anahtar}' bir ad listesi olmalı.")
    return d


class Hata(_KayitliHesap):
    tur = models.Simulasyon.HATA

    def girdi(self, es, veri):
        bozuk = servis.bozuklari_ayikla(es, _liste(veri, "bozuk"), katı=True)
        if not bozuk:
            raise servis.GirdiHatasi("En az bir eleman verin: bozuk=core_1&bozuk=core_2")
        return {"bozuk": bozuk}

    def hesapla(self, es, girdi):
        return servis.hata(es, girdi["bozuk"])

    def ozet_metni(self, sonuc):
        return servis.hata_ozeti(sonuc)


class Izleme(_KayitliHesap):
    tur = models.Simulasyon.IZLEME

    def girdi(self, es, veri):
        return {"bozuk": servis.bozuklari_ayikla(es, _liste(veri, "bozuk"), katı=True)}

    def hesapla(self, es, girdi):
        return servis.izleme(es, girdi["bozuk"])

    def ozet_metni(self, sonuc):
        return servis.izleme_ozeti(sonuc)


class Erisim(_KayitliHesap):
    tur = models.Simulasyon.ERISIM

    def girdi(self, es, veri):
        kaynak, hedef = veri.get("kaynak"), veri.get("hedef")
        if not isinstance(kaynak, str) or not isinstance(hedef, str):
            raise servis.GirdiHatasi("kaynak ve hedef cihaz adı verin.")
        return {"kaynak": kaynak, "hedef": hedef, "port": veri.get("port", "")}

    def hesapla(self, es, girdi):
        return servis.erisim_sorgusu(es, **girdi)

    def ozet_metni(self, sonuc):
        return servis.erisim_ozeti(sonuc)

    def get(self, request, slug):
        # Parametre yoksa matrisin kendisini döndür.
        if "kaynak" not in request.query_params and "hedef" not in request.query_params:
            return Response(servis.erisim_matrisi_tablosu(_senaryo(slug)[1]))
        return super().get(request, slug)


class Siem(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not hasattr(request.data, "get"):
            raise ValidationError({"detay": "İstek gövdesi bir JSON nesnesi olmalı."})
        log = request.data.get("log")
        if not isinstance(log, str) or not log.strip():
            raise ValidationError({"detay": "'log' alanında log metni verin."})
        kaynak = request.data.get("kaynak") if isinstance(request.data.get("kaynak"), str) else "API"
        try:
            rapor = servis.siem(log, kaynak[:100])
        except servis.GirdiHatasi as e:
            raise _girdi_hatasi(e)
        k = servis.kaydet(request.user, None, models.Simulasyon.SIEM,
                          {"kaynak": rapor["kaynak"], "satir": len(log.splitlines())}, rapor,
                          servis.siem_ozeti(rapor))
        return Response({**rapor, "kayit_id": k.pk}, status=201)


class GecmisSerializer(serializers.ModelSerializer):
    senaryo = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = models.Simulasyon
        fields = ["id", "tur", "senaryo", "zaman", "ozet", "girdi", "sonuc"]


class GecmisListesi(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GecmisSerializer

    def get_queryset(self):
        q = models.Simulasyon.objects.filter(kullanici=self.request.user).select_related("senaryo")
        tur = self.request.query_params.get("tur")
        return q.filter(tur=tur) if tur in dict(models.Simulasyon.TURLER) else q


class GecmisDetay(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GecmisSerializer

    def get_queryset(self):
        return models.Simulasyon.objects.filter(kullanici=self.request.user).select_related("senaryo")


@api_view(["GET"])
def kok(request):
    return Response({
        "senaryolar": request.build_absolute_uri("/api/senaryolar/"),
        "gecmis": request.build_absolute_uri("/api/gecmis/"),
        "siem": request.build_absolute_uri("/api/siem/"),
    })
