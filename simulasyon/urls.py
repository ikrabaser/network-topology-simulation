from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("senaryo/<slug:slug>/", views.senaryo_detay, name="senaryo"),
    path("senaryo/<slug:slug>/hata/", views.hata, name="hata"),
    path("senaryo/<slug:slug>/erisim/", views.erisim, name="erisim"),
    path("senaryo/<slug:slug>/izleme/", views.izleme, name="izleme"),
    path("senaryo/<slug:slug>/kaydet/<str:tur>/", views.kaydet, name="kaydet"),
    path("siem/", views.siem, name="siem"),
    path("gecmis/", views.gecmis, name="gecmis"),
    path("gecmis/<int:pk>/", views.gecmis_detay, name="gecmis_detay"),
    path("gecmis/<int:pk>/sil/", views.gecmis_sil, name="gecmis_sil"),
    path("hesap/giris/", auth_views.LoginView.as_view(template_name="simulasyon/giris.html"), name="giris"),
    path("hesap/kayit/", views.kayit, name="kayit"),
    path("hesap/cikis/", auth_views.LogoutView.as_view(), name="cikis"),
]
