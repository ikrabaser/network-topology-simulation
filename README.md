# Ağ Topolojisi Simülasyonu

**Türkçe** · [English](README.en.md)

Ağ mimarilerini (ofis, e-ticaret, üniversite, hastane) **graf olarak modelleyen** ve üzerinde şunları deneyen bir Python projesi:

- **Hata simülasyonu:** bir cihaz, kablo ya da güç kaynağı bozulursa hangi erişimler kopar? Tek hata noktaları (SPOF) hangileri?
- **VLAN erişim matrisi:** hangi bölge hangi bölgeye hangi portla erişebilir? Varsayılan red mantığıyla.
- **Mini SIEM:** farklı cihazların loglarını okur, olayları ilişkilendirir, alarm üretir.
- **Mini izleme:** Zabbix mantığıyla, izleme düğümü her cihaza ulaşabiliyor mu?
- **Django web arayüzü:** hepsini tarayıcıdan dener, diyagramı çizer, bozulan cihazı kırmızı gösterir.
- **Veritabanı ve admin paneli:** topoloji, kablolar, gereksinimler, VLAN kuralları SQLite'ta tutulur; admin panelinden düzenlenir, yeni senaryo eklenir.
- **Hesaplar ve geçmiş:** kayıt/giriş vardır; çalıştırılan simülasyonlar kullanıcıya özel geçmişe kaydedilir.
- **REST API:** aynı hesaplamalar JSON olarak (Django REST framework).

![Senaryolar sayfası: dört senaryo, her birinin tek hata noktası sayısı](docs/img/ana-sayfa.png)

## Mimari

Motor (`ag_motoru/`) Django'dan bağımsız saf Python + NetworkX'tir. Komut satırı motoru doğrudan, web arayüzü ve REST API ise `servis.py` üzerinden kullanır; senaryolar veritabanında durur ve `yukle.py` ile motorun grafına çevrilir.

```mermaid
flowchart LR
    subgraph arayuz["Arayüzler"]
        cli["main.py<br/>komut satırı"]
        web["simulasyon/<br/>web arayüzü + admin"]
        api["simulasyon/api.py<br/>REST API"]
    end
    subgraph katman["Django katmanı"]
        servis["servis.py<br/>hesaplama ve kayıt"]
        yukle["yukle.py<br/>veritabanı ↔ motor"]
        db[("SQLite<br/>senaryolar, kullanıcılar, geçmiş")]
    end
    subgraph motor["ag_motoru/ (saf Python + NetworkX)"]
        modeller["ag_modelleri<br/>4 senaryonun grafı"]
        hata["hata_simulasyonu<br/>hata ve tek hata noktası"]
        erisim["erisim_matrisi<br/>VLAN kuralları"]
        izleme["mini_izleme<br/>cihaz durumu"]
        diyagram["mermaid_uret<br/>diyagram üretimi"]
        siem["mini_siem<br/>log korelasyonu"]
        loglar["ornek_log_uret<br/>örnek loglar"]
    end
    modeller --> hata
    hata --> erisim
    hata --> izleme
    modeller --> diyagram
    loglar -.-> siem
    cli --> modeller
    web --> servis
    api --> servis
    servis --> yukle
    yukle --> db
    yukle --> motor
    servis --> motor
```

## Kurulum

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate                # veritabanını (db.sqlite3) oluşturur
python manage.py seed_senaryolar        # dört yerleşik senaryoyu veritabanına yükler
python manage.py createsuperuser        # admin paneli için (isteğe bağlı)
python manage.py runserver
```

Tarayıcıda `http://127.0.0.1:8000` açılır. `seed_senaryolar` var olan senaryoyu değiştirmez (elle yaptığınız düzenlemeler korunur); kodla yazılmış hâline döndürmek için `python manage.py seed_senaryolar ofis --yenile` çalıştırın. Simülasyon geçmişi `--yenile` ile silinmez. Diyagramlar Mermaid ile çizildiği için tarayıcının internete erişebilmesi gerekir (kütüphane CDN'den yüklenir).

## Web arayüzü

