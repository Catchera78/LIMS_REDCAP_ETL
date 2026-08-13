# Revue finale V1.0 — LIMS → REDCap ETL (MDF)

**Date :** 2026-08-13
**Portée :** revue complète du système avant utilisation réelle (Prompt 13).
**Méthode :** inspection du code (grep/relecture) + exécution de la suite de tests
(107 tests) + non-régression vs Golden Stata + exécution réelle de bout en bout.

---

## Verdict global : **PASS WITH RESERVATIONS**

Le système est **techniquement conforme** à tous les points de contrôle
ci-dessous. Les deux réserves de maintenabilité (R1, R2) ont été **appliquées et
résolues** ; il ne reste que R3 (un simple `pip install` en production) et,
surtout, les **validations métier** qui relèvent du Data Manager (voir dernière
section). Aucune règle métier n'a été modifiée pour faire passer les tests.

---

## Points de contrôle

| # | Contrôle | Verdict | Preuve |
|---|---|---|---|
| 1 | Aucun mapping basé sur une position de colonne | ✅ PASS | `grep` : aucun `vNN` / `column_position` / index codé en dur. L'association passe par `source_group\|source_field\|source_occurrence` (`mapping_loader.resolve_columns`). Les `.position` proviennent tous d'identités **résolues**. Test structurel E (COLDA renommé) : aucune mauvaise variable affectée. |
| 2 | Aucun chemin absolu | ✅ PASS | `grep` sur `src/`, `config/`, `run_pipeline.py`, `build_reference_schema.py`, `tests/` : aucun `X:\` ni chemin POSIX absolu. Tous les chemins sont relatifs à `SCRIPT_DIR`. |
| 3 | Aucun fichier source modifié | ✅ PASS | `openpyxl.load_workbook(read_only=True)`, lecteur stdlib en lecture seule, `archiver` = `shutil.copy2` et **refuse** une destination = source. Run réel : md5 de l'extraction **inchangé**. |
| 4 | Aucune exception Python masquée | ✅ PASS | Tous les `except` ciblent un type précis (`ValueError`, `DateParseError`, `SchemaGuardError`…) et agissent. Les 5 `except Exception` sont des **gardes de dépendance optionnelle** (openpyxl/pandas), un reconfigure UTF-8, ou le garde-fou de `run_pipeline` qui **journalise** (`log.exception`). Un seul `pass` : fallback UTF-8 console. |
| 5 | Aucune visite inconnue acceptée | ✅ PASS | `transformer` → `ERROR_UNKNOWN_VISIT` (jamais d'event vide silencieux) → statut `NOT_READY`. Tests `test_transformer.test_unknown_visit_*`, structurel F. |
| 6 | Aucune date invalide transformée silencieusement | ✅ PASS | Date impossible → `ERROR_INVALID_DATE` (sortie vide **+ erreur enregistrée**, valeur source conservée). Tests `test_date_parser.test_invalid_date_raises`, `test_transformer.test_invalid_date_produces_error_invalid_date`. |
| 7 | Aucun fichier READY produit en présence d'une erreur bloquante | ✅ PASS | `compute_status` → `NOT_READY` si erreurs ou Schema `FAIL` ; l'export nomme alors `NOT_READY_Data_<date>.csv`. Tests `test_redcap_exporter.test_status_and_filename`, `test_not_ready_never_named_ready`. |
| 8 | Toutes les transformations importantes testées | ✅ PASS | 107 tests / 13 fichiers : identité colonnes, Schema Guard (5 scénarios), mapping (résolution/ambiguïté), recodes, event, dates (12 mois + formats), heures (fractions Excel), `repeat_instance` (tri chronologique), export (format exact), QC (8 feuilles), structure (A–F), tableau de bord. |
| 9 | Golden Dataset comparé | ✅ PASS | `compare_with_stata.py` : **42 072 / 42 075 cellules identiques**, 0 différence `VALUE`/`DATE`/`TIME`/`MAPPING`/`MISSING`. Voir `REGRESSION_ANALYSIS.md`. |
| 10 | Rapport QC produit | ✅ PASS | `QC_Report_<date>.xlsx`, 8 feuilles (SUMMARY, SCHEMA, ERRORS, WARNINGS, UNKNOWN_VISITS, UNKNOWN_COLUMNS, DUPLICATES, MAPPING). Vérifié en round-trip + run réel. |
| 11 | Archivage fonctionnel | ✅ PASS | Run réel : `archive/2026-08-13/{raw,output,qc,logs}` tous peuplés ; original copié dans `raw/`, jamais modifié. |

---

## Qualités notables

- **Correction de deux défauts hérités** confirmée par la non-régression :
  1. l'enregistrement `ACC-0001` que le do-file Stata supprimait (double
     `drop in 1`) est désormais conservé ;
  2. l'encodage UTF-8 est correct (le Golden contenait 3 valeurs corrompues
     `Ã©chantillon`).
- **Résilience structurelle** démontrée (Prompt 11) : ajout/déplacement de
  colonnes → le pipeline fonctionne ; suppression d'obligatoire → `FAIL` ;
  renommage → non reconnu **sans** mauvaise affectation.
- **Zéro dépendance bloquante** : le lecteur/écrivain Excel fonctionne avec
  openpyxl **ou** en repli bibliothèque standard.
- **Séparation stricte** données/config : toute règle métier est dans
  `config/*.csv` / `pipeline.json`, modifiable par le Data Manager sans toucher
  au code.

---

## Réserves (maintenabilité — non bloquantes)

| # | Réserve | Statut | Impact / Recommandation |
|---|---|---|---|
| R1 | Duplication d'orchestration `run_pipeline.py` / `src/etl.py`. | ✅ **RÉSOLUE** | `run_pipeline` appelle désormais `run_etl` (une seule implémentation de la chaîne métier). La correction a d'ailleurs révélé et corrigé un **bug latent** de `run_etl` : les avertissements `WARNING_MULTIPLE_RECORDS_SAME_EVENT` étaient perdus (non intégrés à `tr.issues`). 107 tests re-validés + run réel identique. |
| R2 | Champs admin liés à un `source_group` = bannière (ex. `DÉTAILS DU PARTICIPANT...`) dans le mapping. | ✅ **RÉSOLUE** | `source_group` vidé pour les **9 champs admin à nom globalement unique** (`Laboratoire`, `Sites`, `EssaiClin`, `Essai Clinique`, `ID de Participant`, `N° de Visite`, `Âge en Jours`, `Sexe`, `InsPar`) → résolution par nom de champ, robuste au libellé de bannière. `Date`/`Heure` (noms répétés) **gardent** leur groupe pour désambiguïser, comme les blocs MDFT. Tests `test_r2_*`. *Nuance* : le Schema Guard, lui, reste basé sur `groupe+champ` ; après un vrai changement de bannière, il suffit de régénérer `reference_schema.json` (une commande) — **le mapping n'a plus à être édité**. |
| R3 | Vérification de la présence d'openpyxl. | ✅ **RÉSOLUE** | `src/environment.py` : vérification à chaque exécution (journal + **note** sur le tableau de bord si absent) + commande dédiée `python run_pipeline.py --check`. `requirements.txt` rendu honnête (pandas/dateutil non utilisés). **Bug corrigé au passage** : le repli stdlib échouait sur les vraies extractions LIMS (cibles de relation **absolues** → chemin doublé) ; corrigé (`_normalize_part`, test). L'extraction réelle `26_08_13` est désormais lue et comparée (voir ci-dessous). |

Aucune de ces réserves n'affecte la **correction** des résultats produits.

### Non-régression stricte confirmée (extraction 26_08_13 fournie par le DM)

L'extraction `26_08_13` correspondant au Golden a été fournie (`input/`) et
comparée : **0 ligne perdue** (0 MISSING), **42 068 / 42 075 cellules
identiques**. Les 7 écarts de cellule + 12 lignes EXTRA sont **entièrement
expliqués** (extraction plus complète : `ACC-0001` + nouveaux prélèvements M21 ;
1 échantillon Selles complété entre les deux extractions ; 2 corrections
d'encodage) — **aucun défaut du pipeline**. Détail :
[`docs/REGRESSION_ANALYSIS.md`](REGRESSION_ANALYSIS.md).

---

## Points restant à valider par le Data Manager (avant mise en production)

- [ ] **`ACC-0001`** : confirmer que cet enregistrement (supprimé par Stata,
  conservé ici) doit bien être importé dans REDCap (probablement manquant
  aujourd'hui dans la base).
- [ ] **Nommage `SAMCC` / `SAMCD` / `SAMCO` / `CollDate`** (colonnes 79/81/85) :
  confirmer les variables REDCap cibles (mappées telles quelles, annotées dans
  `lims_redcap_mapping.csv`).
- [ ] **`lims_age`** : confirmer que la variable REDCap attend bien un âge **en
  jours** (`Âge en Jours`, et non `Âge`).
- [x] **Extraction `26_08_13`** : fournie et comparée en non-régression stricte
  (0 ligne perdue). **Reste à confirmer par le DM** : les 12 enregistrements
  supplémentaires (dont `ACC-0001` et les nouveaux M21) et la mise à jour de
  l'échantillon Selles de `PT-0006` sont des évolutions attendues de la
  donnée LIMS.
- [ ] **Format de sortie REDCap** : confirmer `DD/MM/YYYY`, séparateur `;`,
  UTF-8 avec BOM (reproduit la référence).
- [ ] **Politique valeurs manquantes/inconnues** : confirmer site inconnu →
  bloquant, sexe inconnu → avertissement, date de réception manquante → à définir.
- [ ] **Correspondances des 40 règles** de `lims_redcap_mapping.csv` et des 16
  visites de `visits_mapping.csv` : validation formelle comme référentiel contrôlé.
- [ ] **Cohérence `reference_schema.json` ↔ `lims_redcap_mapping.csv`** (les 9
  obligatoires concordent aujourd'hui ; à re-vérifier si l'un des deux évolue).

---

## Conclusion

La V1.0 satisfait les 15 critères d'acceptation de la spécification (§21) et les
11 points de contrôle de cette revue. Elle **remplace le processus manuel** :
l'Excel LIMS est utilisé directement, sans création de `source.csv`, sans
suppression manuelle d'en-têtes/légendes, sans chemin codé en dur, avec
génération automatique du fichier REDCap + rapport QC + archivage, et validation
de non-régression vs Stata.

**Recommandation : mise en production autorisée après validation, par le Data
Manager, des points listés ci-dessus** — en particulier `ACC-0001` et le
nommage `SAMCC/SAMCD`. Le contrôle humain avant import REDCap reste requis
(la V1.0 ne réalise pas l'import).
