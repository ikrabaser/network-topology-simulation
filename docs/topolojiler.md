# Ağ topolojileri

Bu dosya `python main.py diyagram` komutuyla modelden otomatik üretilir.
Yuvarlak: internet/dış, dörtgen: ağ cihazı, altıgen: firewall, silindir: sunucu, yuvarlak köşeli: uç cihaz.

## Senaryo 1: Üç katlı ofis (tek hat)

```mermaid
flowchart TB
    internet(("İnternet"))
    hat_1["Fiber hat"]
    router_1["ONT / Edge Router"]
    fw_1{{"Firewall"}}
    core_1["Core switch"]
    dmz_sw["DMZ switch"]
    web_sunucu[("Web sunucu")]
    eposta[("E-posta")]
    kat1_sw["Kat 1 PoE switch"]
    kat2_sw["Kat 2 PoE switch"]
    kat3_sw["Kat 3 PoE switch"]
    ad[("Active Directory")]
    dhcp_dns[("DHCP/DNS")]
    nac_radius[("NAC/Radius")]
    nas[("NAS (yedek)")]
    zabbix[("Zabbix")]
    siem[("SIEM")]
    ap_k2(["Kat 2 Wi-Fi AP"])
    pc_k1("PC")
    telefon_k1("IP telefon")
    personel_k2("Personel (Wi-Fi)")
    misafir_k2("Misafir (Wi-Fi)")
    yazici_k3("Yazıcı")
    kamera_k3("Kamera")
    internet --- hat_1
    hat_1 --- router_1
    router_1 --- fw_1
    fw_1 --- core_1
    fw_1 --- dmz_sw
    core_1 --- kat1_sw
    core_1 --- kat2_sw
    core_1 --- kat3_sw
    core_1 --- ad
    core_1 --- dhcp_dns
    core_1 --- nac_radius
    core_1 --- nas
    core_1 --- zabbix
    core_1 --- siem
    dmz_sw --- web_sunucu
    dmz_sw --- eposta
    kat1_sw --- pc_k1
    kat1_sw --- telefon_k1
    kat2_sw --- ap_k2
    kat3_sw --- yazici_k3
    kat3_sw --- kamera_k3
    ap_k2 --- personel_k2
    ap_k2 --- misafir_k2
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
    class core_1,dmz_sw,kat1_sw,kat2_sw,kat3_sw,ap_k2 core
    class internet dis
    class fw_1 fw
    class hat_1,router_1 hat
    class pc_k1,telefon_k1,personel_k2,misafir_k2,yazici_k3,kamera_k3 istemci
    class web_sunucu,eposta,ad,dhcp_dns,nac_radius,nas sunucu
    class zabbix,siem yonetim
```

## Senaryo 2: E-ticaret (çift hat, çift firewall, çift core)

```mermaid
flowchart TB
    internet(("İnternet"))
    evden_calisan("Evden çalışan (VPN)")
    bulut_yedek(("Bulut yedek"))
    hat_1["Hat 1"]
    router_1["ONT/Router 1"]
    fw_1{{"Firewall 1"}}
    core_1["Core switch 1"]
    dmz_sw_1["DMZ switch 1"]
    hat_2["Hat 2"]
    router_2["ONT/Router 2"]
    fw_2{{"Firewall 2"}}
    core_2["Core switch 2"]
    dmz_sw_2["DMZ switch 2"]
    waf[("WAF")]
    web_sunucu[("Web sunucu")]
    odeme_sayfasi[("Ödeme sayfası")]
    ad[("Active Directory")]
    dhcp_dns[("DHCP/DNS")]
    nac_radius[("NAC/Radius")]
    veritabani[("Veritabanı")]
    nas[("NAS (yedek)")]
    zabbix[("Zabbix")]
    siem[("SIEM")]
    kat1_sw["Kat 1 PoE switch"]
    kat2_sw["Kat 2 PoE switch"]
    ap_k2(["Kat 2 Wi-Fi AP"])
    calisan_k1("Çalışan PC (kat 1)")
    calisan_k2("Çalışan PC (kat 2)")
    misafir_k2("Misafir (Wi-Fi)")
    internet --- hat_1
    internet --- hat_2
    internet --- evden_calisan
    internet --- bulut_yedek
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
    core_1 --- ad
    core_1 --- dhcp_dns
    core_1 --- nac_radius
    core_1 --- veritabani
    core_1 --- nas
    core_1 --- zabbix
    core_1 --- siem
    dmz_sw_1 --- fw_2
    dmz_sw_1 --- waf
    dmz_sw_1 --- web_sunucu
    dmz_sw_1 --- odeme_sayfasi
    hat_2 --- router_2
    router_2 --- fw_2
    fw_2 --- core_2
    fw_2 --- dmz_sw_2
    core_2 --- kat1_sw
    core_2 --- kat2_sw
    core_2 --- ad
    core_2 --- dhcp_dns
    core_2 --- nac_radius
    core_2 --- veritabani
    core_2 --- nas
    core_2 --- zabbix
    core_2 --- siem
    dmz_sw_2 --- waf
    dmz_sw_2 --- web_sunucu
    dmz_sw_2 --- odeme_sayfasi
    kat1_sw --- calisan_k1
    kat2_sw --- ap_k2
    kat2_sw --- calisan_k2
    ap_k2 --- misafir_k2
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
    class core_1,dmz_sw_1,core_2,dmz_sw_2,kat1_sw,kat2_sw,ap_k2 core
    class internet,bulut_yedek dis
    class fw_1,fw_2 fw
    class hat_1,router_1,hat_2,router_2 hat
    class evden_calisan,calisan_k1,calisan_k2,misafir_k2 istemci
    class waf,web_sunucu,odeme_sayfasi,ad,dhcp_dns,nac_radius,veritabani,nas sunucu
    class zabbix,siem yonetim
```