| Sayfa | Ne yapar |
|---|---|
| `/` | Dört senaryo, her biri için tek hata noktası sayısı |
| `/senaryo/<kisa-ad>/` | Topoloji diyagramı, tek hata noktası tablosu, gereksinimler |
| `/senaryo/<kisa-ad>/hata/` | Cihaz/güç kaynağı seç, bozulunca ne koptuğunu gör; bozulanlar diyagramda kırmızı |
| `/senaryo/<kisa-ad>/erisim/` | VLAN matrisi, beklenen engellerin doğrulaması, uçtan uca sorgu |
| `/senaryo/<kisa-ad>/izleme/` | İzleme düğümü gözüyle cihaz durumları |
| `/siem/` | Log yapıştır ya da yükle, alarmları gör (örnek loglar giriş gerektirmez; kendi logunuz için giriş gerekir) |
| `/gecmis/` | Giriş yapan kullanıcının kayıtlı simülasyonları |
| `/hesap/giris/`, `/hesap/kayit/` | Giriş ve kayıt |
| `/admin/` | Senaryo düzenleme (yönetici hesabı) |
| `/api/` | REST API |

Yerleşik senaryoların kısa adları: `ofis`, `eticaret`, `universite`, `hastane`. Admin panelinden eklediğiniz senaryo da kendi kısa adıyla aynı sayfalarda açılır.

### Hata simülasyonu

Hastane senaryosunda `core_1` tek başına bozulunca hiçbir gereksinim kopmaz; `core_1` ve `core_2` birlikte bozulunca 8 gereksinim kopar. Sayfada bozulan cihazlar ayrıca diyagramda kırmızı gösterilir.

![Hata simülasyonu sayfası: core_1 ve core_2 seçili, 8 gereksinim koptu](docs/img/hata-simulasyonu.png)

### VLAN erişim matrisi ve uçtan uca sorgu

Öğrenci cihazından öğrenci işleri veritabanına kablo yolu vardır ama politika izin vermez; sonuç ENGEL'dir.

![Erişim matrisi sayfası: üniversite senaryosu, öğrenci cihazından veritabanına sorgu ENGEL](docs/img/erisim-matrisi.png)

### Mini SIEM

Saldırılı örnek log: 212 olay, 5 alarm.

![SIEM sayfası: örnek saldırılı log için 5 alarm](docs/img/siem-raporu.png)

## Veritabanı ve admin paneli

Senaryolar kodda değil veritabanında durur. `/admin/` altında bir senaryoyu açınca cihazlar, kablolar, gereksinimler, izin kuralları ve beklenen engeller tek sayfada düzenlenir; sayfanın üstünde tek hata noktası özeti ve tutarsızlık listesi (bağlantısız cihaz, olmayan bölgeye kural, olmayan izleme düğümü) görünür.

![Admin paneli: senaryo listesi, her senaryo için cihaz, kablo ve merkezi tek hata noktası sayısı](docs/img/admin-liste.png)

Hatalı topoloji kayda girmez: cihaz adı küçük harfle başlayan `a-z0-9_` olmalıdır ve Mermaid'in ayrılmış sözcükleri (`end`, `graph`, ...) yasaktır; bir cihaz kendine bağlanamaz, ters yönde ikinci kablo eklenemez, kablo ve gereksinimde yalnızca aynı senaryonun cihazları seçilebilir; port numaraları 1-65535 olmalıdır. Yeni bir cihaza kablo bağlamak için önce cihazı kaydedin, sonra kablo ekleyin.

Yerleşik dört senaryo, veritabanından yüklendiğinde kodla yazılmış hâliyle birebir aynı graf, gereksinim, kural ve analiz sonucunu verir (bu bir testle doğrulanır).

## Hesaplar ve geçmiş

Kayıt olup giriş yapınca hata, izleme ve erişim sayfalarında **Geçmişe kaydet** düğmesi görünür. Kayıt sırasında sonuç istemciden alınmaz, sunucuda yeniden hesaplanır. SIEM'de kendi logunuzu analiz ettiğinizde sonuç otomatik kaydedilir (logun kendisi saklanmaz, yalnızca kaynak adı, satır sayısı ve alarmlar). Her kullanıcı yalnızca kendi kayıtlarını görür ve silebilir.

