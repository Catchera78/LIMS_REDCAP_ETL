# Guide d'utilisation — Pipeline LIMS → REDCap (MDF)

Guide pas à pas pour le Data Manager : comprendre ce que fait le pipeline et
l'exécuter en toute sécurité. Aucune connaissance en programmation n'est requise
pour l'usage courant (sections 1 à 8).

---

## 1. À quoi sert ce pipeline

Il transforme **automatiquement** une extraction Excel du LIMS Epicentre en un
fichier prêt pour l'import REDCap MDF, avec un rapport qualité (QC).

Il **remplace** l'ancien processus manuel :

> ~~Excel LIMS → nettoyage manuel → `source.csv` → do-file Stata → ré-enregistrement Excel → REDCap~~

par :

> **Excel LIMS → ETL automatique → contrôles QC → `Ready_Data.csv` + rapport QC → validation humaine → REDCap**

**Ce qu'il fait :** lit l'Excel directement (plus de `source.csv`, plus de
suppression manuelle d'en-têtes ou de légendes), reconstruit l'identité des
colonnes, contrôle la structure, applique les transformations (sites, sexe,
visites, dates, heures, `redcap_repeat_instance`), produit le fichier REDCap et
un rapport QC, et archive tout.

**Ce qu'il ne fait PAS (volontairement) :** il **n'importe pas** dans REDCap.
Un contrôle humain reste obligatoire avant l'import (voir section 10).

---

## 2. Installation — une seule fois par poste

Prérequis : **Python 3** installé sur le poste Windows.

1. Ouvrir une invite de commande dans le dossier `LIMS_REDCAP_ETL`.
2. (Recommandé) installer la dépendance Excel :

   ```
   pip install -r requirements.txt
   ```

3. Vérifier l'environnement :

   ```
   python run_pipeline.py --check
   ```

   Le message doit indiquer `openpyxl : PRESENT`. En cas d'absence, le pipeline
   **fonctionne quand même** (lecteur de secours intégré), mais l'installation
   est recommandée.

> À faire une seule fois. Ensuite, l'usage courant est un simple double-clic
> (section 3).

---

## 3. Exécution pas à pas (usage courant)

### Étape 1 — Exporter depuis le LIMS
Exporter l'onglet **`Résultats des Analyse`** au format Excel `.xlsx`.
Ne rien nettoyer manuellement : le pipeline gère les en-têtes et les légendes.

### Étape 2 — Déposer le fichier
Placer **UN SEUL** fichier `.xlsx` dans le dossier **`input/`**.
(S'il y en a plusieurs, le pipeline s'arrête et le signale.)

### Étape 3 — Lancer
Double-cliquer sur **`RUN_LIMS_REDCAP.bat`**.
Une fenêtre s'ouvre, affiche un tableau de bord, et **reste ouverte** à la fin.

### Étape 4 — Lire le tableau de bord
Exemple :

```
==========================================
         LIMS -> REDCap MDF
==========================================

Input:
Extrait LIMS 26_08_13.xlsx

Structure............... OK
Mapping................. OK
Transformation.......... OK
QC...................... WARNING

Records source.......... 947
Records output.......... 947
Errors.................. 0
Warnings................ 81

STATUS:
READY_WITH_WARNINGS

Output:
output/Ready_Data_26_08_13.csv

QC:
output/QC_Report_26_08_13.xlsx
```

### Étape 5 — Agir selon le STATUS
Voir la section 5. En résumé : `READY`/`READY_WITH_WARNINGS` → un fichier
`Ready_Data` est produit ; `NOT_READY` → **aucun** fichier `Ready_Data`, corriger
d'abord.

### Étape 6 — Revoir le rapport QC
Ouvrir `output/QC_Report_<date>.xlsx` et vérifier les feuilles (section 7),
en particulier `ERRORS`, `WARNINGS` et `DUPLICATES`.

### Étape 7 — Importer dans REDCap
Une fois la revue faite et validée, importer `output/Ready_Data_<date>.csv`
via le module d'importation de REDCap.

---

## 4. Comprendre le tableau de bord

| Ligne | Signification |
|---|---|
| **Input** | Fichier d'entrée détecté |
| **Structure** | Contrôle de structure (Schema Guard) : `OK` / `WARNING` / `FAIL` |
| **Mapping** | Association colonnes LIMS → variables REDCap : `OK` / `FAIL` |
| **Transformation** | Application des règles (recodes, dates, event…) : `OK` / `ERROR` |
| **QC** | Reflet du statut global : `OK` / `WARNING` / `ERROR` |
| **Records source** | Nombre de lignes de données lues (participant renseigné) |
| **Records output** | Nombre d'enregistrements produits |
| **Errors / Warnings** | Nombre d'erreurs bloquantes / d'avertissements |
| **STATUS** | Statut global (section 5) |
| **Output / QC** | Chemins des fichiers produits |
| **Note** | (Le cas échéant) recommandation non bloquante, ex. installer openpyxl |

---

## 5. Les trois statuts

| Statut | Signification | Fichier produit | Action |
|---|---|---|---|
| **READY** | 0 erreur, 0 avertissement | `Ready_Data_<date>.csv` | Vérifier le QC puis importer |
| **READY_WITH_WARNINGS** | 0 erreur bloquante, mais des avertissements | `Ready_Data_<date>.csv` | **Examiner les avertissements** (QC) avant d'importer |
| **NOT_READY** | ≥ 1 erreur bloquante | `NOT_READY_Data_<date>.csv` (jamais `Ready_Data`) | **Ne pas importer.** Corriger la cause (section 10), relancer |

> Le nommage protège l'import : un fichier `NOT_READY_Data_*` ne doit jamais être
> importé dans REDCap.

---

## 6. Les fichiers produits

À chaque exécution, dans `output/` :

- **`Ready_Data_<date>.csv`** — le fichier à importer (UTF-8, séparateur `;`,
  45 colonnes dans l'ordre attendu). En cas d'erreur bloquante :
  `NOT_READY_Data_<date>.csv`.
- **`QC_Report_<date>.xlsx`** — le rapport qualité (8 feuilles, section 7).

Et une **archive complète** dans `archive/<date>/` :

```
archive/<date>/
├── raw/     copie du fichier LIMS original (jamais modifié)
├── output/  copie du Ready_Data produit
├── qc/      copie du rapport QC
└── logs/    journal détaillé (run_<date>.log)
```

> `<date>` = le jeton `AA_MM_JJ` extrait du nom du fichier d'entrée
> (ex. `Extrait LIMS 26_08_13.xlsx` → `26_08_13`).

---

## 7. Lire le rapport QC (`QC_Report_<date>.xlsx`)

| Feuille | Contenu |
|---|---|
| **SUMMARY** | Fichier, date, lignes source/sortie, participants, erreurs, avertissements, **statut final** |
| **SCHEMA** | Résultat du contrôle de structure (colonnes manquantes, déplacées, nouvelles) |
| **ERRORS** | Erreurs bloquantes : `error_code, severity, source_row, patid, variable, source_value, message` |
| **WARNINGS** | Avertissements (même structure) |
| **UNKNOWN_VISITS** | Visites non reconnues (à ajouter au mapping des visites) |
| **UNKNOWN_COLUMNS** | Nouvelles colonnes LIMS détectées |
| **DUPLICATES** | Participants ayant plusieurs prélèvements pour un même événement |
| **MAPPING** | Le mapping réellement utilisé pendant l'exécution |

**Chaque ligne d'erreur/avertissement indique la ligne source (`source_row`), le
participant (`patid`) et la valeur en cause (`source_value`)** — pour retrouver et
corriger rapidement dans le LIMS.

---

## 8. Glossaire des codes

| Code | Gravité | Signification | Que faire |
|---|---|---|---|
| `ERROR_UNKNOWN_VISIT` | Bloquant | Une valeur de « N° de Visite » n'est pas dans le mapping des visites | Vérifier la visite ; l'ajouter à `config/visits_mapping.csv` si légitime |
| `ERROR_UNKNOWN_SITE` | Bloquant | Valeur de site non reconnue (≠ TBR/SAFO) | Vérifier la valeur ; compléter `config/sites_mapping.csv` |
| `ERROR_INVALID_DATE` | Bloquant | Date non interprétable | Corriger la date dans le LIMS |
| `ERROR_INVALID_TIME` | Avertissement | Heure non interprétable | Vérifier l'heure dans le LIMS |
| `WARNING_UNKNOWN_SEX` | Avertissement | Sexe ≠ M/F (valeur non vide) | Vérifier ; compléter `config/sex_mapping.csv` si besoin |
| `WARNING_MULTIPLE_RECORDS_SAME_EVENT` | Avertissement | Plusieurs prélèvements pour un même participant/événement | Confirmer qu'il s'agit de vraies répétitions (rattrapage), pas de doublons |

> Une valeur source **vide** reste vide **sans** erreur (comme l'ancien
> processus) ; seule une valeur **non vide non reconnue** est signalée.

---

## 9. Modifier les correspondances SANS toucher au code

Toutes les règles métier sont dans des fichiers `config/*.csv`, éditables au
tableur (les enregistrer en **UTF-8**, séparateur `;`) :

| Fichier | Rôle |
|---|---|
| `config/lims_redcap_mapping.csv` | Colonne LIMS → variable REDCap (40 règles) |
| `config/sites_mapping.csv` | `TBR→1`, `SAFO→2` |
| `config/sex_mapping.csv` | `M→1`, `F→2` |
| `config/visits_mapping.csv` | `N° de Visite` → `redcap_event_name` (16 visites) |
| `config/redcap_output_columns.csv` | Les 45 colonnes de sortie, dans l'ordre |
| `config/pipeline.json` | Réglages généraux (onglet, formats, statuts) |

**Ajouter une visite** : ajouter une ligne à `visits_mapping.csv`.
**Ajouter un site** : ajouter une ligne à `sites_mapping.csv`.

> Après édition, relancer le pipeline : il **valide** les fichiers de config au
> démarrage et bloque en cas d'incohérence (doublon, ambiguïté).

**Si la structure de l'export LIMS change durablement** (colonnes ajoutées /
renommées, validées par le DM), régénérer la signature de référence :

```
python build_reference_schema.py "chemin\vers\Extrait LIMS.xlsx"
```

---

## 10. Que faire si… (dépannage)

| Message / situation | Cause | Solution |
|---|---|---|
| `Aucun fichier .xlsx trouvé dans input` | `input/` est vide | Y déposer l'extraction `.xlsx` |
| `Plusieurs fichiers .xlsx dans input` | ≥ 2 fichiers | N'en laisser qu'**un** |
| STATUS `NOT_READY`, `ERROR_UNKNOWN_VISIT` | Visite non mappée | Voir `UNKNOWN_VISITS` du QC ; corriger le LIMS ou compléter `visits_mapping.csv` |
| STATUS `NOT_READY`, `ERROR_INVALID_DATE` | Date illisible | Voir `ERRORS` du QC (`source_row`, `patid`) ; corriger le LIMS |
| Structure `FAIL` | Colonne obligatoire absente (ex. `ID de Participant`) | Vérifier l'export LIMS ; l'onglet et les colonnes obligatoires doivent être présents |
| Structure `WARNING` | Colonne déplacée ou nouvelle | Non bloquant ; vérifier `SCHEMA`/`UNKNOWN_COLUMNS` du QC |
| Note « openpyxl absent » | Dépendance non installée | Non bloquant ; `pip install -r requirements.txt` |

Le **journal complet** de chaque exécution est dans
`archive/<date>/logs/run_<date>.log` (utile pour un diagnostic approfondi).

---

## 11. Checklist de validation avant import REDCap (Data Manager)

- [ ] Statut `READY` ou `READY_WITH_WARNINGS` (jamais importer un `NOT_READY_Data`).
- [ ] Feuille `ERRORS` du QC **vide**.
- [ ] Feuille `WARNINGS` / `DUPLICATES` revue : les répétitions sont légitimes.
- [ ] Feuille `UNKNOWN_VISITS` **vide** (sinon, compléter le mapping).
- [ ] Nombre de `Records output` cohérent avec l'attendu.
- [ ] Le fichier LIMS original a bien été archivé (`archive/<date>/raw/`).

---

## 12. Où est quoi (arborescence)

```
LIMS_REDCAP_ETL/
├── input/                    <- déposer l'extraction .xlsx ICI
├── output/                   <- Ready_Data + QC_Report produits
├── archive/                  <- copies horodatées (raw, output, qc, logs)
├── config/                   <- règles métier (éditables au tableur)
├── src/                      <- code (ne pas modifier sans revue)
├── legacy/                   <- ancien do-file Stata (référence)
├── docs/                     <- documentation (audit, revue, ce guide…)
├── RUN_LIMS_REDCAP.bat       <- double-cliquer pour lancer
├── run_pipeline.py           <- point d'entrée
└── requirements.txt
```

---

## 13. Annexe — exécution en ligne de commande

```
python run_pipeline.py                 exécution normale (comme le .bat)
python run_pipeline.py --check         vérifier l'environnement (openpyxl)
python run_pipeline.py --input <dir>   utiliser un autre dossier d'entrée
python build_reference_schema.py <xlsx>   régénérer la structure de référence
python -m pytest -q                    lancer la suite de tests (technique)
```

---

## Pour aller plus loin

- `docs/CURRENT_PIPELINE_AUDIT.md` — audit du processus Stata historique.
- `docs/CURRENT_LIMS_REDCAP_MAPPING.csv` — matrice LIMS → Stata → REDCap.
- `docs/REGRESSION_ANALYSIS.md` — comparaison avec le résultat Stata (non-régression).
- `docs/STRUCTURAL_TEST_REPORT.md` — comportement face aux changements de structure.
- `docs/V1_RELEASE_REVIEW.md` — revue de mise en production + points à valider.
- `README.md` — vue technique d'ensemble.

*Guide v1.0 — le contrôle humain avant l'import REDCap reste obligatoire.*
