# CURRENT_PIPELINE_AUDIT — Pipeline LIMS → REDCap (état actuel)

**Périmètre :** Prompt 0 — audit **en lecture seule** du processus existant, avant tout développement.
**Aucun fichier source n'a été modifié.** Aucune correction n'a été appliquée.
**Date d'audit :** 2026-08-13
**Livrables associés :** `docs/CURRENT_LIMS_REDCAP_MAPPING.csv` (matrice de correspondance colonne par colonne).

Fichiers de référence audités (dans `Doc sources/`) :

| Fichier | Rôle | Constat clé |
|---|---|---|
| `Extrait LIMS 26_08_05.xlsx` | Extraction LIMS brute | Onglet `Résultats des Analyse`, **3 lignes d'en-tête**, ~101 colonnes, ~940 lignes de données + bloc de légende en bas |
| `source.csv` | Fichier intermédiaire (préparé manuellement) | `;`-séparé, encodage **cp1252**, **1 seule ligne d'en-tête**, 936 lignes de données, 101 colonnes |
| `Dofile _LIMS import_2025-04-22_csv_MAJ_2026-08-13.do` | Transformation Stata | Chemins absolus codés en dur, identification **par position** (`v1`…`v101`) |
| `Ready_Data_26_08_13.csv` | Sortie de référence (Golden Dataset) | `;`-séparé, **45 colonnes**, 935 lignes de données, dates au format **DD/MM/YYYY** |

> ⚠️ **Attention transversale :** les fichiers ne proviennent pas tous de la même extraction. L'Excel est daté **26_08_05** ; `source.csv` et `Ready_Data` sont datés **26_08_13**. Voir §9 (incohérences) et §11 (ambiguïtés).

---

## 1. Chemin de traitement actuel

```
Extraction LIMS Excel (onglet "Résultats des Analyse")
        │   [MANUEL] Étape 1 : récupérer l'export LIMS
        │   [MANUEL] Étape 2 : supprimer les lignes d'en-tête "non utiles"
        │   [MANUEL] Étape 3 : supprimer les légendes en bas de fichier
        │   [MANUEL] Étape 4 : enregistrer en CSV sous le nom "source.csv"
        ▼
source.csv  (;-séparé, cp1252)
        │   [STATA] Étape 5 : import delimited varnames(nonames) → v1..v101
        │           drop in 1/1 ; renames par position ; mappings ; dates ; repeat_instance
        ▼
Ready_Data_26_08_13.dta  →  export delimited  →  Ready_Data_26_08_13.csv
        │   [MANUEL] Étape 6 : ouvrir et ré-enregistrer en "CSV unicode"
        │   [MANUEL] Étape 6bis : import dans REDCap (module d'importation)
        ▼
REDCap MDF
```

Le processus repose sur **4 opérations manuelles** avant Stata et **1 après** Stata. Ces étapes manuelles sont la principale source de fragilité (voir §9-A).

---

## 2. Lignes d'en-tête

### 2.1 Dans l'Excel LIMS (`Résultats des Analyse`)
Le fichier possède **3 lignes d'en-tête** :

| Ligne | Contenu | Exemple |
|---|---|---|
| 1 | Titre du rapport | `Résultats d'Analyse par Numéro de Lab` |
| 2 | **Codes de groupe LIMS** (colonnes 64+) / bannières de section fusionnées (colonnes 1-63) | `MDFT-SAL0`, `MDFT-COLDA`, `DÉTAILS DU PARTICIPANT...`, `Reçu en Lab` |
| 3 | **Noms de champ** | `Laboratoire`, `Saliva H0`, `COLDA`, `Sexe` |

Les données commencent en **ligne 4**. Bloc de **légende** en bas (ex. `COLDA: Date de collecte`, `SAMCD: Remarque échantillon`) — à retirer (étape 3 manuelle).

### 2.2 Dans `source.csv` (tel que fourni)
`source.csv` ne contient **qu'UNE seule ligne d'en-tête** : elle correspond à la **ligne 3 de l'Excel** (les noms de champ). La ligne des codes `MDFT-*` (ligne 2 Excel) a été supprimée lors de la préparation manuelle.