## Senaryo 3: Üniversite kampüsü (üç bina)

```mermaid
flowchart TB
    internet(("İnternet"))
    hat_1["Fiber hat"]
    router_1["ONT/Edge Router"]
    fw_1{{"Firewall"}}
    core_1["Core switch"]
    dmz_sw["DMZ switch"]
    web_sunucu[("Web sunucu")]
    eposta[("E-posta")]
    ad[("Active Directory")]
    dhcp_dns[("DHCP/DNS")]
    nac_radius[("NAC/Radius")]
    nas[("NAS (yedek)")]
    ogrenci_isleri_db[("Öğrenci işleri DB")]
    zabbix[("Zabbix")]
    siem[("SIEM")]
    idari_sw["İdari bina switch"]
    derslik_sw["Derslik binası switch"]
    yurt_sw["Yurt PoE switch"]
    yurt_ap(["Yurt Wi-Fi AP"])
    personel_pc("Personel PC")
    ogrenci_isleri_pc("Yetkili personel PC")
    projeksiyon("Projeksiyon")
    lab_pc("Laboratuvar PC")
    ogrenci_cihazi("Öğrenci cihazı (Wi-Fi)")
    internet --- hat_1
    hat_1 --- router_1
    router_1 --- fw_1
    fw_1 --- core_1
    fw_1 --- dmz_sw
    core_1 --- idari_sw
    core_1 --- derslik_sw
    core_1 --- yurt_sw
    core_1 --- ad
    core_1 --- dhcp_dns
    core_1 --- nac_radius
    core_1 --- nas
    core_1 --- ogrenci_isleri_db
    core_1 --- zabbix
    core_1 --- siem
    dmz_sw --- web_sunucu
    dmz_sw --- eposta
    idari_sw --- personel_pc
    idari_sw --- ogrenci_isleri_pc
    derslik_sw --- projeksiyon
    derslik_sw --- lab_pc
    yurt_sw --- yurt_ap
    yurt_ap --- ogrenci_cihazi
    classDef dis fill:#e8e8e8,stroke:#666,color:#111
    classDef hat fill:#fff3cd,stroke:#b8860b,color:#111
    classDef fw fill:#e0d4f7,stroke:#6f42c1,color:#111
    classDef core fill:#d0e4f7,stroke:#1f6fb2,color:#111
    classDef sunucu fill:#d4f1e6,stroke:#1d8a63,color:#111
    classDef yonetim fill:#fde2e2,stroke:#c0392b,color:#111
    classDef istemci fill:#f5f5f5,stroke:#999,color:#111
    classDef bozuk fill:#f8b4b4,stroke:#c0392b,stroke-width:3px,color:#111
    classDef gucsuz fill:#fde7b0,stroke:#e67e22,stroke-width:3px,stroke-dasharray:4 3,color:#111
    class core_1,dmz_sw,idari_sw,derslik_sw,yurt_sw,yurt_ap core
    class internet dis
    class fw_1 fw
    class hat_1,router_1 hat
    class personel_pc,ogrenci_isleri_pc,projeksiyon,lab_pc,ogrenci_cihazi istemci
    class web_sunucu,eposta,ad,dhcp_dns,nac_radius,nas,ogrenci_isleri_db sunucu
    class zabbix,siem yonetim
```

## Senaryo 4: Hastane (7/24, tam yedekli, DR sitesi)

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

