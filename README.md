# LIMS → REDCap ETL (MDF) — v1.0

Pipeline automatisé transformant une extraction Excel du LIMS Epicentre en un
fichier prêt pour l'import REDCap MDF, avec contrôles qualité et validation
humaine avant import.

> **🔒 Données.** Ce dépôt ne contient **aucune donnée d'essai réelle**. Les
> fichiers de travail (`input/`, `output/`, `archive/`) sont exclus via
> `.gitignore` et tout identifiant participant/accession présent dans les
> exemples, tests et documents est **synthétique** (`PT-0001…`, `ACC-0001…`).

> **État : V1.0 complète (Prompts 1–13).**
> Chaîne complète : lecture → structure → identité des colonnes → Schema Guard →
> mapping externalisé → transformations → dates & heures →
> `redcap_repeat_instance` → export `Ready_Data` → rapport QC → archivage +
> journal, avec tableau de bord console (double-clic `.bat`). Non-régression
> Stata **PASS**, résistance aux changements de structure testée, **revue de
> release : PASS WITH RESERVATIONS** (voir
> [`docs/V1_RELEASE_REVIEW.md`](docs/V1_RELEASE_REVIEW.md) — points à valider par
> le Data Manager). **107 tests, tous verts.**

## Identité des colonnes (Prompt 2)

Une colonne n'est **jamais** identifiée par sa position. `column_identity.py`
reconstruit une clé stable à partir des deux lignes d'en-tête :

```
section (groupe)  +  champ  +  occurrence
MDFT-SAL0 | COLDA | 1
MDFT-SAL3 | COLDA | 1
MDFT-PL   | COLDA | 1
```

Ainsi les noms simples répétés (`COLDA`, `COLTI`, `Date`, `Heure`) ne sont
jamais des identifiants seuls, et **insérer une colonne avant une variable ne
change pas son identité**. Les valeurs brutes (`raw_code`, `raw_name`) sont
conservées pour tracer les incohérences connues (ex. code `MDFT-SAMCC` /
nom `SAMCO` en position 79) — sans correction à ce stade.

## Schema Guard (Prompt 3)

`schema_guard.py` compare la structure de chaque extraction à
`config/reference_schema.json` (91 colonnes nommées, dont **9 obligatoires**) et
rend un statut :

| Statut | Signification |
|---|---|
| `PASS` | structure identique à la référence |
| `PASS_WITH_WARNINGS` | colonne **déplacée**, **nouvelle** colonne, colonne **optionnelle** absente, ambiguïté non critique, ou écart de nombre de colonnes |
| `FAIL` | variable **obligatoire** absente, ou identité obligatoire ambiguë |

Les déplacements de colonnes ne sont **jamais** bloquants (identité par contenu,
pas par position). Le journal détaille : *Expected / Found columns*, *Missing
required / optional*, *New columns*, *Moved columns*, *Ambiguous columns*, et le
statut.

Régénérer la référence (uniquement après validation d'un changement de
structure) :

```bash
python build_reference_schema.py "chemin/vers/Extrait LIMS.xlsx"
```

## Mapping externalisé (Prompt 4)

Toutes les règles métier vivent dans `config/*.csv` — **modifiables par le Data
Manager sans toucher au code**. Le code ne contient plus aucune référence à une
position (`v64`, `column_position == 64`) : chaque variable REDCap est associée à
une colonne via son **identité** `source_group | source_field | source_occurrence`.

| Fichier | Contenu | Source |
|---|---|---|
| `lims_redcap_mapping.csv` | 40 règles identité LIMS → variable REDCap (+ `required`, `data_type`, `active`, `notes`) | do-file + Excel + Ready_Data |
| `sites_mapping.csv` | `TBR→1`, `SAFO→2` | do-file |
| `sex_mapping.csv` | `M→1`, `F→2` | do-file |
| `visits_mapping.csv` | 16 visites → `redcap_event_name` (variantes WASHOUT/WASHOU incluses) | do-file |
| `redcap_output_columns.csv` | 45 colonnes de sortie, dans l'ordre exact | Ready_Data |