### 2.3 Ce que le do-file attend
Le do-file supprime **DEUX** lignes :
- `drop in 1/1` (ligne 17) — supprime la 1ʳᵉ ligne ;
- `drop in 1` (ligne 327) — supprime à nouveau la 1ʳᵉ ligne, **après** tous les traitements.

➡️ Le do-file suppose donc **2 lignes d'en-tête** dans `source.csv`, alors que le `source.csv` fourni n'en a qu'**une**. **Conséquence directe : perte d'un enregistrement réel** (voir §9-A).

---

## 3. Colonnes LIMS utilisées vs ignorées

`source.csv` = 101 colonnes (`v1`..`v101`). Le do-file conserve **44 colonnes source** et en dérive/ajoute des variables techniques pour aboutir à **45 colonnes** de sortie.

### 3.1 Colonnes conservées (position → variable Stata)
Voir le détail complet et les en-têtes métier dans `docs/CURRENT_LIMS_REDCAP_MAPPING.csv`. Synthèse :

`v1, v5, v7, v16, v17, v19*, v25, v27, v45, v46, v56, v64→v92`
(*`v19` est utilisé pour dériver `redcap_event_name` puis **droppé** — il n'apparaît pas en sortie.)

### 3.2 Colonnes ignorées / supprimées
Supprimées explicitement (ligne 224) :
`v2 v3 v4 v5 v6 v8 v9 v10 v11 v12 v13 v14 v15 v18 v19 v20 v21 v22 v23 v24 v26 v27 v28 v29 v30 v31 v32 v33 v34 v35 v36 v37 v38 v39 v40 v41 v42 v43 v44 v47 v48 v49 v50 v51 v52 v53 v54 v55 v57 v58 v59 v60 v61 v62 v63 v93`
Puis (ligne 355) : `v94 v95 v96 v97 v98 v99 v100 v101` (groupe `MDFT-AUTR` / `MDFT-SAMP` + colonne finale vide).

> Note : `v5` et `v27` figurent dans la liste `drop` **après** avoir servi à générer `lims_site1` et `lims_sexe` — comportement volontaire (la valeur utile est déjà copiée).

Champs LIMS notables **ignorés** : Initiales, N° de Dépistage, `Âge` (`v24`, ex. `91j` — c'est `Âge en Jours`/`v25` qui est retenu), DDN, coordonnées, dates Capture/Accédé/PremImprimé/Vérifié/Machine, Diagnostic, ICD10, groupe `Autres`.

---

## 4. Correspondances par position (v1 / v7 / v16 / v25 / v45 …)

Le do-file **n'utilise jamais les en-têtes** : il renomme par numéro de colonne. Extrait :

| Position | En-tête métier (Excel ligne 2 / ligne 3) | Variable Stata | Variable REDCap |
|---|---|---|---|
| `v1` | Laboratoire | `lims_laboratoire` | `lims_laboratoire` |
| `v5` | Sites | `lims_site1` | `lims_site1` (recodé) |
| `v7` | EssaiClin | `lims_essaiclin` | `lims_essaiclin` |
| `v16` | Essai Clinique | `lims_essai_clinique` | `lims_essai_clinique` |
| `v17` | ID de Participant | `lims_id_participant` | `lims_id_participant` + `patid` |
| `v19` | N° de Visite | *(intermédiaire)* | `redcap_event_name` |
| `v25` | Âge en Jours | `lims_age` | `lims_age` |
| `v27` | Sexe | `lims_sexe` | `lims_sexe` (recodé) |
| `v45` | Reçu en Lab / Date | `lims_date_reu_en_lab` | `lims_date_reu_en_lab` |
| `v46` | Reçu en Lab / Heure | `lims_heure_reu_en_lab` | `lims_heure_reu_en_lab` |
| `v56` | InsPar | `lims_inspar` | `lims_inspar` |
| `v64`→`v92` | Blocs SAL0/SAL3/SAL4/SEL/PL | `lims_*` | `lims_*` |

**Point de fragilité majeur :** les champs répétés `Date`/`Heure` existent à plusieurs positions (`v41,v43,v45,v47,v57,v60` = `Date` ; `v42,v46,v58,v61` = `Heure`). Seule la **position** distingue « Reçu en Lab » des autres. Toute insertion/suppression de colonne en amont casse silencieusement la correspondance.

---

## 5. Transformations

| # | Transformation | Détail (do-file) |
|---|---|---|
| T1 | `patid` | `gen patid = lims_id_participant` |
| T2 | `redcap_repeat_instrument` | constante `labo_prlvements_biologiques_sousetude_mdf_lims` |
| T3 | `redcap_data_access_group` | constante `""` (vide) |
| T4 | `lims_tab_id` | constante `LIMS` |
| T5 | Site | `gen site=1 if v5=="TBR"` ; `replace site=2 if v5=="SAFO"` → `lims_site1` |
| T6 | Sexe | `gen sex=1 if v27=="M"` ; `replace sex=2 if v27=="F"` → `lims_sexe` |
| T7 | Visite → événement | 16 règles `gen/replace redcap_event_name` selon `v19` (§8) |
| T8 | Dates | remplacement des mois FR puis `date(…, "DMY")` (§6) |
| T9 | `redcap_repeat_instance` | `bys patid redcap_event_name (lims_date_reu_en_lab): gen =_n` (§7) |
| T10 | Ordre des colonnes | `order …` explicite (§10) |
| T11 | Renommages finaux | `lims_heure_reçu_en_lab`→`lims_heure_reu_en_lab` ; `lims_date_reçu_en_lab`→`lims_date_reu_en_lab` (suppression du `ç` accentué) |

**Aucune transformation ne signale d'erreur :** une valeur de site/sexe/visite non prévue produit silencieusement une valeur manquante ou vide (voir §9-D/E).

---

## 6. Conversion des dates

Colonnes converties : `lims_date_reu_en_lab` (`v45`), `lims_sal0_colda` (`v65`), `lims_sal3_colda` (`v71`), `lims_sal4_colda` (`v76`), `lims_sel_colse` (`v81`), `lims_pl_colda` (`v87`).

Mécanisme : pour chaque mois, `subinstr` remplace le libellé français par `/NN/` puis `date(var,"DMY")`, format d'affichage `%tdCCYY-NN-DD`.

| Libellé FR | Remplacement | | Libellé FR | Remplacement |
|---|---|---|---|---|
| `Janv` | `/01/` | | `Juil` | `/07/` |
| `Févr` | `/02/` | | `Août` | `/08/` |
| `Mars` | `/03/` | | `Sept` | `/09/` |
| `Avr` | `/04/` | | `Oct` | `/10/` |
| `Mai` | `/05/` | | `Nov` | `/11/` |
| `Juin` | `/06/` | | `Déc` | `/12/` |

Exemple : `02-Mai-2024` → `02-/05/-2024` → `date()` → 2 mai 2024.

> **Incohérence de format (§9-G) :** le do-file formate en `%tdCCYY-NN-DD` (→ `2024-05-06`), mais `Ready_Data_26_08_13.csv` affiche `06/05/2024` (DD/MM/YYYY). Cela indique que le fichier de référence a été **ré-enregistré via Excel** (étape 6 manuelle), qui a aussi imposé le séparateur `;` et l'encodage unicode. Le Golden Dataset n'est donc **pas** l'export Stata brut.

Il n'existe **aucune gestion de date invalide** : une date non interprétable devient silencieusement manquante.

---

## 7. Logique `redcap_repeat_instance`

```stata
gen redcap_repeat_instrument = "labo_prlvements_biologiques_sousetude_mdf_lims"
gsort patid redcap_event_name
bys patid redcap_event_name (lims_date_reu_en_lab): gen redcap_repeat_instance = _n
```

1. Regroupement par `patid` + `redcap_event_name` ;
2. Tri chronologique interne par `lims_date_reu_en_lab` ;
3. Numérotation `1, 2, 3…` (`_n`).

Exemple observé dans `Ready_Data` (participant `PT-0001`, `suivi__mois_15__si_arm_4`) : `07/05/2025` → instance **1** ; `20/05/2025` → instance **2**. Aucun avertissement n'est produit lorsqu'un participant a plusieurs lignes pour un même événement.

> Le tri se fait sur la variable **date convertie** ; les valeurs de date manquantes sont triées en premier par Stata et reçoivent donc les instances basses — comportement à surveiller lors de la reproduction Python.

---

## 8. Mappings

### 8.1 Site (`v5` → `lims_site1`)
| Valeur LIMS | REDCap |
|---|---|
| `TBR` | `1` |
| `SAFO` | `2` |
| *(autre)* | **manquant, silencieux** |

Valeurs observées dans `source.csv` : `TBR` (482), `SAFO` (454). Aucune autre.

### 8.2 Sexe (`v27` → `lims_sexe`)
| Valeur LIMS | REDCap |
|---|---|
| `M` | `1` |
| `F` | `2` |
| *(vide/autre)* | **manquant, silencieux** |

Valeurs observées : `M` (407), `F` (528), **vide (1)** → 1 enregistrement avec `lims_sexe` manquant.

### 8.3 Visite (`v19` → `redcap_event_name`)
16 correspondances (chaque mois a une variante `[n]` et une variante `WASHOUT/WASHOU[n]`) :

| `v19` | `redcap_event_name` | | `v19` | `redcap_event_name` |
|---|---|---|---|---|
| `M3[1]` | `initiation__mois_3_arm_4` | | `M15[5]` | `suivi__mois_15__si_arm_4` |
| `M3 WASHOUT[16]` | `initiation__mois_3_arm_4` | | `M15 WASHOU[14]` | `suivi__mois_15__si_arm_4` |
| `M6[2]` | `suivi__mois_6__sit_arm_4` | | `M18[6]` | `suivi__mois_18__si_arm_4` |
| `M6 WASHOUT[9]` | `suivi__mois_6__sit_arm_4` | | `M18 WASHOU[11]` | `suivi__mois_18__si_arm_4` |
| `M9[3]` | `suivi__mois_9__sit_arm_4` | | `M21[7]` | `suivi__mois_21__si_arm_4` |
| `M9 WASHOUT[13]` | `suivi__mois_9__sit_arm_4` | | `M21 WASHOU[15]` | `suivi__mois_21__si_arm_4` |
| `M12[4]` | `suivi__mois_12__si_arm_4` | | `M24[8]` | `suivi__mois_24__si_arm_4` |
| `M12 WASHOU[10]` | `suivi__mois_12__si_arm_4` | | `M24 WASHOU[12]` | `suivi__mois_24__si_arm_4` |

**Vérification sur les données courantes :** toutes les valeurs `v19` de `source.csv` sont couvertes — **aucune visite non mappée** dans cette extraction. Toute valeur non listée produirait un `redcap_event_name` **vide, sans erreur**.

> Ligne commentée dans le do-file : `*replace … if v19=="M18 WASHOU[15]"`. L'indice `[15]` est attribué à **M21 WASHOU[15]** (actif). Dans l'extraction courante, M18 utilise `[11]` et M21 utilise `[15]` : cohérent **par coïncidence**. Les indices `[n]` sont des identifiants internes LIMS susceptibles de changer (§9-F).

---

## 9. Incohérences identifiées (aucune non corrigée silencieusement)

**A — 🔴 Perte d'un enregistrement réel (bloquant potentiel).**
Le do-file supprime 2 lignes (`drop in 1/1` + `drop in 1`) alors que le `source.csv` fourni n'a qu'**une** ligne d'en-tête. Le second `drop in 1` supprime donc la **1ʳᵉ ligne de données**.
*Preuve :* l'accession `ACC-0001` / participant `PT-0004` / visite `M3[1]`, présente en 1ʳᵉ ligne de données de `source.csv`, est **absente** de `Ready_Data_26_08_13.csv`. Décompte : `source.csv` = 936 lignes de données → `Ready_Data` = 935. Cette suppression dépend du nombre de lignes d'en-tête laissées manuellement : elle est **fragile et non détectée**.

**B — 🟠 `v79` : code Excel `MDFT-SAMCC`, nom Excel `SAMCO`, variable Stata `lims_sal4_samcc`.** Trois libellés différents pour la même colonne (bloc Saliva H4).

**C — 🟠 `v85` : code Excel `MDFT-SAMCD`, nom Excel `SAMCO`, variable Stata `lims_sel_samcd`.** (bloc Selles).

**D — 🟠 `v81` : code Excel `MDFT-COLSE`, nom Excel `CollDate`, variable Stata `lims_sel_colse`.** Le nom de champ diffère des autres blocs (`COLDA`).

> B/C/D sont **confirmées par la spécification** (§5 de la spec liste `MDFT-SAL4;SAMCO;…;lims_sal4_samcc` et `MDFT-SEL;SAMCO;…;lims_sel_samcd`). Conformément à la consigne, **rien n'est corrigé** : le Golden Dataset devra trancher ce qui est historique / LIMS / REDCap réel.

**E — 🟠 Identification exclusivement par position.** `Date`/`Heure` (et tous les blocs `v64+`) ne sont reconnus que par leur numéro de colonne. Contraire au principe de conception de la spec (« ne jamais identifier une variable uniquement par sa position »).

**F — 🟡 Indices de visite `[n]` fragiles.** Le mapping visite dépend d'indices internes LIMS (`[15]`, `[11]`…) qui peuvent être réattribués par le LIMS. Une ligne (`M18 WASHOU[15]`) est déjà commentée, signe d'un ajustement passé.

**G — 🟠 Format du Golden Dataset ≠ export Stata brut.** `Ready_Data_26_08_13.csv` est `;`-séparé et affiche les dates en `DD/MM/YYYY`, alors que le do-file exporte en virgule et formate en `CCYY-NN-DD`. Le fichier a été **repassé par Excel** (étape 6). La cible de non-régression n'est donc pas déterministe au niveau du format (séparateur, format de date, encodage).

**H — 🟡 Extractions de dates différentes.** Excel = `26_08_05` (~940 lignes) ; `source.csv`/`Ready_Data` = `26_08_13` (936 lignes). Les fichiers fournis ne décrivent pas le **même** run.

**I — 🟡 Chemins absolus codés en dur** dans le do-file (import, save, export vers `D:\MSF\…\9 - Lab_ Data\…`). Non portable.

**J — 🟡 Sexe manquant non signalé.** 1 enregistrement a un `Sexe` vide → `lims_sexe` manquant, sans avertissement.

**K — 🟡 Étapes manuelles non tracées** (suppression d'en-têtes, de légendes, ré-enregistrement Excel). Aucune trace/log ; source de A et G.

---

## 10. Ordre final des colonnes (45)

Fixé explicitement par `order …` (ligne 353) et confirmé par l'en-tête de `Ready_Data_26_08_13.csv` :

```
1  patid
2  redcap_repeat_instrument
3  redcap_event_name
4  redcap_repeat_instance
5  redcap_data_access_group
6  lims_tab_id
7  lims_laboratoire
8  lims_site1
9  lims_essaiclin
10 lims_essai_clinique
11 lims_id_participant
12 lims_age
13 lims_sexe
14 lims_date_reu_en_lab
15 lims_heure_reu_en_lab
16 lims_inspar
17 lims_mdft_sal0
18 lims_sal0_colda
19 lims_sal0_colti
20 lims_sal0_aliqu
21 lims_sal0_samca
22 lims_d2o_dose_saliva_h0
23 lims_mdft_sal3
24 lims_sal3_colda
25 lims_sal3_colti
26 lims_sal3_aliqu
27 lims_sal3_samcb
28 lims_sal4_sal4
29 lims_sal4_colda
30 lims_sal4_colti
31 lims_sal4_aliqu
32 lims_sal4_samcc
33 lims_mdft_sel
34 lims_sel_colse
35 lims_sel_colti
36 lims_sel_stoti
37 lims_sel_aliqu
38 lims_sel_samcd
39 lims_mdft_pl
40 lims_pl_colda
41 lims_pl_colti
42 lims_pl_centi
43 lims_pl_stoti
44 lims_pl_aliqu
45 lims_pl_samco
```

---

## 11. Risques

| # | Risque | Impact | Gravité |
|---|---|---|---|
| R1 | Suppression de la 1ʳᵉ ligne de données selon le nb d'en-têtes manuels (§9-A) | Perte silencieuse d'enregistrements dans REDCap | 🔴 Élevée |
| R2 | Identification par position (§9-E) | Mauvaise variable alimentée si la structure LIMS change | 🔴 Élevée |
| R3 | Indices de visite `[n]` (§9-F) | `redcap_event_name` erroné ou vide sans alerte | 🟠 Moyenne |
| R4 | Format Golden Dataset non déterministe (§9-G) | Faux positifs massifs en test de non-régression | 🟠 Moyenne |
| R5 | Aucune gestion d'erreur (site/sexe/visite/date inconnus) | Données manquantes ou vides importées sans contrôle | 🟠 Moyenne |
| R6 | Chemins absolus + étapes manuelles (§9-I/K) | Non reproductible, non traçable | 🟡 Faible-moyenne |
| R7 | Extractions de dates différentes (§9-H) | La non-régression exacte n'est pas réalisable en l'état | 🟠 Moyenne |

---

## 12. Ambiguïtés (nécessitent une décision documentée)

1. **Naming SAMCC / SAMCD / SAMCO / CollDate** (`v79`, `v81`, `v85`) : quelle est la variable REDCap *réellement attendue* ? Historique, artefact LIMS, ou correct ? → à trancher via le Golden Dataset (ne PAS corriger maintenant).
2. **Nombre de lignes d'en-tête à retenir** : le futur ETL doit lire directement l'Excel (3 en-têtes) ; la règle de détection doit être définie sans ambiguïté pour éviter R1.
3. **Format de sortie cible** : REDCap attend-il `DD/MM/YYYY` (comme le fichier de référence repassé par Excel) ou `YYYY-MM-DD` (comme l'export Stata brut) ? Séparateur `;` ou `,` ? Encodage ? → à confirmer avec la config REDCap MDF.
4. **`Âge` vs `Âge en Jours`** : le do-file retient `Âge en Jours` (`v25`) dans `lims_age`. À confirmer que la variable REDCap `lims_age` attend bien un âge **en jours**.
5. **Politique sur Sexe/Date/Site manquants** : bloquant ou avertissement ? (la spec propose « selon configuration »).
6. **Répétitions même participant/événement** : toutes attendues, ou certaines sont des doublons à investiguer ?

---

## 13. Points nécessitant une validation humaine (Data Manager)

- [ ] **Confirmer/infirmer que la perte de `ACC-0001` (§9-A) est non intentionnelle.** Si oui, l'enregistrement manque dans REDCap et doit être ré-importé.
- [ ] Valider la matrice `docs/CURRENT_LIMS_REDCAP_MAPPING.csv` comme **référentiel contrôlé** du futur système.
- [ ] Trancher le naming SAMCC/SAMCD/SAMCO/CollDate (ambiguïté 1).
- [ ] Fournir l'**Excel LIMS `26_08_13`** (extraction identique à `Ready_Data_26_08_13.csv`) pour rendre le test de non-régression valide (§9-H).
- [ ] Fixer le format de sortie REDCap exact (dates, séparateur, encodage) — ambiguïté 3.
- [ ] Valider la sémantique de `lims_age` (jours) — ambiguïté 4.
- [ ] Définir la politique bloquant/warning pour valeurs manquantes ou inconnues (site, sexe, date, visite).

---

*Fin de l'audit. Aucune modification du pipeline existant n'a été effectuée. Le développement du nouvel ETL ne doit pas démarrer avant validation de ce document et de la matrice de mapping associée.*
