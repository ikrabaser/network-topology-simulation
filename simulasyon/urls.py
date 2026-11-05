from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("senaryo/<str:ad>/", views.senaryo_detay, name="senaryo"),
    path("senaryo/<str:ad>/hata/", views.hata, name="hata"),
    path("senaryo/<str:ad>/erisim/", views.erisim, name="erisim"),
    path("senaryo/<str:ad>/izleme/", views.izleme, name="izleme"),
    path("siem/", views.siem, name="siem"),
]
