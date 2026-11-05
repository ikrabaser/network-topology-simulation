from django.core.management.base import BaseCommand, CommandError

from ag_motoru.ag_modelleri import SENARYOLAR, senaryo_al
from simulasyon.yukle import ice_aktar


class Command(BaseCommand):
    help = "Yerleşik senaryoları (ofis, eticaret, universite, hastane) veritabanına aktarır."

    def add_arguments(self, parser):
        parser.add_argument("senaryolar", nargs="*", help="Aktarılacak senaryolar (boşsa hepsi).")
        parser.add_argument("--yenile", action="store_true",
                            help="Var olan senaryonun içeriğini yerleşik hâliyle değiştirir (admin düzenlemelerini siler).")

    def handle(self, *args, senaryolar, yenile, **opts):
        adlar = senaryolar or list(SENARYOLAR)
        bilinmeyen = [a for a in adlar if a not in SENARYOLAR]
        if bilinmeyen:
            raise CommandError(f"Bilinmeyen senaryo: {', '.join(bilinmeyen)}. Seçenekler: {', '.join(SENARYOLAR)}")
        for ad in adlar:
            es = senaryo_al(ad)
            obj, yazildi = ice_aktar(es, yenile=yenile)
            if yazildi:
                self.stdout.write(self.style.SUCCESS(
                    f"{ad}: aktarıldı ({obj.cihazlar.count()} cihaz, {obj.baglantilar.count()} kablo, "
                    f"{obj.gereksinimler.count()} gereksinim, {obj.kurallar.count()} kural, {obj.engeller.count()} engel)"))
            else:
                self.stdout.write(f"{ad}: zaten var, değiştirilmedi (--yenile ile sıfırlanır)")