`mapping_loader.py` charge, **valide** (doublon de variable, identité ambiguë,
type invalide, colonne de sortie non produite → **bloquant**) et **résout**
chaque règle contre l'extraction : 0 correspondance → non résolue (bloquant si
obligatoire), 1 → OK, **>1 → ambigu (bloquant)**. Les incohérences historiques
`SAMCO`/`SAMCC`/`SAMCD` sont mappées telles quelles (colonne réelle → variable
historique) et annotées dans `notes` — à arbitrer via le Golden Dataset.

**Robustesse (R2)** : les 9 champs admin à nom **globalement unique**
(`Laboratoire`, `Sites`, `EssaiClin`, `Essai Clinique`, `ID de Participant`,
`N° de Visite`, `Âge en Jours`, `Sexe`, `InsPar`) ont un `source_group` **vide**
→ ils sont résolus par le seul nom de champ, donc insensibles à un changement de
libellé de bannière LIMS. `Date`/`Heure` et les blocs MDFT gardent leur groupe
(noms répétés à désambiguïser).

## Transformations métier (Prompt 5)

`transformer.py` reproduit le do-file Stata (réglages dans `config.transform`) :

- `patid = lims_id_participant` ; constantes `lims_tab_id = "LIMS"`,
  `redcap_data_access_group = ""`, `redcap_repeat_instrument = "labo_..."` ;
- recodes de valeur : `TBR→1 / SAFO→2`, `M→1 / F→2` ;
- `redcap_event_name` via `visits_mapping.csv` ;
  **visite inconnue → `ERROR_UNKNOWN_VISIT`** (jamais un event vide silencieux).

**Ligne de données** = participant renseigné (colonne *ID de Participant*
résolue par identité) : le bloc de légende est exclu automatiquement, sans
suppression manuelle. Règle de valeur manquante alignée sur Stata : une valeur
source **vide** reste vide **sans** erreur ; une valeur **non vide non reconnue**
déclenche le code configuré (site → ERROR, sexe → WARNING).

Non encore reproduit ici : `redcap_repeat_instance` (vide, Prompt 7).

## Dates & heures (Prompt 6)

`date_parser.py` remplace les dizaines de substitutions de mois du do-file par
**une** fonction testée. En lisant l'Excel **directement**, les dates sont des
chaînes françaises (`02-Mai-2024`) mais les heures sont des **fractions Excel**
(`0.65069…`) — les deux sont gérées, ainsi que les dates Excel réelles.

- Dates acceptées : `02-Mai-2024`, `2-Mai-2024`, `02/05/2024`, `2024-05-02`,
  `02-05-2024`, objet date, n° de série Excel → sortie **`DD/MM/YYYY`** (reproduit
  la référence).
- Heures acceptées : `11:27`, `11:27:00`, fraction Excel, objet time → sortie
  **`HH:MM`**.
- 12 mois FR couverts (`Janv`…`Déc`, config `transform.french_months`).
- Date impossible → **`ERROR_INVALID_DATE`** (valeur de sortie vide **mais** erreur
  enregistrée avec la valeur source ; jamais silencieux) ; heure impossible →
  `ERROR_INVALID_TIME` (avertissement).

Vérifié sur l'extraction réelle : `02-Mai-2024 → 02/05/2024`,
`0.65069 → 15:37`, `0.43055 → 10:20` — valeurs identiques à celles produites par
l'ancien `source.csv`.

## redcap_repeat_instance (Prompt 7)

`repeat_instance.py` reproduit `bys patid redcap_event_name
(lims_date_reu_en_lab): gen = _n` :

1. groupement par `patid + redcap_event_name` ;
2. tri **chronologique** par `lims_date_reu_en_lab` (date **reparsée**, pas la
   chaîne — `07/12/2024` avant `07/05/2025`) ;
3. numérotation `1, 2, 3…`.

