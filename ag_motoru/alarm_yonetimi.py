"""Alarm yönetimi: kök neden bastırma, dalgalanma (flapping) ve arıza olayları.

Gerçek izleme sistemleri her anormal durumu ayrı ayrı bildirmez. Üç şey yapar:

  1. Bağımlılık bastırma: izleme düğümüne giden yolda bir cihaz düştüyse, onun arkasında
     kalıp ulaşılamayan cihazların alarmı bastırılır; sadece kök neden bildirilir.
  2. Histerezis: bir cihaz üst üste `deneme` kontrol başarısız olmadan alarm onaylanmaz
     (tek seferlik kayıplar alarm üretmez; Nagios'taki soft/hard durum mantığı).
  3. Dalgalanma (flapping): son `pencere` kontrolde `esik` ya da daha fazla kez durum
     değiştiren cihaz için tek tek alarm yerine tek bir "dalgalanıyor" bildirimi gönderilir.

Zaman, "kontrol sayısı" olarak ilerler: her adım bir izleme kontrolüdür.
"""
from __future__ import annotations

from collections import deque

from .ag_modelleri import GECIS_TURLERI, Senaryo
from .mini_izleme import IZLEME_KAPALI, UP, ag_izleme

MAKS_ADIM = 120


# ---- 1. bağımlılık bastırma ----------------------------------------------------------------

def ust_dugumler(senaryo: Senaryo) -> tuple:
    """(üstler, seviye): sağlam topolojide izleme düğümüne bir adım daha yakın komşular.

    Sunucu/istemci gibi uç cihazlar yol üzerinde sayılmaz (ulaşılabilirlik kuralıyla aynı).
    """
    g, izleyici = senaryo.graf, senaryo.izleme_dugumu
    seviye = {izleyici: 0}
    kuyruk = deque([izleyici])
    while kuyruk:
        n = kuyruk.popleft()
        if n != izleyici and g.nodes[n]["tur"] not in GECIS_TURLERI:
            continue
        for m in g[n]:
            if m not in seviye:
                seviye[m] = seviye[n] + 1
                kuyruk.append(m)
    ustler = {n: [u for u in g[n] if seviye.get(u) == s - 1
                  and (u == izleyici or g.nodes[u]["tur"] in GECIS_TURLERI)]
              for n, s in seviye.items() if n != izleyici}
    return ustler, seviye


def kok_neden(senaryo: Senaryo, durumlar: dict) -> dict:
    """UP olmayan cihazları kök neden ve bastırılan (belirti) olarak ayırır.

    Bir cihaz, izleme düğümüne giden bütün üst komşuları da UP değilse belirtidir.
    En az bir üst komşusu UP olduğu halde kendisi UP değilse kök nedendir.
    Dönen sözlük: kokler (listesi), bastirilan (cihaz -> hangi köklerin arkasında),
    izleme_kapali (izleme düğümü kendisi kapalıysa hiçbir şey ayırt edilemez).
    """
    down = {n for n, d in durumlar.items() if d != UP}
    if durumlar and all(d == IZLEME_KAPALI for d in durumlar.values()):
        return {"kokler": [], "bastirilan": {}, "izleme_kapali": True}
    ustler, seviye = ust_dugumler(senaryo)

    kok_mu = {}
    for n in down:
        u = ustler.get(n)
        kok_mu[n] = not u or any(x not in down for x in u)

    onbellek = {}

    def koklere(n):
        if kok_mu[n]:
            return {n}
        if n not in onbellek:
            onbellek[n] = set().union(*(koklere(x) for x in ustler[n] if x in down))
        return onbellek[n]

    kokler = sorted((n for n in down if kok_mu[n]), key=lambda n: (seviye.get(n, 10**6), n))
    bastirilan = {n: sorted(koklere(n)) for n in sorted(down) if not kok_mu[n]}
    return {"kokler": kokler, "bastirilan": bastirilan, "izleme_kapali": False}


def kok_neden_metni(senaryo: Senaryo, durumlar: dict) -> str:
    k = kok_neden(senaryo, durumlar)
    if k["izleme_kapali"]:
        return "İzleme düğümü kapalı: hiçbir cihaz ayırt edilemez, alarm üretilemez."
    if not k["kokler"]:
        return "Alarm yok."
    satirlar = [f"{len(k['kokler'])} kök neden, {len(k['bastirilan'])} alarm bastırıldı:"]
    for r in k["kokler"]:
        arkada = sorted(c for c, koker in k["bastirilan"].items() if r in koker)
        ek = f" (arkasında {len(arkada)} cihaz)" if arkada else ""
        satirlar.append(f"  KÖK NEDEN: {r} {durumlar[r]}{ek}")
    return "\n".join(satirlar)


