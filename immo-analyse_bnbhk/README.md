# ImmoAnalyse — Qualité et exploration de données immobilières

Données synthétiques inspirées du marché immobilier sénégalais (5 sources : 3 formats CSV / Excel / JSON).
**Objectif** : transformer des données brutes et hétérogènes en données propres, puis les explorer (EDA).

## Structure

```
immo-analyse/
├── data/
│   ├── raw/             # 5 sources d'origine (jamais modifiées)
│   ├── referentiels/    # référentiel géographique + règles métier
│   └── propre/          # créé par pipeline.py : donnees_propres.csv, quarantaine.csv
├── notebooks/
│   └── 01_exploration.ipynb   # EDA (graphiques + conclusions)
├── tests/
│   └── test_pipeline.py       # tests des fonctions de nettoyage
├── pipeline.py          # chargement -> nettoyage -> tri -> doublons
└── requirements.txt
```

## Utilisation

```bash
python -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -r requirements.txt

python pipeline.py                   # 1. nettoie les données  -> data/propre/
jupyter notebook notebooks/01_exploration.ipynb   # 2. explore
python tests/test_pipeline.py        # (optionnel) vérifie les fonctions
```

## Ce que fait `pipeline.py`

| Étape | Fonction | Rôle |
|-------|----------|------|
| 1 | `charger_sources()` | Lit les 5 fichiers, renomme les colonnes pareil, empile (3 184 lignes) |
| 2 | `nettoyer()` | Prix (« 57.62 millions » -> 57 620 000), surface, dates (2 formats), type de bien, casse |
| 3 | `trier()` | Règles **bloquantes** -> quarantaine ; règles d'**avertissement** -> on garde et on signale |
| 4 | `marquer_doublons()` | Marque les doublons exacts et probables, sans rien supprimer |

**Règles bloquantes** (ligne en quarantaine) : identifiant absent, transaction invalide, prix ou surface absent/invalide/≤ 0, date invalide, date future pour un bien vendu, type de bien hors référentiel.

**Avertissements** (ligne conservée) : surface ou prix atypique, loyer atypique, trop de chambres, salles de bain > chambres + 2, ville/région incohérentes, date future.

Tous les seuils sont en haut de `pipeline.py`.

## Résultats de référence

| Indicateur | Valeur |
|------------|--------|
| Lignes reçues | 3 184 |
| Conservées / quarantaine | 3 001 / 183 |
| Corrigées | 419 |
| Avec avertissement | 174 |
| Doublons exacts / probables | 28 / 81 |
| Prix de vente médian | ≈ 71 M FCFA |

## Choix techniques

- **Données brutes préservées** : `data/raw/` n'est jamais modifié.
- **Quarantaine avec valeurs brutes** : on voit pourquoi une ligne est rejetée (ex. « à négocier »).
- **Doublons marqués, pas supprimés** : l'analyste décide.
- **Médiane plutôt que moyenne** : moins sensible aux prix extrêmes.