![Geçmiş sayfası: kayıtlı hata, izleme, erişim ve SIEM sonuçları](docs/img/gecmis.png)

## REST API

Okuma ve hesaplama uçları herkese açıktır; sonucu kaydetmek, SIEM analizi ve geçmiş giriş ister. Giriş için tarayıcı oturumu ya da HTTP Basic kullanılır.

| Uç | GET | POST |
|---|---|---|
| `/api/senaryolar/` | senaryo listesi ve özetleri | |
| `/api/senaryolar/<kisa-ad>/` | cihazlar, kablolar, gereksinimler, tutarsızlıklar | |
| `/api/senaryolar/<kisa-ad>/analiz/` | tek hata noktası analizi | |
| `/api/senaryolar/<kisa-ad>/diyagram/` | Mermaid metni | |
| `/api/senaryolar/<kisa-ad>/hata/?bozuk=core_1&bozuk=core_2` | hata simülasyonu | aynı hesap + geçmişe kaydet (giriş) |
| `/api/senaryolar/<kisa-ad>/izleme/?bozuk=...` | izleme durumları | aynı + kaydet (giriş) |
| `/api/senaryolar/<kisa-ad>/erisim/` | VLAN matrisi; `?kaynak=&hedef=&port=` ile uçtan uca sorgu | sorgu + kaydet (giriş) |
| `/api/siem/` | | `{"log": "..."}` analiz + kaydet (giriş) |
| `/api/gecmis/`, `/api/gecmis/<id>/` | kendi kayıtların (`?tur=hata`) | DELETE ile silme |

Bilinmeyen cihaz adı ya da geçersiz port `400` döner; bilinmeyen senaryo `404`.

```powershell
curl.exe http://127.0.0.1:8000/api/senaryolar/
curl.exe "http://127.0.0.1:8000/api/senaryolar/hastane/hata/?bozuk=core_1&bozuk=core_2"
# kaydetmek için giriş gerekir (parolayı curl sorar)
'{"bozuk": ["core_1", "core_2"]}' | Out-File -Encoding ascii istek.json
curl.exe -u kullanici -X POST -H "Content-Type: application/json" -d "@istek.json" http://127.0.0.1:8000/api/senaryolar/hastane/hata/
```

## Komut satırı

Komut satırı veritabanını kullanmaz; kodla yazılmış dört yerleşik senaryo üzerinde çalışır.

```powershell
python main.py hata hastane                          # tek hata noktası raporu
python main.py hata hepsi
python main.py hata hastane --bozuk core_1,core_2    # birden fazla hatayı aynı anda dene
python main.py erisim universite                     # VLAN matrisi
python main.py erisim universite --sorgu ogrenci_cihazi ogrenci_isleri_db 3306
python main.py siem ornek_loglar/saldirili.log
python main.py izleme ofis --bozuk core_1
python main.py diyagram > docs/topolojiler.md        # Mermaid diyagramları
python main.py log-uret                              # örnek logları yeniden üret
```

## Nasıl çalışır (adım adım)

### 1. Ağ bir graftır

Cihazlar düğüm, kablolar kenardır. Her düğümün bir türü (`router`, `firewall`, `core`, `switch`, `sunucu`, `istemci`...), bir bölgesi (VLAN) ve çalışması için gereken güç kaynakları vardır. Her senaryo ayrıca **gereksinimleri** listeler:

```
acil_pc  ->  hbys_1 veya hbys_2     "Acil hekimi HBYS'ye ulaşabilmeli"
```

Hedef birden fazlaysa küme demektir: ikisinden birine ulaşmak yeter.

### 2. Bozma: düğümü graftan çıkar

Bozulan cihaz graftan silinir. Bir cihazın **bütün** güç kaynakları bozulursa o cihaz da kapanır (hastanede `sebeke_1`, `sebeke_2` ve `jenerator` üçü birden gitmeden hiçbir cihaz kapanmaz).

### 3. Ulaşılabilirlik: genişlik öncelikli arama

