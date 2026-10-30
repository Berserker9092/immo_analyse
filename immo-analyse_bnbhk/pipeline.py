"""
ImmoAnalyse — Pipeline de nettoyage

Lancer :  python pipeline.py

Le pipeline fait 4 choses, dans cet ordre :
    1. CHARGER   : lire les 5 sources (CSV, Excel, JSON) et les empiler dans un seul tableau
    2. NETTOYER  : mettre prix, surface, date, type de bien... dans un format unique
    3. TRIER     : lignes inutilisables -> quarantaine ; les autres -> données propres
    4. DOUBLONS  : repérer (sans supprimer) les annonces qui se ressemblent

Résultat : 2 fichiers dans data/propre/  (donnees_propres.csv et quarantaine.csv)
"""

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# RÉGLAGES (tout ce qu'on peut vouloir changer est ici, pas dans le code)
# ----------------------------------------------------------------------
RACINE = Path(__file__).parent
RAW = RACINE / "data" / "raw"
SORTIE = RACINE / "data" / "propre"
REF_GEO = RACINE / "data" / "referentiels" / "referentiel_geographique.csv"

# Seuils : au-delà, la valeur est "bizarre" (avertissement), pas forcément fausse
SURFACE_MIN, SURFACE_MAX = 5, 2000                  # m²
PRIX_VENTE_MIN, PRIX_VENTE_MAX = 100_000, 2_000_000_000   # FCFA
LOYER_MIN, LOYER_MAX = 25_000, 5_000_000            # FCFA / mois
CHAMBRES_MAX_APPART = 10

# Les 7 types de biens autorisés, avec les écritures que l'on rencontre
TYPES_BIEN = {
    "appartement": "Appartement", "appart": "Appartement", "appt": "Appartement",
    "studio": "Studio",
    "chambre": "Chambre", "chambre simple": "Chambre",
    "villa": "Villa",
    "maison": "Maison",
    "terrain": "Terrain", "terrains": "Terrain",
    "local commercial": "Local commercial", "local": "Local commercial",
    "bureau": "Local commercial", "magasin": "Local commercial",
}
TRANSACTIONS = {
    "vente": "vente", "vendre": "vente", "achat": "vente",
    "location": "location", "louer": "location", "loyer": "location", "rent": "location",
}

# Colonnes du tableau final (le "schéma" commun aux 5 sources)
COLONNES = ["id_local", "source", "date", "type_transaction", "type_bien", "region",
            "ville", "prix", "surface", "chambres", "salles_bain", "statut"]


# ----------------------------------------------------------------------
# ÉTAPE 1 — CHARGER : chaque source a ses propres noms de colonnes,
# on les renomme tous pareil puis on empile.
# ----------------------------------------------------------------------
def charger_sources() -> pd.DataFrame:
    # Source 1 : CSV avec séparateur ";"
    plateforme = pd.read_csv(RAW / "plateforme_immo_sn.csv", sep=";", dtype=str).rename(columns={
        "ref_plateforme": "id_local", "date_mise_en_ligne": "date", "categorie": "type_bien",
        "commune": "ville", "pieces": "chambres", "sdb": "salles_bain"})

    # Source 2 : fichier Excel (feuille "Annonces"), que des ventes
    agence = pd.read_excel(RAW / "agence_teranga.xlsx", sheet_name="Annonces", dtype=str).rename(columns={
        "Code": "id_local", "Date": "date", "Region": "region", "Ville": "ville", "Type": "type_bien",
        "Prix_FCFA": "prix", "Surface_m2": "surface", "Chambres": "chambres", "SDB": "salles_bain",
        "Statut": "statut"})
    agence["type_transaction"] = "vente"

    # Source 3 : JSON imbriqué -> json_normalize "aplatit" les sous-dictionnaires
    with open(RAW / "particuliers.json", encoding="utf-8") as f:
        particuliers = pd.json_normalize(json.load(f)).rename(columns={
            "annonce.id": "id_local", "annonce.date": "date", "annonce.statut": "statut",
            "annonce.localisation.region": "region", "annonce.localisation.ville": "ville",
            "annonce.details.type": "type_bien", "annonce.details.transaction": "type_transaction",
            "annonce.details.prix": "prix", "annonce.details.surface": "surface",
            "annonce.details.chambres": "chambres", "annonce.details.sdb": "salles_bain"})

    # Source 4 : actes de notaires = ventes conclues
    notaires = pd.read_csv(RAW / "notaires.csv", dtype=str).rename(columns={
        "id_acte": "id_local", "date_acte": "date", "montant_fcfa": "prix",
        "superficie": "surface", "nb_chambres": "chambres"})
    notaires["type_transaction"] = "vente"

    # Source 5 : vieux CSV (séparateur ";" et encodage latin-1), ventes passées
    historique = pd.read_csv(RAW / "import_historique.csv", sep=";", encoding="latin-1", dtype=str).rename(columns={
        "ID": "id_local", "DateVente": "date", "Region": "region", "Ville": "ville", "TypeBien": "type_bien",
        "Prix": "prix", "Surface": "surface", "Chambres": "chambres", "SallesBain": "salles_bain"})
    historique["type_transaction"] = "vente"
    historique["statut"] = "Vendu"

    # On garde le nom de la source, puis on empile (colonnes absentes = vides)
    sources = {"plateforme": plateforme, "agence": agence, "particuliers": particuliers,
               "notaires": notaires, "historique": historique}
    for nom, tableau in sources.items():
        tableau["source"] = nom
        print(f"  {nom:13s}: {len(tableau):5d} lignes")
    return pd.concat(sources.values(), ignore_index=True)[COLONNES]


