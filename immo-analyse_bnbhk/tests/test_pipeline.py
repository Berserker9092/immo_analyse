"""Tests simples des fonctions de nettoyage.  """
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import convertir_prix, convertir_surface, convertir_dates, TYPES_BIEN


def test_prix_millions():
    assert convertir_prix("57.62 millions") == 57_620_000

def test_prix_avec_espaces_et_devise():
    assert convertir_prix("37 965 000 FCFA") == 37_965_000

def test_prix_texte_inutilisable():
    assert convertir_prix("à négocier") is None
    assert convertir_prix("None FCFA") is None

def test_prix_negatif_ou_absent():
    assert convertir_prix("-100") is None
    assert convertir_prix(None) is None

def test_surface_virgule_decimale():
    assert convertir_surface("28,4") == 28.4

def test_surface_invalide():
    assert convertir_surface("0") is None
    assert convertir_surface("quatre-vingt") is None

def test_dates_deux_formats():
    d = convertir_dates(pd.Series(["2023-05-12", "05/06/2018", "32/13/2024"]))
    assert d[0] == pd.Timestamp("2023-05-12")
    assert d[1] == pd.Timestamp("2018-06-05")      # JJ/MM/AAAA : 5 juin, pas 6 mai
    assert pd.isna(d[2])                           # date impossible -> vide

def test_synonyme_type_bien():
    assert TYPES_BIEN["appart"] == "Appartement"


if __name__ == "__main__":
    for nom, fonction in list(globals().items()):
        if nom.startswith("test_"):
            fonction()
            print("OK ", nom)
    print("Tous les tests passent.")
