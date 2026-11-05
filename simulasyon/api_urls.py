from django.urls import path

from . import api

urlpatterns = [
    path("", api.kok),
    path("senaryolar/", api.SenaryoListesi.as_view()),
    path("senaryolar/<slug:slug>/", api.SenaryoDetay.as_view()),
    path("senaryolar/<slug:slug>/analiz/", api.Analiz.as_view()),
    path("senaryolar/<slug:slug>/diyagram/", api.Diyagram.as_view()),
    path("senaryolar/<slug:slug>/hata/", api.Hata.as_view()),
    path("senaryolar/<slug:slug>/izleme/", api.Izleme.as_view()),
    path("senaryolar/<slug:slug>/zaman/", api.Zaman.as_view()),
    path("senaryolar/<slug:slug>/erisim/", api.Erisim.as_view()),
    path("siem/", api.Siem.as_view()),
    path("ariza/", api.ArizaListesi.as_view()),
    path("ariza/ozet/", api.ArizaOzeti.as_view()),
    path("gecmis/", api.GecmisListesi.as_view()),
    path("gecmis/<int:pk>/", api.GecmisDetay.as_view()),
]
