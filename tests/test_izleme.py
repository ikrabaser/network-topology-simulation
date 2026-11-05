import socket
import threading

from ag_motoru.ag_modelleri import eticaret, hastane, ofis
from ag_motoru.mini_izleme import (ARIZALI, GUCSUZ, IZLEME_KAPALI, ULASILAMIYOR, UP, ag_izleme,
                                   alarmlar, durum_degisimleri, tcp_kontrol)


def test_saglam_agda_her_sey_up():
    d = ag_izleme(ofis())
    assert set(d.values()) == {UP}
    assert alarmlar(d) == []


def test_ofiste_core_dusunce_izleme_koerlesir():
    """Ofiste Zabbix core'un arkasında: core düşünce firewall dahil hiçbir şey görünmez."""
    d = ag_izleme(ofis(), bozuklar=("core_1",))
    assert d["core_1"] == ARIZALI
    assert d["kat1_sw"] == ULASILAMIYOR and d["ad"] == ULASILAMIYOR
    assert d["fw_1"] == ULASILAMIYOR  # firewall çalışıyor ama Zabbix ona core'dan başka yoldan ulaşamaz


def test_yedekli_agda_tek_core_dusunce_izleme_gormeye_devam_eder():
    for s, core in ((hastane(), "core_1"), (eticaret(), "core_1")):
        d = ag_izleme(s, bozuklar=(core,))
        assert d[core] == ARIZALI
        assert [c for c, durum in d.items() if durum not in (UP, ARIZALI)] == []


def test_guc_kesintisinde_gucsuz_ve_izleme_kapali():
    d = ag_izleme(ofis(jenerator=False), bozuklar=("sebeke",))
    assert d["core_1"] == GUCSUZ and d["router_1"] == GUCSUZ
    assert d["hat_1"] == IZLEME_KAPALI  # zabbix de kapalı, hiçbir şey izlenemez


def test_alarm_ve_durum_degisimi():
    onceki = ag_izleme(hastane())
    sonraki = ag_izleme(hastane(), bozuklar=("hbys_1",))
    assert alarmlar(sonraki) == ["ALARM: hbys_1 -> ARIZALI"]
    assert durum_degisimleri(onceki, sonraki) == [("hbys_1", UP, ARIZALI)]


def test_tcp_kontrol_ayakta_ve_kapali():
    sunucu = socket.socket()
    sunucu.bind(("127.0.0.1", 0))
    sunucu.listen(1)
    port = sunucu.getsockname()[1]
    t = threading.Thread(target=lambda: sunucu.accept()[0].close(), daemon=True)
    t.start()
    ok, ms = tcp_kontrol("127.0.0.1", port)
    assert ok is True and ms is not None and ms >= 0
    t.join(timeout=2)
    sunucu.close()
    ok, ms = tcp_kontrol("127.0.0.1", port, zaman_asimi=0.5)
    assert ok is False and ms is None
