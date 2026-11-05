"""Veritabanı <-> motor dönüşümü.

senaryo_yukle(): veritabanındaki bir senaryoyu motorun beklediği `Senaryo` nesnesine çevirir.
ice_aktar():     motordaki (kodla yazılmış) bir senaryoyu veritabanına yazar.
"""
from __future__ import annotations

import networkx as nx
from django.db import transaction

from ag_motoru import ag_modelleri as motor

from . import models


def senaryo_yukle(obj: models.Senaryo) -> motor.Senaryo:
    g = nx.Graph()
    for c in obj.cihazlar.all():
        g.add_node(c.ad, tur=c.tur, etiket=c.etiket or c.ad, bolge=c.bolge or None,
                   guc=c.guc_listesi, katman="erisim" if c.erisim_katmani else "merkez")
    for b in obj.baglantilar.select_related("kaynak", "hedef"):
        g.add_edge(b.kaynak.ad, b.hedef.ad)
    gereksinimler = [
        motor.Gereksinim(r.kaynak.ad, tuple(h.ad for h in r.hedefler.all()), r.aciklama)
        for r in obj.gereksinimler.select_related("kaynak").prefetch_related("hedefler")
    ]
    kurallar = [motor.Kural(k.kaynak_bolge, k.hedef_bolge, k.port_kumesi, k.aciklama) for k in obj.kurallar.all()]
    engeller = [motor.Engel(e.kaynak_bolge, e.hedef_bolge, e.port, e.aciklama) for e in obj.engeller.all()]
    return motor.Senaryo(obj.slug, obj.baslik, g, gereksinimler, kurallar, engeller, obj.izleme_dugumu)


@transaction.atomic
def ice_aktar(es: motor.Senaryo, yenile: bool = False) -> tuple:
    """(Senaryo nesnesi, yazıldı_mı). Var olan senaryo `yenile` olmadan değiştirilmez."""
    obj, yeni = models.Senaryo.objects.get_or_create(
        slug=es.ad, defaults={"baslik": es.baslik, "izleme_dugumu": es.izleme_dugumu})
    if not yeni and not yenile:
        return obj, False
    if not yeni:
        # Cihazlar silinince kabloları ve gereksinim bağları da silinir; geçmiş kayıtları korunur.
        obj.cihazlar.all().delete()
        obj.kurallar.all().delete()
        obj.engeller.all().delete()
        obj.baslik, obj.izleme_dugumu = es.baslik, es.izleme_dugumu
        obj.save()

    g = es.graf
    cihaz = {}
    for ad, d in g.nodes(data=True):
        cihaz[ad] = models.Cihaz(
            senaryo=obj, ad=ad, tur=d["tur"], etiket=d["etiket"], bolge=d["bolge"] or "",
            guc=",".join(d["guc"]), erisim_katmani=d["katman"] == "erisim")
    models.Cihaz.objects.bulk_create(cihaz.values())
    cihaz = {c.ad: c for c in obj.cihazlar.all()}
    models.Baglanti.objects.bulk_create(
        [models.Baglanti(senaryo=obj, kaynak=cihaz[a], hedef=cihaz[b]) for a, b in g.edges])
    for r in es.gereksinimler:
        gk = models.Gereksinim.objects.create(senaryo=obj, kaynak=cihaz[r.kaynak], aciklama=r.aciklama)
        gk.hedefler.set([cihaz[h] for h in r.hedefler])
    models.Kural.objects.bulk_create([
        models.Kural(senaryo=obj, kaynak_bolge=k.kaynak, hedef_bolge=k.hedef,
                     portlar=",".join(str(p) for p in sorted(k.portlar)) if k.portlar else "",
                     aciklama=k.aciklama)
        for k in es.kurallar])
    models.Engel.objects.bulk_create([
        models.Engel(senaryo=obj, kaynak_bolge=e.kaynak, hedef_bolge=e.hedef, port=e.port, aciklama=e.aciklama)
        for e in es.engeller])
    return obj, True
