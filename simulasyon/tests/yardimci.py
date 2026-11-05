"""Testler için ortak taban sınıf: yerleşik dört senaryoyu test veritabanına yükler."""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

SENARYOLAR = ("ofis", "eticaret", "universite", "hastane")
PAROLA = "deneme-parolasi-4821"


class SenaryolarYuklu(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_senaryolar", stdout=StringIO())
        cls.ali = User.objects.create_user("ali", password=PAROLA)
        cls.veli = User.objects.create_user("veli", password=PAROLA)