# ----------------------------------------------------------------------
# ÉTAPE 2 — NETTOYER : une petite fonction par type de donnée.
# Règle commune : si on n'arrive pas à comprendre la valeur, on renvoie None.
# ----------------------------------------------------------------------
def convertir_prix(valeur):
    """'57.62 millions' -> 57620000 | '37 965 000 FCFA' -> 37965000 | 'à négocier' -> None"""
    if pd.isna(valeur):
        return None
    texte = str(valeur).lower()
    facteur = 1_000_000 if "million" in texte else 1
    chiffres = re.sub(r"[^\d.,-]", "", texte).replace(",", ".")   # on ne garde que chiffres, . et -
    try:
        prix = float(chiffres) * facteur
    except ValueError:                                            # ex : "à négocier"
        return None
    return prix if prix > 0 else None


def convertir_surface(valeur):
    """'28,4' -> 28.4 | 'quatre-vingt' -> None | 0 -> None"""
    if pd.isna(valeur):
        return None
    chiffres = re.sub(r"[^\d.,]", "", str(valeur)).replace(",", ".")
    try:
        surface = float(chiffres)
    except ValueError:
        return None
    return surface if surface > 0 else None


def convertir_dates(colonne: pd.Series) -> pd.Series:
    """Les dates arrivent en '2020-07-03' (ISO) ou en '05/06/2018' (JJ/MM/AAAA)."""
    iso = pd.to_datetime(colonne, format="%Y-%m-%d", errors="coerce")
    francais = pd.to_datetime(colonne, format="%d/%m/%Y", errors="coerce")
    dates = iso.fillna(francais)                       # on prend le format qui a marché
    plausible = (dates.dt.year >= 1990) & (dates.dt.year <= date.today().year + 2)
    return dates.where(plausible)                      # date absurde -> vide


def nettoyer(brut: pd.DataFrame) -> pd.DataFrame:
    df = brut.copy()
    df["type_transaction"] = df["type_transaction"].str.strip().str.lower().map(TRANSACTIONS)
    df["type_bien"] = df["type_bien"].str.strip().str.lower().map(TYPES_BIEN)
    df["prix"] = df["prix"].apply(convertir_prix)
    df["surface"] = df["surface"].apply(convertir_surface)
    df["date"] = convertir_dates(df["date"])
    df["region"] = df["region"].str.strip().str.title()
    df["ville"] = df["ville"].str.strip().str.title()
    df["statut"] = df["statut"].str.strip().str.capitalize()
    # Chambres / salles de bain : en nombre, et une valeur négative n'a pas de sens
    for colonne in ["chambres", "salles_bain"]:
        nombre = pd.to_numeric(df[colonne], errors="coerce")
        df[colonne] = nombre.where(nombre >= 0)
    df["prix_m2"] = (df["prix"] / df["surface"]).round(0)
    return df


# ----------------------------------------------------------------------
# ÉTAPE 3 — TRIER : quarantaine (bloquant) ou avertissement (on garde)
# Chaque règle = un nom + un "masque" (True là où la règle est violée).
# ----------------------------------------------------------------------
def ajouter_motifs(df: pd.DataFrame, regles: dict, colonne: str) -> None:
    """Écrit dans `colonne` la liste des règles violées par chaque ligne."""
    df[colonne] = ""
    for nom, violation in regles.items():
        df.loc[violation, colonne] += nom + " | "
    df[colonne] = df[colonne].str.rstrip(" |")


