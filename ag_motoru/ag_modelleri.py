"""Dört ağ senaryosunun (ofis, e-ticaret, üniversite, hastane) graf modelleri.

Her senaryo üç şeyden oluşur:
  1. Fiziksel topoloji  -> networkx grafı (cihazlar = düğüm, kablolar = kenar)
  2. Gereksinimler      -> "şu cihaz şuraya ulaşabilmeli" listesi
  3. VLAN / bölge kuralları -> "hangi bölge hangi bölgeye hangi portla erişebilir"

Düğüm özellikleri:
  tur    : internet, hat, router, firewall, core, switch, ap, sunucu, istemci, yonetim, dis
  etiket : çizimlerde görünen ad
  bolge  : VLAN / güvenlik bölgesi (istemci ve sunucular için)
  guc    : cihazın çalışması için gereken güç kaynaklarından herhangi biri yeterlidir
  katman : "erisim" (kat/bina switch'i, AP) ya da "merkez"
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

# Trafiğin içinden geçebildiği cihaz türleri. Sunucu ve istemciler sadece
# uç noktadır: iki core arasında "sunucunun içinden" geçilemez.
GECIS_TURLERI = {"internet", "hat", "router", "firewall", "core", "switch", "ap"}

# Örnek port numaraları
HTTP, HTTPS, DNS, DHCP = 80, 443, 53, 67
SMTP, KERBEROS, LDAP, RADIUS = 25, 88, 389, 1812
MYSQL = 3306
YAZICI, RTSP = 9100, 554
DICOM, DICOM_TLS = 104, 11112
REPLIKASYON = 5001
WEB = (HTTP, HTTPS, DNS)


@dataclass(frozen=True)
class Kural:
    """Bölgeden bölgeye izin kuralı. portlar=None -> tüm portlar."""
    kaynak: str
    hedef: str
    portlar: frozenset | None = None
    aciklama: str = ""


@dataclass(frozen=True)
class Gereksinim:
    """kaynak, hedeflerden en az birine ulaşabilmeli (birden fazla hedef = küme)."""
    kaynak: str
    hedefler: tuple
    aciklama: str


@dataclass(frozen=True)
class Engel:
    """Politikanın kesinlikle reddetmesi gereken bir erişim."""
    kaynak: str
    hedef: str
    port: int | None
    aciklama: str


@dataclass
class Senaryo:
    ad: str
    baslik: str
    graf: nx.Graph
    gereksinimler: list
    kurallar: list
    engeller: list
    izleme_dugumu: str = "zabbix"


def izin(kaynak, hedef, *portlar, aciklama=""):
    return Kural(kaynak, hedef, frozenset(portlar) if portlar else None, aciklama)


class _Ag:
    """Graf kurmak için küçük yardımcı."""

    def __init__(self):
        self.g = nx.Graph()

    def dugum(self, ad, tur, etiket=None, bolge=None, guc=(), erisim=False):
        self.g.add_node(
            ad, tur=tur, etiket=etiket or ad, bolge=bolge,
            guc=tuple(guc), katman="erisim" if erisim else "merkez",
        )

    def bagla(self, a, *digerleri):
        for b in digerleri:
            if a not in self.g or b not in self.g:
                raise KeyError(f"Bilinmeyen düğüm: {a} - {b}")
            self.g.add_edge(a, b)


# ---------------------------------------------------------------------------
# Senaryo 1: Üç katlı ofis (tek hat, tek firewall)
# ---------------------------------------------------------------------------
def ofis(jenerator: bool = True) -> Senaryo:
    guc = ("sebeke", "jenerator") if jenerator else ("sebeke",)
    a = _Ag()
    a.dugum("internet", "internet", "İnternet", bolge="internet")
    a.dugum("hat_1", "hat", "Fiber hat")
    a.dugum("router_1", "router", "ONT / Edge Router", guc=guc)
    a.dugum("fw_1", "firewall", "Firewall", guc=guc)
    a.dugum("core_1", "core", "Core switch", guc=guc)
    a.dugum("dmz_sw", "switch", "DMZ switch", guc=guc)
    a.dugum("web_sunucu", "sunucu", "Web sunucu", bolge="dmz", guc=guc)
    a.dugum("eposta", "sunucu", "E-posta", bolge="dmz", guc=guc)
    for k in (1, 2, 3):
        a.dugum(f"kat{k}_sw", "switch", f"Kat {k} PoE switch", guc=guc, erisim=True)
    for s, et in (("ad", "Active Directory"), ("dhcp_dns", "DHCP/DNS"),
                  ("nac_radius", "NAC/Radius"), ("nas", "NAS (yedek)")):
        a.dugum(s, "sunucu", et, bolge="sunucu", guc=guc)
    a.dugum("zabbix", "yonetim", "Zabbix", bolge="yonetim", guc=guc)
    a.dugum("siem", "yonetim", "SIEM", bolge="yonetim", guc=guc)
    a.dugum("ap_k2", "ap", "Kat 2 Wi-Fi AP", guc=guc, erisim=True)
    a.dugum("pc_k1", "istemci", "PC", bolge="pc")
    a.dugum("telefon_k1", "istemci", "IP telefon", bolge="telefon")
    a.dugum("personel_k2", "istemci", "Personel (Wi-Fi)", bolge="personel_wifi")
    a.dugum("misafir_k2", "istemci", "Misafir (Wi-Fi)", bolge="misafir_wifi")
    a.dugum("yazici_k3", "istemci", "Yazıcı", bolge="yazici_kamera")
    a.dugum("kamera_k3", "istemci", "Kamera", bolge="yazici_kamera")

    a.bagla("internet", "hat_1")
    a.bagla("hat_1", "router_1")
    a.bagla("router_1", "fw_1")
    a.bagla("fw_1", "core_1", "dmz_sw")
    a.bagla("dmz_sw", "web_sunucu", "eposta")
    a.bagla("core_1", "kat1_sw", "kat2_sw", "kat3_sw", "ad", "dhcp_dns",
            "nac_radius", "nas", "zabbix", "siem")
    a.bagla("kat1_sw", "pc_k1", "telefon_k1")
    a.bagla("kat2_sw", "ap_k2")
    a.bagla("ap_k2", "personel_k2", "misafir_k2")
    a.bagla("kat3_sw", "yazici_k3", "kamera_k3")

    gereksinimler = [
        Gereksinim("pc_k1", ("internet",), "PC internete çıkabilmeli"),
        Gereksinim("pc_k1", ("ad",), "PC, AD sunucusuna ulaşabilmeli"),
        Gereksinim("personel_k2", ("ad",), "Personel Wi-Fi'dan AD'ye ulaşabilmeli"),
        Gereksinim("misafir_k2", ("internet",), "Misafir internete çıkabilmeli"),
        Gereksinim("kamera_k3", ("nas",), "Kamera kaydı NAS'a yazılabilmeli"),
        Gereksinim("internet", ("web_sunucu",), "Web sitesi internetten erişilebilir olmalı"),
        Gereksinim("internet", ("eposta",), "E-posta sunucusu internetten erişilebilir olmalı"),
    ]
    kurallar = [
        izin("pc", "sunucu", aciklama="AD, DHCP, DNS, dosya"),
        izin("pc", "internet", *WEB),
        izin("pc", "yazici_kamera", YAZICI, RTSP, aciklama="yazdırma ve kamera izleme"),
        izin("telefon", "sunucu", DNS, DHCP),
        izin("personel_wifi", "sunucu"),
        izin("personel_wifi", "internet", *WEB),
        izin("misafir_wifi", "internet", *WEB, aciklama="misafir sadece internete çıkar"),
        izin("sunucu", "internet", *WEB, aciklama="güncellemeler"),
        izin("internet", "dmz", HTTP, HTTPS, SMTP),
        izin("yonetim", "*", aciklama="yönetim ağı her yeri izler"),
    ]
    engeller = [
        Engel("misafir_wifi", "sunucu", None, "misafir iç ağa giremez"),
        Engel("misafir_wifi", "yonetim", None, "misafir yönetim ağına giremez"),
        Engel("yazici_kamera", "internet", None, "yazıcı/kamera internete kapalı"),
        Engel("internet", "sunucu", None, "internetten iç ağa doğrudan erişim yok"),
        Engel("dmz", "sunucu", None, "DMZ ele geçirilse iç ağa geçemez"),
    ]
    return Senaryo("ofis", "Senaryo 1: Üç katlı ofis (tek hat)", a.g,
                   gereksinimler, kurallar, engeller)


# ---------------------------------------------------------------------------
# Senaryo 2: E-ticaret (çift hat, çift firewall, çift core)
# ---------------------------------------------------------------------------
def eticaret() -> Senaryo:
    guc = ("sebeke", "jenerator")
    a = _Ag()
    a.dugum("internet", "internet", "İnternet", bolge="internet")
    a.dugum("evden_calisan", "istemci", "Evden çalışan (VPN)", bolge="uzaktan_vpn")
    a.dugum("bulut_yedek", "dis", "Bulut yedek", bolge="bulut")
    for i in (1, 2):
        a.dugum(f"hat_{i}", "hat", f"Hat {i}")
        a.dugum(f"router_{i}", "router", f"ONT/Router {i}", guc=guc)
        a.dugum(f"fw_{i}", "firewall", f"Firewall {i}", guc=guc)
        a.dugum(f"core_{i}", "core", f"Core switch {i}", guc=guc)
        a.dugum(f"dmz_sw_{i}", "switch", f"DMZ switch {i}", guc=guc)
    for s, et in (("waf", "WAF"), ("web_sunucu", "Web sunucu"),
                  ("odeme_sayfasi", "Ödeme sayfası")):
        a.dugum(s, "sunucu", et, bolge="dmz", guc=guc)
    for s, et in (("ad", "Active Directory"), ("dhcp_dns", "DHCP/DNS"),
                  ("nac_radius", "NAC/Radius"), ("veritabani", "Veritabanı"),
                  ("nas", "NAS (yedek)")):
        a.dugum(s, "sunucu", et, bolge="sunucu", guc=guc)
    a.dugum("zabbix", "yonetim", "Zabbix", bolge="yonetim", guc=guc)
    a.dugum("siem", "yonetim", "SIEM", bolge="yonetim", guc=guc)
    for k in (1, 2):
        a.dugum(f"kat{k}_sw", "switch", f"Kat {k} PoE switch", guc=guc, erisim=True)
    a.dugum("ap_k2", "ap", "Kat 2 Wi-Fi AP", guc=guc, erisim=True)
    a.dugum("calisan_k1", "istemci", "Çalışan PC (kat 1)", bolge="personel")
    a.dugum("calisan_k2", "istemci", "Çalışan PC (kat 2)", bolge="personel")
    a.dugum("misafir_k2", "istemci", "Misafir (Wi-Fi)", bolge="misafir_wifi")

    a.bagla("internet", "hat_1", "hat_2", "evden_calisan", "bulut_yedek")
    for i in (1, 2):
        a.bagla(f"hat_{i}", f"router_{i}")
        a.bagla(f"router_{i}", f"fw_{i}")
    a.bagla("fw_1", "fw_2")  # HA bağlantısı
    for f in ("fw_1", "fw_2"):
        a.bagla(f, "core_1", "core_2", "dmz_sw_1", "dmz_sw_2")
    a.bagla("core_1", "core_2")
    for d in ("dmz_sw_1", "dmz_sw_2"):
        a.bagla(d, "waf", "web_sunucu", "odeme_sayfasi")
    for c in ("core_1", "core_2"):
        a.bagla(c, "kat1_sw", "kat2_sw", "ad", "dhcp_dns", "nac_radius",
                "veritabani", "nas", "zabbix", "siem")
    a.bagla("kat1_sw", "calisan_k1")
    a.bagla("kat2_sw", "ap_k2", "calisan_k2")
    a.bagla("ap_k2", "misafir_k2")

    gereksinimler = [
        Gereksinim("internet", ("web_sunucu",), "Web sitesi internetten erişilebilir olmalı"),
        Gereksinim("internet", ("odeme_sayfasi",), "Ödeme sayfası internetten erişilebilir olmalı"),
        Gereksinim("web_sunucu", ("veritabani",), "Web sunucu veritabanına ulaşabilmeli"),
        Gereksinim("odeme_sayfasi", ("veritabani",), "Ödeme sayfası veritabanına ulaşabilmeli"),
        Gereksinim("calisan_k1", ("internet",), "Kat 1 çalışanı internete çıkabilmeli"),
        Gereksinim("calisan_k2", ("ad",), "Kat 2 çalışanı AD'ye ulaşabilmeli"),
        Gereksinim("misafir_k2", ("internet",), "Misafir internete çıkabilmeli"),
        Gereksinim("evden_calisan", ("ad",), "Evden çalışan VPN ile AD'ye ulaşabilmeli"),
        Gereksinim("nas", ("bulut_yedek",), "NAS, ofis dışı yedeğe (bulut) yazabilmeli"),
    ]
    kurallar = [
        izin("personel", "sunucu"),
        izin("personel", "internet", *WEB),
        izin("uzaktan_vpn", "sunucu", KERBEROS, LDAP, HTTPS, aciklama="VPN kullanıcısı sınırlı portlar"),
        izin("misafir_wifi", "internet", *WEB),
        izin("internet", "dmz", HTTP, HTTPS),
        izin("dmz", "sunucu", MYSQL, aciklama="web/ödeme -> veritabanı: tek yön, tek port"),
        izin("sunucu", "bulut", HTTPS, aciklama="ofis dışı yedek"),
        izin("sunucu", "internet", *WEB),
        izin("yonetim", "*"),
    ]
    engeller = [
        Engel("misafir_wifi", "sunucu", None, "misafir veritabanına ulaşamaz"),
        Engel("misafir_wifi", "dmz", None, "misafir DMZ'ye bağlanamaz"),
        Engel("internet", "sunucu", None, "internetten veritabanına doğrudan erişim yok"),
        Engel("dmz", "sunucu", LDAP, "DMZ, AD'ye erişemez (sadece 3306 açık)"),
        Engel("dmz", "sunucu", 22, "DMZ, iç ağda SSH deneyemez"),
        Engel("uzaktan_vpn", "yonetim", None, "VPN kullanıcısı yönetim ağına giremez"),
    ]
    return Senaryo("eticaret", "Senaryo 2: E-ticaret (çift hat, çift firewall, çift core)",
                   a.g, gereksinimler, kurallar, engeller)


# ---------------------------------------------------------------------------
# Senaryo 3: Üniversite kampüsü (üç bina)
# ---------------------------------------------------------------------------
def universite() -> Senaryo:
    guc = ("sebeke", "jenerator")
    a = _Ag()
    a.dugum("internet", "internet", "İnternet", bolge="internet")
    a.dugum("hat_1", "hat", "Fiber hat")
    a.dugum("router_1", "router", "ONT/Edge Router", guc=guc)
    a.dugum("fw_1", "firewall", "Firewall", guc=guc)
    a.dugum("core_1", "core", "Core switch", guc=guc)
    a.dugum("dmz_sw", "switch", "DMZ switch", guc=guc)
    a.dugum("web_sunucu", "sunucu", "Web sunucu", bolge="dmz", guc=guc)
    a.dugum("eposta", "sunucu", "E-posta", bolge="dmz", guc=guc)
    for s, et in (("ad", "Active Directory"), ("dhcp_dns", "DHCP/DNS"),
                  ("nac_radius", "NAC/Radius"), ("nas", "NAS (yedek)")):
        a.dugum(s, "sunucu", et, bolge="sunucu", guc=guc)
    a.dugum("ogrenci_isleri_db", "sunucu", "Öğrenci işleri DB", bolge="ogrenci_isleri", guc=guc)
    a.dugum("zabbix", "yonetim", "Zabbix", bolge="yonetim", guc=guc)
    a.dugum("siem", "yonetim", "SIEM", bolge="yonetim", guc=guc)
    for b, et in (("idari_sw", "İdari bina switch"), ("derslik_sw", "Derslik binası switch"),
                  ("yurt_sw", "Yurt PoE switch")):
        a.dugum(b, "switch", et, guc=guc, erisim=True)
    a.dugum("yurt_ap", "ap", "Yurt Wi-Fi AP", guc=guc, erisim=True)
    a.dugum("personel_pc", "istemci", "Personel PC", bolge="personel")
    a.dugum("ogrenci_isleri_pc", "istemci", "Yetkili personel PC", bolge="yetkili_personel")
    a.dugum("projeksiyon", "istemci", "Projeksiyon", bolge="lab_derslik")
    a.dugum("lab_pc", "istemci", "Laboratuvar PC", bolge="lab_derslik")
    a.dugum("ogrenci_cihazi", "istemci", "Öğrenci cihazı (Wi-Fi)", bolge="ogrenci")

    a.bagla("internet", "hat_1")
    a.bagla("hat_1", "router_1")
    a.bagla("router_1", "fw_1")
    a.bagla("fw_1", "core_1", "dmz_sw")
    a.bagla("dmz_sw", "web_sunucu", "eposta")
    a.bagla("core_1", "idari_sw", "derslik_sw", "yurt_sw", "ad", "dhcp_dns",
            "nac_radius", "nas", "ogrenci_isleri_db", "zabbix", "siem")
    a.bagla("idari_sw", "personel_pc", "ogrenci_isleri_pc")
    a.bagla("derslik_sw", "projeksiyon", "lab_pc")
    a.bagla("yurt_sw", "yurt_ap")
    a.bagla("yurt_ap", "ogrenci_cihazi")

    gereksinimler = [
        Gereksinim("internet", ("web_sunucu",), "Üniversite web sitesi dışarıdan erişilebilir olmalı"),
        Gereksinim("internet", ("eposta",), "E-posta sunucusu dışarıdan erişilebilir olmalı"),
        Gereksinim("ogrenci_isleri_pc", ("ogrenci_isleri_db",), "Yetkili personel öğrenci işleri DB'ye ulaşabilmeli"),
        Gereksinim("lab_pc", ("ad",), "Laboratuvar PC'leri AD ile giriş yapabilmeli"),
        Gereksinim("ogrenci_cihazi", ("internet",), "Öğrenci Wi-Fi'dan internete çıkabilmeli"),
        Gereksinim("ogrenci_cihazi", ("dhcp_dns",), "Öğrenci cihazı IP ve DNS alabilmeli"),
    ]
    kurallar = [
        izin("yetkili_personel", "ogrenci_isleri", MYSQL, aciklama="sadece yetkili personel"),
        izin("yetkili_personel", "sunucu"),
        izin("yetkili_personel", "internet", *WEB),
        izin("personel", "sunucu"),
        izin("personel", "internet", *WEB),
        izin("lab_derslik", "sunucu", DNS, DHCP, KERBEROS, LDAP, RADIUS),
        izin("lab_derslik", "internet", *WEB),
        izin("ogrenci", "internet", *WEB, aciklama="öğrenci sadece internete çıkar"),
        izin("ogrenci", "sunucu", DNS, DHCP, aciklama="sadece IP/DNS almak için"),
        izin("ogrenci", "dmz", HTTP, HTTPS),
        izin("sunucu", "internet", *WEB),
        izin("internet", "dmz", HTTP, HTTPS, SMTP),
        izin("yonetim", "*"),
    ]
    engeller = [
        Engel("ogrenci", "ogrenci_isleri", None, "öğrenci öğrenci işleri verisine erişemez"),
        Engel("ogrenci", "personel", None, "öğrenci personel ağına erişemez"),
        Engel("ogrenci", "yonetim", None, "öğrenci yönetim ağına erişemez"),
        Engel("ogrenci", "sunucu", LDAP, "öğrenci AD'ye doğrudan bağlanamaz"),
        Engel("personel", "ogrenci_isleri", None, "yetkisiz personel öğrenci işleri DB'ye erişemez"),
        Engel("lab_derslik", "ogrenci_isleri", None, "laboratuvar öğrenci işleri DB'ye erişemez"),
        Engel("internet", "ogrenci_isleri", None, "internetten DB'ye erişim yok"),
        Engel("dmz", "ogrenci_isleri", None, "DMZ'den DB'ye erişim yok"),
    ]
    return Senaryo("universite", "Senaryo 3: Üniversite kampüsü (üç bina)", a.g,
                   gereksinimler, kurallar, engeller)


# ---------------------------------------------------------------------------
# Senaryo 4: Hastane (7/24, her katman yedekli, DR sitesi)
# ---------------------------------------------------------------------------
def hastane() -> Senaryo:
    guc = ("sebeke_1", "sebeke_2", "jenerator")
    a = _Ag()
    a.dugum("internet", "internet", "İnternet", bolge="internet")
    a.dugum("dr_sitesi", "dis", "DR sitesi (başka şehir)", bolge="dr_sitesi")
    for i in (1, 2):
        a.dugum(f"hat_{i}", "hat", f"Hat {i} (ISP {i})")
        a.dugum(f"router_{i}", "router", f"ONT/Router {i}", guc=guc)
        a.dugum(f"fw_{i}", "firewall", f"Firewall {i}", guc=guc)
        a.dugum(f"core_{i}", "core", f"Core switch {i}", guc=guc)
        a.dugum(f"dmz_sw_{i}", "switch", f"DMZ switch {i}", guc=guc)
    a.dugum("waf", "sunucu", "WAF", bolge="dmz", guc=guc)
    a.dugum("randevu_sitesi", "sunucu", "Randevu sitesi", bolge="dmz", guc=guc)
    for s, et in (("hbys_1", "HBYS 1"), ("hbys_2", "HBYS 2"), ("pacs_1", "PACS 1"),
                  ("pacs_2", "PACS 2"), ("ad", "Active Directory"), ("dhcp_dns", "DHCP/DNS"),
                  ("nac_radius", "NAC/Radius"), ("san", "Depolama (SAN)")):
        a.dugum(s, "sunucu", et, bolge="sunucu", guc=guc)
    a.dugum("zabbix", "yonetim", "Zabbix", bolge="yonetim", guc=guc)
    a.dugum("siem", "yonetim", "SIEM", bolge="yonetim", guc=guc)
    for k, et in ((1, "Acil"), (2, "Poliklinik/Lab"), (3, "Yoğun bakım"), (4, "Ameliyathane")):
        a.dugum(f"kat{k}_sw", "switch", f"Kat {k} PoE switch ({et})", guc=guc, erisim=True)
    a.dugum("ap_hasta", "ap", "Hasta Wi-Fi AP", guc=guc, erisim=True)
    a.dugum("acil_pc", "istemci", "Acil hekim PC", bolge="hekim")
    a.dugum("poliklinik_pc", "istemci", "Poliklinik hekim PC", bolge="hekim")
    a.dugum("yb_monitor", "istemci", "Yoğun bakım monitörü", bolge="tibbi_cihaz")
    a.dugum("ameliyat_cihazi", "istemci", "Ameliyathane cihazı", bolge="tibbi_cihaz")
    a.dugum("hasta_telefonu", "istemci", "Hasta/ziyaretçi (Wi-Fi)", bolge="hasta_wifi")

    a.bagla("internet", "hat_1", "hat_2")
    for i in (1, 2):
        a.bagla(f"hat_{i}", f"router_{i}")
        a.bagla(f"router_{i}", f"fw_{i}")
    a.bagla("fw_1", "fw_2")  # HA bağlantısı
    for f in ("fw_1", "fw_2"):
        a.bagla(f, "core_1", "core_2", "dmz_sw_1", "dmz_sw_2", "dr_sitesi")
    a.bagla("core_1", "core_2")
    for d in ("dmz_sw_1", "dmz_sw_2"):
        a.bagla(d, "waf", "randevu_sitesi")
    for c in ("core_1", "core_2"):
        a.bagla(c, "kat1_sw", "kat2_sw", "kat3_sw", "kat4_sw", "hbys_1", "hbys_2",
                "pacs_1", "pacs_2", "ad", "dhcp_dns", "nac_radius", "san", "zabbix", "siem")
    a.bagla("kat1_sw", "acil_pc")
    a.bagla("kat2_sw", "poliklinik_pc", "ap_hasta")
    a.bagla("kat3_sw", "yb_monitor")
    a.bagla("kat4_sw", "ameliyat_cihazi")
    a.bagla("ap_hasta", "hasta_telefonu")

    hbys, pacs = ("hbys_1", "hbys_2"), ("pacs_1", "pacs_2")
    gereksinimler = [
        Gereksinim("internet", ("randevu_sitesi",), "Randevu sitesi internetten erişilebilir olmalı"),
        Gereksinim("randevu_sitesi", hbys, "Randevu sitesi HBYS kümesine ulaşabilmeli"),
        Gereksinim("acil_pc", hbys, "Acil hekimi HBYS'ye ulaşabilmeli"),
        Gereksinim("acil_pc", pacs, "Acil hekimi PACS görüntülerine ulaşabilmeli"),
        Gereksinim("poliklinik_pc", hbys, "Poliklinik hekimi HBYS'ye ulaşabilmeli"),
        Gereksinim("yb_monitor", hbys, "Yoğun bakım monitörü HBYS'ye veri gönderebilmeli"),
        Gereksinim("ameliyat_cihazi", pacs, "Ameliyathane cihazı PACS'e ulaşabilmeli"),
        Gereksinim("hasta_telefonu", ("internet",), "Hasta Wi-Fi'dan internete çıkabilmeli"),
        Gereksinim("san", ("dr_sitesi",), "Depolama DR sitesine replikasyon yapabilmeli"),
    ]
    kurallar = [
        izin("hekim", "sunucu", HTTPS, DICOM, DICOM_TLS, KERBEROS, LDAP, DNS, DHCP,
             aciklama="HBYS, PACS, AD"),
        izin("hekim", "internet", *WEB),
        izin("tibbi_cihaz", "sunucu", DICOM, DICOM_TLS, HTTPS, aciklama="sadece ilgili sunucular"),
        izin("hasta_wifi", "internet", *WEB),
        izin("internet", "dmz", HTTPS),
        izin("dmz", "sunucu", HTTPS, aciklama="randevu -> HBYS: tek yön, tek port"),
        izin("sunucu", "dr_sitesi", REPLIKASYON, aciklama="DR replikasyonu"),
        izin("dr_sitesi", "sunucu", REPLIKASYON),
        izin("yonetim", "*"),
    ]
    engeller = [
        Engel("hasta_wifi", "sunucu", None, "hasta Wi-Fi'ı HBYS/PACS'e erişemez"),
        Engel("hasta_wifi", "hekim", None, "hasta Wi-Fi'ı hekim ağına erişemez"),
        Engel("hasta_wifi", "yonetim", None, "hasta Wi-Fi'ı yönetim ağına erişemez"),
        Engel("tibbi_cihaz", "internet", None, "tıbbi cihazlar internete kapalı"),
        Engel("tibbi_cihaz", "hekim", None, "tıbbi cihaz hekim PC'lerine erişemez"),
        Engel("internet", "sunucu", None, "internetten HBYS/PACS'e doğrudan erişim yok"),
        Engel("dmz", "sunucu", LDAP, "randevu sitesi AD'ye erişemez"),
    ]
    return Senaryo("hastane", "Senaryo 4: Hastane (7/24, tam yedekli, DR sitesi)", a.g,
                   gereksinimler, kurallar, engeller)


SENARYOLAR = {"ofis": ofis, "eticaret": eticaret, "universite": universite, "hastane": hastane}


def senaryo_al(ad: str) -> Senaryo:
    if ad not in SENARYOLAR:
        raise KeyError(f"Bilinmeyen senaryo: {ad}. Seçenekler: {', '.join(SENARYOLAR)}")
    return SENARYOLAR[ad]()


def tum_senaryolar() -> list:
    return [f() for f in SENARYOLAR.values()]
