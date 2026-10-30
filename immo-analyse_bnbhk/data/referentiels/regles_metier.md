# Règles métier — ImmoAnalyse

## Bloquantes (quarantaine)
- prix absent, non numérique, <= 0 après normalisation.
- surface absente, non numérique, <= 0 après normalisation.
- date non interprétable ou impossible (ex. 32/13/2024).
- date future pour une transaction déclarée vendue.
- identifiant absent.

## Normalisables (correction fiable documentée)
- casse et espaces dans region, ville, type_bien.
- séparateurs de milliers dans les prix (espace, virgule).
- virgule décimale dans les surfaces.
- suffixes FCFA ou millions si l'unité est explicite.
- synonymes de catégories (appart -> Appartement).
- dates JJ/MM/AAAA ou ISO.

## Avertissements (conserver, signaler)
- surface < 5 m² ou > 2 000 m² : atypique, pas nécessairement faux.
- prix < 100 000 FCFA ou > 2 000 000 000 FCFA : atypique, vérifier.
- ville et region incompatibles : signaler, ne pas corriger sans preuve.
- type_bien absent du référentiel : signaler.
- doublon probable entre sources : ne pas fusionner sans justification.

## Mesures à produire
- taux de valeurs manquantes par colonne
- nombre de doublons exacts et de doublons probables
- nombre d'erreurs de conversion par champ
- nombre d'enregistrements corrigés / mis en quarantaine / conservés avec avertissement
- taux d'enregistrements entièrement conformes