Fidélité Stata : date manquante triée **en dernier** ; égalités départagées par
l'ordre d'apparition (déterministe, là où Stata est arbitraire). Un groupe de
plusieurs lignes pour un même `(patid, event)` produit
**`WARNING_MULTIPLE_RECORDS_SAME_EVENT`** (81 sur l'extraction de test).

## Export Ready_Data (Prompt 8)

`redcap_exporter.py` écrit un CSV **au format exact** de la référence :
séparateur `;`, **UTF-8 avec BOM**, fins de ligne **CRLF**, noms REDCap exacts,
**ordre exact** de `redcap_output_columns.csv`, **aucune colonne technique
interne**. Vérifié : l'en-tête produit est identique à celui de
`Ready_Data_26_08_13.csv`.

**Gate colonnes** : avant écriture, chaque enregistrement est comparé à
`redcap_output_columns.csv` ; toute colonne manquante, en trop ou en double
**bloque l'export**.

**Nom selon le statut** : `READY` / `READY_WITH_WARNINGS` →
`Ready_Data_<date>.csv` ; `NOT_READY` → `NOT_READY_Data_<date>.csv` (jamais
`Ready_Data`, pour éviter tout import REDCap accidentel). La date est le jeton
`AA_MM_JJ` extrait du nom de l'extraction.

## Rapport QC (Prompt 9)

`qc_reporter.py` produit `QC_Report_<date>.xlsx` (écrit via `xlsx_writer`,
openpyxl ou repli stdlib) avec **8 feuilles** :

| Feuille | Contenu |
|---|---|
| `SUMMARY` | fichier, run ID, date, lignes source/output, participants, erreurs, warnings, **statut final** |
| `SCHEMA` | résultat du Schema Guard (manquantes, déplacées, nouvelles, ambiguës) |
| `ERRORS` / `WARNINGS` | `error_code, severity, source_row, patid, variable, source_value, message` |
| `UNKNOWN_VISITS` | visites non mappées (valeur, occurrences, exemple) |
| `UNKNOWN_COLUMNS` | nouvelles colonnes LIMS détectées |
| `DUPLICATES` | répétitions `patid/event` (potentiels doublons) |
| `MAPPING` | mapping réellement utilisé + colonne source résolue |

**Statut global** : `READY` (0 erreur, 0 warning) · `READY_WITH_WARNINGS`
(warnings seulement) · `NOT_READY` (≥ 1 erreur bloquante ou Schema `FAIL`). En
`NOT_READY`, aucun fichier `Ready_Data` n'est produit — seulement
`NOT_READY_Data_<date>.csv`.

## Non-régression vs Golden Stata (Prompt 10)

```bash
python tests/regression/compare_with_stata.py
```

Compare le résultat Python à `Ready_Data_26_08_13.csv` (Golden), cellule par
cellule (clé `patid + redcap_event_name + redcap_repeat_instance`) et écrit
`output/regression_differences.xlsx` (feuilles SUMMARY, CLASSIFICATION,
DIFFERENCES, ROWS_ONLY_STATA, ROWS_ONLY_PYTHON). Différences classées `FORMAT`,
`DATE`, `TIME`, `MAPPING`, `MISSING`, `EXTRA`, `VALUE` — **aucune corrigée**.

**Résultat : PASS.** 42 072 / 42 075 cellules identiques ; **0** différence
`VALUE`/`DATE`/`TIME`/`MAPPING`/`MISSING`. Les seuls écarts sont **2 défauts
hérités que le nouvel ETL corrige** : 1 enregistrement (`ACC-0001`) que Stata
supprimait à tort, et 3 valeurs à l'encodage corrompu dans le Golden. Analyse
détaillée : [`docs/REGRESSION_ANALYSIS.md`](docs/REGRESSION_ANALYSIS.md).

## Tests de changement de structure (Prompt 11)

`tests/test_structural_changes.py` génère des `.xlsx` synthétiques (structure
volontairement cassée) et vérifie le comportement — résultats dans
[`docs/STRUCTURAL_TEST_REPORT.md`](docs/STRUCTURAL_TEST_REPORT.md) :

| Test | Modification | Attendu | Obtenu |
|---|---|---|---|
| A | colonne ajoutée avant `MDFT-SAL0` | fonctionne | ✅ 40/40 résolus, `READY` |
| B | `MDFT-PL` déplacé | fonctionne | ✅ 40/40 résolus, `READY` |
| C | nouvelle colonne `MDFT-TEMP` | `PASS_WITH_WARNINGS` | ✅ colonne signalée |
| D | `ID de Participant` supprimé | `FAIL` | ✅ bloqué, `NOT_READY` |
| E | `COLDA` de `MDFT-SAL0` renommé | non reconnu, contrôlé | ✅ `lims_sal0_colda` vide, voisines intactes |
| F | visite inconnue | `ERROR_UNKNOWN_VISIT` | ✅ `NOT_READY` |

Le cœur du pipeline est factorisé dans `src/etl.py` (`run_etl`), **utilisé à la
fois par `run_pipeline.py` et par ces tests** — une seule implémentation de la
chaîne métier (réserve R1 de la revue de release levée).

---

## Utilisation (Windows)

> 📘 **Guide pas à pas complet pour le Data Manager :**
> [`docs/GUIDE_UTILISATION.md`](docs/GUIDE_UTILISATION.md) (explication + exécution,
> sans prérequis technique).

1. Placer **une** extraction LIMS `.xlsx` dans le dossier `input/`.
2. Double-cliquer sur **`RUN_LIMS_REDCAP.bat`**.
3. Lire le tableau de bord à l'écran ; la fenêtre **ne se ferme pas**
   automatiquement.

La console n'affiche que ce tableau de bord (le détail complet va dans
`archive/<date>/logs/run_<date>.log`) :

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

