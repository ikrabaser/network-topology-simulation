import networkx as nx
import pytest

from ag_motoru.ag_modelleri import SENARYOLAR, tum_senaryolar
from ag_motoru.erisim_matrisi import bolgeler


@pytest.mark.parametrize("s", tum_senaryolar(), ids=list(SENARYOLAR))
def test_graf_tek_parca(s):
    assert nx.is_connected(s.graf)


@pytest.mark.parametrize("s", tum_senaryolar(), ids=list(SENARYOLAR))
def test_gereksinim_dugumleri_var(s):
    for r in s.gereksinimler:
        for n in (r.kaynak,) + r.hedefler:
            assert n in s.graf, f"{s.ad}: {n} grafta yok"


@pytest.mark.parametrize("s", tum_senaryolar(), ids=list(SENARYOLAR))
def test_kural_bolgeleri_grafta_var(s):
    zonlar = set(bolgeler(s))
    kullanilan = {k.kaynak for k in s.kurallar} | {k.hedef for k in s.kurallar}
    kullanilan |= {e.kaynak for e in s.engeller} | {e.hedef for e in s.engeller}
    assert kullanilan - {"*"} <= zonlar


@pytest.mark.parametrize("s", tum_senaryolar(), ids=list(SENARYOLAR))
def test_izleme_dugumu_var(s):
    assert s.izleme_dugumu in s.graf
