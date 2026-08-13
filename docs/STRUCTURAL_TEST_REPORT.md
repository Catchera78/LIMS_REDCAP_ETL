# Rapport des tests de changement de structure

**Date :** 2026-08-13  
**Base :** en-tetes reels de `Extrait LIMS 26_08_05.xlsx` + 20 lignes de donnees, puis mutation, ecriture d'un `.xlsx` synthetique, execution du pipeline complet.

| Test | Modification | Attendu | Résultat observé | Verdict |
|---|---|---|---|---|
| A | Colonne ajoutee avant MDFT-SAL0 | le pipeline fonctionne | OK ; schema=PASS_WITH_WARNINGS ; mappings_resolus=40/40 ; non_resolus=- ; nouvelles_colonnes=1 ; codes=- ; statut=READY | ✅ |
| B | MDFT-PL deplace en fin de fichier | le pipeline fonctionne | OK ; schema=PASS_WITH_WARNINGS ; mappings_resolus=40/40 ; non_resolus=- ; nouvelles_colonnes=0 ; codes=- ; statut=READY | ✅ |
| C | Nouvelle colonne MDFT-TEMP | PASS_WITH_WARNINGS | OK ; schema=PASS_WITH_WARNINGS ; mappings_resolus=40/40 ; non_resolus=- ; nouvelles_colonnes=1 ; codes=- ; statut=READY | ✅ |
| D | ID de Participant supprime | FAIL | BLOQUE (mapping: Resolution du mapping impossible : - OBLIGATOIRE non resolue : DéTAILS DU PARTICIPANT...|ID de Participant|1 -> lims_id_participant - OBLIGATOIRE non resolue : DéTAILS DU PARTICIPANT...|N° de Visite|1 -> redcap_event_name - OBLIGATOIRE non resolue : DéTAILS DU PARTICIPANT...|Âge en Jours|1 -> lims_age - OBLIGATOIRE non resolue : DéTAILS DU PARTICIPANT...|Sexe|1 -> lims_sexe) ; schema=FAIL ; statut=NOT_READY | ✅ |
| E | COLDA de MDFT-SAL0 renomme en 'Collection Date' | mapping non reconnu, traitement controle, sans mauvaise variable | OK ; schema=PASS_WITH_WARNINGS ; mappings_resolus=39/40 ; non_resolus=['lims_sal0_colda'] ; nouvelles_colonnes=1 ; codes=- ; statut=READY | ✅ |
| F | Visite inconnue (M99[42]) | ERROR_UNKNOWN_VISIT | OK ; schema=PASS ; mappings_resolus=40/40 ; non_resolus=- ; nouvelles_colonnes=0 ; codes={'ERROR_UNKNOWN_VISIT': 1} ; statut=NOT_READY | ✅ |

## Interprétation

- **A / B** : l'identité des colonnes étant reconstruite par contenu (`section | champ | occurrence`), l'ajout ou le déplacement de colonnes ne casse pas la résolution — les 40 règles se résolvent, le pipeline produit un fichier (Schema Guard signale déplacements/nouveautés en `PASS_WITH_WARNINGS`).
- **C** : la nouvelle colonne inconnue est détectée par le Schema Guard (`PASS_WITH_WARNINGS`) et reportée dans `UNKNOWN_COLUMNS` ; elle n'entre pas dans la sortie.
- **D** : la variable obligatoire `ID de Participant` absente déclenche `FAIL` (Schema Guard) et bloque la résolution du mapping — aucun fichier `Ready_Data` n'est produit. *Observation* : dans le LIMS, la bannière `DÉTAILS DU PARTICIPANT...` (ligne des codes) est co-localisée avec la colonne `ID de Participant` ; sa suppression décale donc aussi le groupe de `Sexe`/`N° de Visite`/`Âge en Jours` → plusieurs obligatoires non résolues, ce qui **renforce** le `FAIL`. Aucune mauvaise variable n'est alimentée.
- **E** : `COLDA` renommé n'est plus reconnu ; `lims_sal0_colda` reste **non résolue et vide**, et **aucune autre variable n'est affectée par erreur** (pas d'association par position). Traitement contrôlé, `PASS_WITH_WARNINGS`.
- **F** : la visite inconnue produit `ERROR_UNKNOWN_VISIT` → statut `NOT_READY`, fichier nommé `NOT_READY_Data_*` (jamais `Ready_Data`).

Tous les comportements observés correspondent aux comportements attendus.