Kaynaktan başlanır, komşulara gidilir. Önemli kural: **sunucu ve istemciler uç cihazdır, trafik içlerinden geçmez.** Sadece router, firewall, switch gibi cihazlar geçiş yapabilir. Aksi halde iki core arasında "sunucu üzerinden" sahte bir köprü oluşurdu.

Aşağıdaki şema hastane senaryosundan alınmış sadeleştirilmiş bir parçadır (gerçek grafın alt grafı: acil hekim PC'si, kat 1 switch'i, iki core ve HBYS sunucuları). `core_1` bozulunca yol `core_2` üzerinden sürer:

```mermaid
flowchart TB
    core_1["Core switch 1"]
    core_2["Core switch 2"]
    acil_pc("Acil hekim PC")
    hbys_1[("HBYS 1")]
    kat1_sw["Kat 1 PoE switch (Acil)"]
    hbys_2[("HBYS 2")]
    core_1 --- core_2
    core_1 --- kat1_sw
    core_1 --- hbys_1
    core_1 --- hbys_2
    core_2 --- kat1_sw
    core_2 --- hbys_1
    core_2 --- hbys_2
    acil_pc --- kat1_sw
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
    class core_2,kat1_sw core
    class acil_pc istemci
    class hbys_1,hbys_2 sunucu
    class core_1 bozuk
```

`core_1` ve `core_2` birlikte bozulunca `kat1_sw`'nin gidecek komşusu kalmaz, `acil_pc` HBYS'ye ulaşamaz:

```mermaid
flowchart TB
    core_1["Core switch 1"]
    core_2["Core switch 2"]
    acil_pc("Acil hekim PC")
    hbys_1[("HBYS 1")]
    kat1_sw["Kat 1 PoE switch (Acil)"]
    hbys_2[("HBYS 2")]
    core_1 --- core_2
    core_1 --- kat1_sw
    core_1 --- hbys_1
    core_1 --- hbys_2
    core_2 --- kat1_sw
    core_2 --- hbys_1
    core_2 --- hbys_2
    acil_pc --- kat1_sw
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
    class kat1_sw core
    class acil_pc istemci
    class hbys_1,hbys_2 sunucu
    class core_1,core_2 bozuk
```

### 4. Tek hata noktası

Her cihaz, her güç kaynağı ve her kablo **tek tek** bozulur. Bir gereksinimi koparıyorsa o eleman tek hata noktasıdır. İki ayrım yapılır:

- **Merkezi:** firewall, core, hat gibi. Bozulunca ağın büyük kısmı etkilenir.
- **Erişim katmanı:** kat/bina switch'i ve Wi-Fi AP. Bozulunca sadece o kat/bina etkilenir; ayrı listelenir.

Bozulan elemanın kendisi gereksinimin uç noktasıysa (örn. PC bozulunca "PC internete çıkabilmeli" kopar) bu tasarım hatası sayılmaz, atlanır.

### 5. VLAN erişim matrisi

Kural: `kaynak bölge -> hedef bölge, portlar`. Eşleşen kural yoksa trafik engellenir. Aynı bölge içi serbesttir. `yonetim -> *` kuralı yönetim ağının her yeri izlemesini sağlar. Üniversite senaryosunun matrisi (satır → sütun; `TÜM` = bütün portlar, sayılar = sadece o portlar, `–` = engel):

| | internet | dmz | sunucu | ogrenci_isleri | yonetim | personel | yetkili_personel | lab_derslik | ogrenci |
|---|---|---|---|---|---|---|---|---|---|
| **internet** | TÜM | 25,80,443 | – | – | – | – | – | – | – |
| **dmz** | – | TÜM | – | – | – | – | – | – | – |
| **sunucu** | 53,80,443 | – | TÜM | – | – | – | – | – | – |
| **ogrenci_isleri** | – | – | – | TÜM | – | – | – | – | – |
| **yonetim** | TÜM | TÜM | TÜM | TÜM | TÜM | TÜM | TÜM | TÜM | TÜM |
| **personel** | 53,80,443 | – | TÜM | – | – | TÜM | – | – | – |
| **yetkili_personel** | 53,80,443 | – | TÜM | 3306 | – | – | TÜM | – | – |
| **lab_derslik** | 53,80,443 | – | 53,67,88,389,1812 | – | – | – | – | TÜM | – |
| **ogrenci** | 53,80,443 | 80,443 | 53,67 | – | – | – | – | – | TÜM |