# ---- 2 ve 3. histerezis, dalgalanma, olaylar -----------------------------------------------

def desen_coz(desen: str) -> list:
    """'0110' -> [False, True, True, False]. 1 = eleman bozuk, 0 = sağlam."""
    desen = (desen or "").strip()
    if not 2 <= len(desen) <= MAKS_ADIM or set(desen) - {"0", "1"}:
        raise ValueError(f"Desen 2-{MAKS_ADIM} karakterlik 0 ve 1 dizisi olmalı (örn. 0111010111).")
    return [c == "1" for c in desen]


def _parametre(ad, deger, alt, ust):
    if not isinstance(deger, int) or isinstance(deger, bool) or not alt <= deger <= ust:
        raise ValueError(f"{ad} {alt}-{ust} arasında bir tam sayı olmalı.")
    return deger


def _segmentler(ok: list) -> list:
    """Üst üste başarısız kontrol dizileri: [(baslangic, bitis_dahil)]."""
    sonuc, bas = [], None
    for i, d in enumerate(ok):
        if not d and bas is None:
            bas = i
        elif d and bas is not None:
            sonuc.append((bas, i - 1))
            bas = None
    if bas is not None:
        sonuc.append((bas, len(ok) - 1))
    return sonuc


def seri_analizi(senaryo: Senaryo, bozuklar, desen: str, deneme: int = 3, pencere: int = 10,
                 esik: int = 3, aralik_sn: int = 60) -> dict:
    """Her kontrolde `bozuklar` desene göre bozulur/onarılır; alarm akışı hesaplanır.

    Dönen sözlük: adimlar, cihazlar, olaylar, bildirimler, ozet.
    """
    desen_adim = desen_coz(desen)
    n_adim = len(desen_adim)
    deneme = _parametre("deneme", deneme, 1, 10)
    pencere = _parametre("pencere", pencere, 3, MAKS_ADIM)
    esik = _parametre("esik", esik, 2, pencere)
    aralik_sn = _parametre("aralik_sn", aralik_sn, 1, 86400)
    bozuklar = list(dict.fromkeys(bozuklar))

    # Sadece iki farklı durum var (sağlam / bozuk): her biri bir kez hesaplanır.
    durum_onbellek = {}

    def durum_al(bozuk_mu):
        if bozuk_mu not in durum_onbellek:
            d = ag_izleme(senaryo, bozuklar if bozuk_mu else ())
            durum_onbellek[bozuk_mu] = (d, kok_neden(senaryo, d))
        return durum_onbellek[bozuk_mu]

    adim_durum = [durum_al(b) for b in desen_adim]
    cihazlar = list(adim_durum[0][0])
    ok = {c: [durum[c] == UP for durum, _ in adim_durum] for c in cihazlar}
    ustler, seviye = ust_dugumler(senaryo)

    # dalgalanma: her adımda son `pencere` kontrol içindeki durum değişikliği sayısı
    def pencere_gecis(c, t):
        a = max(0, t - pencere + 1)
        return sum(1 for i in range(a + 1, t + 1) if ok[c][i] != ok[c][i - 1])

    dalga = {c: [pencere_gecis(c, t) >= esik for t in range(n_adim)] for c in cihazlar}

    olaylar, onay_adimi = [], {}
    for c in cihazlar:
        for bas, bit in _segmentler(ok[c]):
            sure = bit - bas + 1
            onayli = sure >= deneme
            onay = bas + deneme - 1
            acik = bit == n_adim - 1
            kok = None
            if onayli:
                kok = c in adim_durum[onay][1]["kokler"]
                onay_adimi.setdefault(onay, []).append(c)
            olaylar.append({
                "cihaz": c, "baslangic": bas + 1, "bitis": None if acik else bit + 2,
                "sure": sure, "sure_sn": sure * aralik_sn, "acik": acik, "onayli": onayli,
                "kok_neden": kok, "dalgali": any(dalga[c][bas:bit + 1]),
            })
    olaylar.sort(key=lambda o: (o["baslangic"], seviye.get(o["cihaz"], 10**6), o["cihaz"]))

    # bildirim akışı
    sirali = sorted(cihazlar, key=lambda c: (seviye.get(c, 10**6), c))
    bildirimler, kok_bast, dalga_bast = [], 0, 0
    alarmli, dalgali_mi = set(), set()
    for t in range(n_adim):
        for c in sirali:
            if dalga[c][t] and c not in dalgali_mi:
                dalgali_mi.add(c)
                ustte = [u for u in ustler.get(c, ()) if u in dalga]
                if ustte and all(dalga[u][t] for u in ustte):
                    kok_bast += 1  # üstündeki cihaz da dalgalanıyor: bu bir belirti
                    continue
                bildirimler.append({"adim": t + 1, "tur": "DALGALANMA", "cihaz": c,
                                    "aciklama": f"{c}: son {pencere} kontrolde {pencere_gecis(c, t)} kez durum değiştirdi"})
            elif not dalga[c][t]:
                dalgali_mi.discard(c)
        for c in sirali:
            if c in onay_adimi.get(t, ()):
                durum = adim_durum[t][0][c]
                if c not in adim_durum[t][1]["kokler"]:
                    kok_bast += 1
                elif dalga[c][t]:
                    dalga_bast += 1
                else:
                    alarmli.add(c)
                    bildirimler.append({"adim": t + 1, "tur": "ALARM", "cihaz": c,
                                        "aciklama": f"{c} {durum} (kök neden, {deneme} kontrol üst üste başarısız)"})
            if t > 0 and ok[c][t] and not ok[c][t - 1] and c in alarmli:
                alarmli.discard(c)
                if not dalga[c][t]:
                    bildirimler.append({"adim": t + 1, "tur": "KURTARMA", "cihaz": c,
                                        "aciklama": f"{c} yeniden UP"})

    satirlar = []
    for c in cihazlar:
        notok = n_adim - sum(ok[c])
        if not notok:
            continue
        segs = _segmentler(ok[c])
        satirlar.append({
            "ad": c, "etiket": senaryo.graf.nodes[c]["etiket"],
            "gecis": sum(1 for i in range(1, n_adim) if ok[c][i] != ok[c][i - 1]),
            "ham_alarm": len(segs), "onayli_alarm": sum(1 for b, e in segs if e - b + 1 >= deneme),
            "dalgali": any(dalga[c]), "kullanilabilirlik": round(100 * (n_adim - notok) / n_adim, 1),
        })
    satirlar.sort(key=lambda r: (r["kullanilabilirlik"], r["ad"]))

    adimlar = []
    for t, (durum, kok) in enumerate(adim_durum):
        adimlar.append({"n": t + 1, "bozuk": desen_adim[t],
                        "up": sum(1 for d in durum.values() if d == UP), "toplam": len(durum),
                        "kokler": kok["kokler"], "bastirilan": len(kok["bastirilan"])})
    ham = sum(r["ham_alarm"] for r in satirlar)
    onayli = sum(r["onayli_alarm"] for r in satirlar)
    return {
        "desen": "".join("1" if b else "0" for b in desen_adim), "bozuk": bozuklar,
        "ayar": {"deneme": deneme, "pencere": pencere, "esik": esik, "aralik_sn": aralik_sn},
        "adimlar": adimlar, "cihazlar": satirlar, "olaylar": olaylar, "bildirimler": bildirimler,
        "ozet": {"adim": n_adim, "ham_alarm": ham, "gecici": ham - onayli, "onayli_alarm": onayli,
                 "kok_bastirilan": kok_bast, "dalgalanma_bastirilan": dalga_bast,
                 "bildirim": len(bildirimler), "dalgali_cihaz": sum(1 for r in satirlar if r["dalgali"])},
    }