def trier(brut: pd.DataFrame, df: pd.DataFrame):
    aujourdhui = pd.Timestamp(date.today())
    vendu = df["statut"].str.lower() == "vendu"

    # --- Règles BLOQUANTES : la ligne est inutilisable -> quarantaine
    bloquantes = {
        "identifiant absent": df["id_local"].isna(),
        "type de transaction invalide": df["type_transaction"].isna(),
        "prix absent ou invalide": df["prix"].isna(),
        "surface absente ou invalide": df["surface"].isna(),
        "date absente ou invalide": df["date"].isna(),
        "date future pour un bien vendu": (df["date"] > aujourdhui) & vendu,
        "type de bien hors référentiel": df["type_bien"].isna(),
    }
    ajouter_motifs(df, bloquantes, "motifs_rejet")
    en_quarantaine = df["motifs_rejet"] != ""

    # --- Règles d'AVERTISSEMENT : on garde la ligne mais on la signale
    geo = pd.read_csv(REF_GEO)
    paires_connues = set(zip(geo["region"].str.lower(), geo["ville"].str.lower()))
    paire = list(zip(df["region"].str.lower(), df["ville"].str.lower()))
    vente = df["type_transaction"] == "vente"
    location = df["type_transaction"] == "location"
    appart = df["type_bien"].isin(["Appartement", "Studio"])
    avertissements = {
        "surface atypique": (df["surface"] < SURFACE_MIN) | (df["surface"] > SURFACE_MAX),
        "prix de vente atypique": vente & ((df["prix"] < PRIX_VENTE_MIN) | (df["prix"] > PRIX_VENTE_MAX)),
        "loyer atypique": location & ((df["prix"] < LOYER_MIN) | (df["prix"] > LOYER_MAX)),
        "trop de chambres": appart & (df["chambres"] > CHAMBRES_MAX_APPART),
        "salles de bain > chambres + 2": df["salles_bain"] > df["chambres"] + 2,
        "ville/région incohérentes": df["region"].notna() & df["ville"].notna()
                                     & pd.Series([p not in paires_connues for p in paire], index=df.index),
        "date future": (df["date"] > aujourdhui) & ~vendu,
    }
    ajouter_motifs(df, avertissements, "avertissements")

    # --- Une ligne est "corrigée" si nettoyer() a changé sa valeur
    df["corrige"] = (
        (pd.to_numeric(brut["prix"], errors="coerce") != df["prix"])
        | (pd.to_numeric(brut["surface"], errors="coerce") != df["surface"])
        | (brut["type_bien"] != df["type_bien"])
        | (brut["ville"] != df["ville"])
    )

    # Quarantaine : on garde les valeurs BRUTES (pour voir pourquoi "à négocier" a été rejeté)
    quarantaine = brut[en_quarantaine].assign(motifs_rejet=df.loc[en_quarantaine, "motifs_rejet"])
    propres = df[~en_quarantaine].drop(columns="motifs_rejet")
    return propres, quarantaine


# ----------------------------------------------------------------------
# ÉTAPE 4 — DOUBLONS : on marque, on ne supprime rien (c'est l'analyste qui décide)
# ----------------------------------------------------------------------
def marquer_doublons(df: pd.DataFrame) -> pd.DataFrame:
    # Doublon EXACT : même ville, type, surface, date et prix (surface/prix arrondis)
    cle_exacte = [df["ville"], df["type_bien"], df["surface"].round(0), df["date"], df["prix"].round(0)]
    df["doublon_exact"] = pd.concat(cle_exacte, axis=1).duplicated(keep=False)

    # Doublon PROBABLE : mêmes ville et type, surface à ±10 m² et prix à ±1 million près
    cle_proche = [df["ville"], df["type_bien"], (df["surface"] / 10).round(), (df["prix"] / 1_000_000).round()]
    proche = pd.concat(cle_proche, axis=1).duplicated(keep=False)
    df["doublon_probable"] = proche & ~df["doublon_exact"]
    return df


# ----------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# ----------------------------------------------------------------------
def main():
    print("1. Chargement")
    brut = charger_sources()
    print(f"  -> {len(brut)} lignes au total\n")

    print("2. Nettoyage")
    nettoye = nettoyer(brut)

    print("3. Tri : propres / quarantaine")
    propres, quarantaine = trier(brut, nettoye)

    print("4. Doublons")
    propres = marquer_doublons(propres)

    SORTIE.mkdir(parents=True, exist_ok=True)
    propres.to_csv(SORTIE / "donnees_propres.csv", index=False)
    quarantaine.to_csv(SORTIE / "quarantaine.csv", index=False)

    conformes = (~propres["corrige"]) & (propres["avertissements"] == "")
    print("\n=== Bilan ===")
    print(f"Lignes reçues        : {len(brut)}")
    print(f"Conservées           : {len(propres)}")
    print(f"Quarantaine          : {len(quarantaine)}")
    print(f"Corrigées            : {propres['corrige'].sum()}")
    print(f"Avec avertissement   : {(propres['avertissements'] != '').sum()}")
    print(f"Entièrement conformes: {conformes.sum()}")
    print(f"Doublons exacts      : {propres['doublon_exact'].sum()}")
    print(f"Doublons probables   : {propres['doublon_probable'].sum()}")
    print(f"\nFichiers écrits dans {SORTIE}")


if __name__ == "__main__":
    main()