Fiziksel yol ile politika ayrı kontrol edilir:

```
$ python main.py erisim universite --sorgu ogrenci_cihazi ogrenci_isleri_db 3306
ogrenci_cihazi (ogrenci) -> ogrenci_isleri_db (ogrenci_isleri) port 3306
  fiziksel yol : VAR
  politika izni: YOK
  sonuç        : ENGEL
```

Kablo yolu vardır ama kural engeller. Veritabanını DMZ'ye değil iç ağa koymak tek başına öğrenciyi durdurmaz; durduran VLAN ayrımı ve kuraldır.

### 6. Mini SIEM: olayları ilişkilendirme

Log satırları ayrıştırılır, kurallar uygulanır. Asıl iş **korelasyondur**: tek tek masum görünen olaylar birleşince saldırı olur. Örnek saldırılı logda alarm zinciri:

```mermaid
sequenceDiagram
    participant S as Saldırgan 203.0.113.50
    participant F as fw_1 (log kaynağı)
    participant M as Mini SIEM
    S->>F: 7 başarısız giriş (03:12:00 - 03:12:12)
    F->>M: AUTH FAIL logları
    Note over M: BRUTE_FORCE (YUKSEK)
    S->>F: admin_can ile başarılı giriş (03:12:45)
    F->>M: AUTH SUCCESS logu
    Note over M: BASARILI_GIRIS (KRITIK)<br/>başarısızlar + başarılı giriş birleşti
    S->>F: 4 aktarım, toplam 1000 MB (03:14:45 - 03:26:45)
    F->>M: TRANSFER logları
    Note over M: VERI_SIZINTISI (KRITIK)<br/>girişten sonra büyük veri aktarımı
```

`VERI_SIZINTISI` alarmı farklı log türlerini (`AUTH` ve `TRANSFER`) birleştirir: giriş olayı ile sonraki veri aktarımlarını tek kanıt zincirine bağlar. Ayrıca `PORT_TARAMA` ve `MESAI_DISI_ADMIN` kuralları vardır. Eşikler `Esikler` sınıfından değiştirilir. Seviyeler: `KRITIK`, `YUKSEK`, `ORTA`.

### 7. Mini izleme

İzleme düğümü (`zabbix`) her cihaza ulaşmayı dener. Durumlar: `UP`, `ARIZALI`, `GÜÇSÜZ`, `ULAŞILAMIYOR`, `İZLEME KAPALI`. Ayrıca `tcp_kontrol(host, port)` gerçek bir TCP bağlantısı dener (ping yönetici yetkisi istediği için TCP kullanılır).

## Bulgular

Dört senaryoda her şey tek tek bozulunca çıkan sonuçlar:

| Senaryo | Düğüm | Kablo | Denenen hata | Merkezi tek hata noktası | Erişim katmanı |
|---|---|---|---|---|---|
| Ofis (tek hat) | 24 | 23 | 42 | **9** | 8 |
| E-ticaret (çift hat/firewall/core) | 29 | 46 | 72 | **0** | 4 |
| Üniversite (üç bina) | 24 | 23 | 43 | **9** | 8 |
| Hastane (tam yedekli, DR) | 34 | 56 | 87 | **0** | 6 |

Modelleme sırasında çıkan iki ders:

1. **DMZ switch'i de tek hata noktası olabilir.** Ofis ve üniversitede `dmz_sw` listede çıkar: tek DMZ switch'i bozulunca web sitesine erişim kopar. Bu yüzden e-ticaret ve hastanede DMZ switch'i de çift (`dmz_sw_1`, `dmz_sw_2`) modellendi.
2. **İzleme sistemi de yedekli konumlanmalı.** Ofis ve üniversitede Zabbix tek core'un arkasında durur; core bozulunca izleme tamamen kör kalır (`0/22 cihaz UP`, firewall çalışıyor olsa bile). Hastane ve e-ticaretteki Zabbix iki core'a da bağlıdır, tek core düşünce her şeyi görmeye devam eder.