def seri_metni(senaryo: Senaryo, bozuklar, desen: str, **ayar) -> str:
    s = seri_analizi(senaryo, bozuklar, desen, **ayar)
    o, a = s["ozet"], s["ayar"]
    satirlar = [
        f"== {senaryo.baslik}: alarm akışı ({o['adim']} kontrol, bozuk: {', '.join(s['bozuk']) or '-'}) ==",
        f"desen {s['desen']} (1 = bozuk)  deneme={a['deneme']} pencere={a['pencere']} eşik={a['esik']}",
        f"ham alarm {o['ham_alarm']} -> onaylı {o['onayli_alarm']} ({o['gecici']} geçici kayıp elendi)"
        f" -> bildirim {o['bildirim']} (kök nedene indirgenen {o['kok_bastirilan']},"
        f" dalgalanma nedeniyle bastırılan {o['dalgalanma_bastirilan']})",
        "", "Bildirimler:"]
    satirlar += [f"  kontrol {b['adim']:>3}  {b['tur']:<10} {b['aciklama']}" for b in s["bildirimler"]] or ["  yok"]
    satirlar += ["", "Olaylar (üst üste başarısız kontrol dizileri):"]
    satirlar += [f"  {x['cihaz']}: {x['baslangic']}-{x['bitis'] or '...'}  {x['sure']} kontrol"
                 f"{'  [onaylı]' if x['onayli'] else '  [geçici]'}"
                 f"{'  [dalgalı]' if x['dalgali'] else ''}" for x in s["olaylar"][:40]] or ["  yok"]
    return "\n".join(satirlar)