Records source.......... 936
Records output.......... 936
Errors.................. 0
Warnings................ 81

STATUS:
READY_WITH_WARNINGS

Output:
output/Ready_Data_26_08_13.csv

QC:
output/QC_Report_26_08_13.xlsx
```

En ligne de commande :

```bash
python run_pipeline.py
python run_pipeline.py --input input --config config/pipeline.json
```

---

## Ce que fait le programme à ce stade

| Étape | Description |
|---|---|
| 1 | Détecte l'unique fichier `.xlsx` dans `input/` (erreur si 0 ou plusieurs). |
| 2 | Ouvre l'onglet `Résultats des Analyse` (recherche tolérante aux accents). |
| 3 | Identifie automatiquement les lignes d'en-tête (codes / noms) et le début des données. |
| 4 | Affiche le nombre de colonnes et de lignes (données vs légende). |
| 5 | Copie le fichier original dans `archive/<date>/raw/` — **l'original n'est jamais modifié**. |
| 6 | Écrit un journal dans `archive/<date>/logs/run_<date>.log`. |

---

## Structure du projet

```
LIMS_REDCAP_ETL/
├── input/                 extraction LIMS .xlsx à traiter
├── output/                fichiers produits (Ready_Data / QC) — Prompts 8-9
├── archive/               copies horodatées : <date>/{raw,output,qc,logs}
├── config/
│   ├── pipeline.json           onglet, ancres, sections, archivage, schema, mapping
│   ├── reference_schema.json   signature de structure de référence (généré)
│   ├── lims_redcap_mapping.csv identité LIMS -> variable REDCap
│   ├── sites_mapping.csv        valeur site LIMS -> code REDCap
│   ├── sex_mapping.csv          valeur sexe LIMS -> code REDCap
│   ├── visits_mapping.csv       N° de Visite -> redcap_event_name
│   └── redcap_output_columns.csv  45 colonnes de sortie, dans l'ordre
├── src/
│   ├── config_loader.py    chargement + validation de la config
│   ├── excel_reader.py     lecture xlsx -> grille (openpyxl ou repli stdlib)
│   ├── header_parser.py    détection des lignes d'en-tête (fonction pure)
│   ├── column_identity.py  identité section+champ+occurrence (fonction pure)
│   ├── schema_guard.py     contrôle de structure PASS/PASS_WITH_WARNINGS/FAIL
│   ├── mapping_loader.py   chargement/validation/résolution des mappings
│   ├── transformer.py      transformations métier (recodes, constantes, event)
│   ├── date_parser.py      dates FR/ISO/Excel + heures (fractions) -> format cible
│   ├── repeat_instance.py  redcap_repeat_instance (tri chronologique par groupe)
│   ├── redcap_exporter.py  écriture Ready_Data (format exact) + gate colonnes
│   ├── qc_reporter.py      rapport QC 8 feuilles + statut global
│   ├── xlsx_writer.py      écriture .xlsx (openpyxl ou repli stdlib)
│   ├── etl.py              cœur réutilisable du pipeline (run_etl)
│   ├── dashboard.py        tableau de bord console (Prompt 12)
│   ├── archiver.py         archivage non destructif du fichier original
│   ├── logging_setup.py    journal console (UTF-8) + fichier
│   └── text_utils.py       normalisation / conversion de cellules
├── build_reference_schema.py  (re)génère config/reference_schema.json
├── tests/                 tests pytest (aussi exécutables seuls)
├── legacy/                do-file Stata historique (référence, non exécuté)
├── docs/                  audit du pipeline actuel + matrice de mapping
├── run_pipeline.py        orchestrateur
├── RUN_LIMS_REDCAP.bat    lanceur Windows
└── requirements.txt
```

---

## Installation

```bash
pip install -r requirements.txt
```

**openpyxl** est recommandé. En son absence, le pipeline bascule automatiquement
sur un lecteur/écrivain `.xlsx` en bibliothèque standard : il **reste
fonctionnel**, mais installez openpyxl sur le poste de production.

Vérifier l'environnement (présence d'openpyxl, moteurs utilisés) :

```bash
python run_pipeline.py --check
```

À chaque exécution, la présence d'openpyxl est vérifiée ; si absent, une **note**
non bloquante apparaît sur le tableau de bord.

---

## Tests

Avec pytest :

```bash
python -m pytest -q
```

Sans pytest (chaque fichier est exécutable seul) :

```bash
python tests/test_header_parser.py
python tests/test_excel_reader.py
```

Le test d'intégration lit l'extraction réelle
`../Doc sources/Extrait LIMS 26_08_05.xlsx` si elle est présente ; sinon il est
ignoré proprement.

---

## Principes de conception (rappel)

- Jamais d'identification d'une variable **uniquement par sa position**.
- Détection automatique de la structure ; rien produit silencieusement.
- Fichier LIMS original **toujours** conservé intact et archivé.
- Chemins **relatifs** ; aucune donnée métier codée en dur (tout en `config/`).
- Mappings modifiables par le Data Manager **sans toucher au code** (Prompt 4).

---

## Feuille de route

| Prompt | Contenu |
|---|---|
| ~~2~~ | ~~Parser d'identité des colonnes (groupe + champ + occurrence).~~ ✅ fait |
| ~~3~~ | ~~Schema Guard (`reference_schema.json`) : PASS / PASS_WITH_WARNINGS / FAIL.~~ ✅ fait |
| ~~4~~ | ~~Externalisation des mappings (`config/*.csv`).~~ ✅ fait |
| ~~5~~ | ~~Transformations Stata : recodes, constantes, event.~~ ✅ fait |
| ~~6~~ | ~~Dates/heures normalisées (mois FR, fractions Excel, ERROR_INVALID_DATE).~~ ✅ fait |
| ~~7~~ | ~~`redcap_repeat_instance` (tri chronologique par participant/event).~~ ✅ fait |
| ~~8~~ | ~~Export Ready_Data (format exact, gate colonnes, nom selon statut).~~ ✅ fait |
| ~~9~~ | ~~Rapport QC (`QC_Report_<date>.xlsx`, 8 feuilles) + statut formalisé.~~ ✅ fait |
| ~~10~~ | ~~Non-régression vs Golden Dataset Stata (PASS, 42072/42075 cellules).~~ ✅ fait |
| ~~11~~ | ~~Tests de changement de structure (A–F).~~ ✅ fait |
| ~~12~~ | ~~Expérience Windows : tableau de bord console + `.bat`.~~ ✅ fait |
| ~~13~~ | ~~Revue finale de release → **PASS WITH RESERVATIONS** (`V1_RELEASE_REVIEW.md`).~~ ✅ fait |

Voir `docs/CURRENT_PIPELINE_AUDIT.md` pour l'audit détaillé du processus Stata
actuel et les points en attente de validation.