Güç tarafı: `ofis(jenerator=False)` ile jeneratörsüz ofis kurulursa `sebeke` merkezi tek hata noktası olarak listeye girer.

## Sınırlamalar

- Servis sağlayıcının kendi ağı modellenmez; "internet" tek bir bulut düğümüdür.
- WAF, DMZ'de trafiğin içinden geçmeyen uç cihaz olarak modellenir; IPS/IDS ise ayrı bir düğüm değil firewall'ın özelliğidir. Bu yüzden WAF'ın arızası ya da IPS'in trafiği kesmesi SPOF analizine girmez.
- Sunucu yedekliliği sadece gereksinimde birden fazla hedef (küme) listelenmişse ölçülür (hastanede HBYS/PACS). Tek hedefli sunucu (örn. e-ticaretteki `veritabani`) bozulursa bu bir tasarım hatası olarak raporlanmaz.
- Güç modeli "kaynaklardan biri yeter" mantığındadır; UPS'in dayanma süresi, ATS gecikmesi gibi zaman boyutu yoktur.
- VLAN politikası bölge düzeyindedir; cihaz bazında kural yoktur.
- SIEM eşikleri örnek değerlerdir, gerçek bir ağın trafiğine göre ayarlanmalıdır.
- Web arayüzü ve API yerel kullanım içindir: `SECRET_KEY` geliştirme anahtarıdır, herkes kayıt olabilir, HTTP Basic kimlik bilgisi şifrelenmeden gider ve istek sınırlaması yoktur. Başka bir ortamda `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` ve `ALLOWED_HOSTS` ayarlarıyla, HTTPS arkasında çalıştırın.
- Komut satırı veritabanındaki senaryoları değil, kodla yazılmış dört senaryoyu kullanır; admin panelinde yapılan düzenleme komut satırına yansımaz.

## Proje yapısı

```
ag_motoru/                 Django'dan bağımsız simülasyon motoru
  ag_modelleri.py          dört senaryonun grafı, gereksinimleri, VLAN kuralları
  hata_simulasyonu.py      tek hata noktası analizi, çoklu hata
  erisim_matrisi.py        VLAN matrisi, uçtan uca sorgu
  mini_siem.py             log ayrıştırma, korelasyon, alarm
  mini_izleme.py           izleme durumu, TCP kontrolü
  mermaid_uret.py          graftan Mermaid diyagramı
  ornek_log_uret.py        örnek log üretici
simulasyon/                Django uygulaması
  models.py                senaryo, cihaz, kablo, gereksinim, kural, engel, simülasyon geçmişi
  yukle.py                 veritabanı <-> motor dönüşümü
  servis.py                hesaplama ve geçmişe kayıt (web ve API ortak kullanır)
  views.py, urls.py        web sayfaları, giriş/kayıt, geçmiş
  api.py, api_urls.py      REST API
  admin.py                 senaryo düzenleme paneli
  management/commands/     seed_senaryolar komutu
  templates/, tests/       şablonlar ve testler
config/                    Django ayarları
tests/                     motor testleri (pytest)
ornek_loglar/              normal.log, saldirili.log
docs/topolojiler.md        dört senaryonun diyagramları
docs/img/                  README ekran görüntüleri
main.py                    komut satırı arayüzü
```

## Testler

```powershell
python -m pytest -q          # motor: 60 test
python manage.py test        # web, admin, API, hesap ve veritabanı: 106 test
```

Testler ayrıca "yedekli senaryoda merkezi tek hata noktası yok", "iki core birden düşünce kopar", "kablo yolu var ama politika engeller", "sunucu içinden geçiş yok" gibi mimari beklentileri doğrular.

## Hastane topolojisi

Diğer üç senaryo için bkz. [docs/topolojiler.md](docs/topolojiler.md).

```mermaid
flowchart TB
    internet(("İnternet"))
    dr_sitesi(("DR sitesi (başka şehir)"))
    hat_1["Hat 1 (ISP 1)"]
    router_1["ONT/Router 1"]
    fw_1{{"Firewall 1"}}
    core_1["Core switch 1"]
    dmz_sw_1["DMZ switch 1"]
    hat_2["Hat 2 (ISP 2)"]
    router_2["ONT/Router 2"]
    fw_2{{"Firewall 2"}}
    core_2["Core switch 2"]
    dmz_sw_2["DMZ switch 2"]
    waf[("WAF")]
    randevu_sitesi[("Randevu sitesi")]
    hbys_1[("HBYS 1")]
    hbys_2[("HBYS 2")]
    pacs_1[("PACS 1")]
    pacs_2[("PACS 2")]
    ad[("Active Directory")]
    dhcp_dns[("DHCP/DNS")]
    nac_radius[("NAC/Radius")]
    san[("Depolama (SAN)")]
    zabbix[("Zabbix")]
    siem[("SIEM")]
    kat1_sw["Kat 1 PoE switch (Acil)"]
    kat2_sw["Kat 2 PoE switch (Poliklinik/Lab)"]
    kat3_sw["Kat 3 PoE switch (Yoğun bakım)"]
    kat4_sw["Kat 4 PoE switch (Ameliyathane)"]
    ap_hasta(["Hasta Wi-Fi AP"])
    acil_pc("Acil hekim PC")
    poliklinik_pc("Poliklinik hekim PC")
    yb_monitor("Yoğun bakım monitörü")
    ameliyat_cihazi("Ameliyathane cihazı")
    hasta_telefonu("Hasta/ziyaretçi (Wi-Fi)")
    internet --- hat_1
    internet --- hat_2
    dr_sitesi --- fw_1
    dr_sitesi --- fw_2
    hat_1 --- router_1
    router_1 --- fw_1
    fw_1 --- fw_2
    fw_1 --- core_1
    fw_1 --- core_2
    fw_1 --- dmz_sw_1
    fw_1 --- dmz_sw_2
    core_1 --- fw_2
    core_1 --- core_2
    core_1 --- kat1_sw
    core_1 --- kat2_sw
    core_1 --- kat3_sw
    core_1 --- kat4_sw
    core_1 --- hbys_1
    core_1 --- hbys_2
    core_1 --- pacs_1
    core_1 --- pacs_2
    core_1 --- ad
    core_1 --- dhcp_dns
    core_1 --- nac_radius
    core_1 --- san
    core_1 --- zabbix
    core_1 --- siem
    dmz_sw_1 --- fw_2
    dmz_sw_1 --- waf
    dmz_sw_1 --- randevu_sitesi
    hat_2 --- router_2
    router_2 --- fw_2
    fw_2 --- core_2
    fw_2 --- dmz_sw_2
    core_2 --- kat1_sw
    core_2 --- kat2_sw
    core_2 --- kat3_sw
    core_2 --- kat4_sw
    core_2 --- hbys_1
    core_2 --- hbys_2
    core_2 --- pacs_1
    core_2 --- pacs_2
    core_2 --- ad
    core_2 --- dhcp_dns
    core_2 --- nac_radius
    core_2 --- san
    core_2 --- zabbix
    core_2 --- siem
    dmz_sw_2 --- waf
    dmz_sw_2 --- randevu_sitesi
    kat1_sw --- acil_pc
    kat2_sw --- poliklinik_pc
    kat2_sw --- ap_hasta
    kat3_sw --- yb_monitor
    kat4_sw --- ameliyat_cihazi
    ap_hasta --- hasta_telefonu
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
    class core_1,dmz_sw_1,core_2,dmz_sw_2,kat1_sw,kat2_sw,kat3_sw,kat4_sw,ap_hasta core
    class internet,dr_sitesi dis
    class fw_1,fw_2 fw
    class hat_1,router_1,hat_2,router_2 hat
    class acil_pc,poliklinik_pc,yb_monitor,ameliyat_cihazi,hasta_telefonu istemci
    class waf,randevu_sitesi,hbys_1,hbys_2,pacs_1,pacs_2,ad,dhcp_dns,nac_radius,san sunucu
    class zabbix,siem yonetim
```
