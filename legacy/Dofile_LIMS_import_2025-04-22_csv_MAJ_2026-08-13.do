/*

** Etape 1: Recuperer le fichier d'exportation LIMS
** Etape 2:  Supprimer les entetes non utiles qui ne sont pas des noms de colones
** Etape 3: Supprimer les legendes en bas du fichier d'eportation
** Etape 4: Enregister ce fichier en version CSV sous le nom "source.csv)"
** Etape 5: Importer ce fichier dans stata en utilisant ce programme ecrit
** Etape 6: Un fichier nommé " Ready_Data_" sera crée, ouvrir ce fichier et l'enregistrer en formar csv unicode
** Etape 6: Ouvrir la BD redcap, utiliser le module d'importation des données pour importer ce fichier produit.

*/

clear

import delimited "D:\MSF\GRP-EPI-PROJ-Microbiome-directed Food (MDF) Trial - Documents\Dossier_Interne_Epicentre\MDF_Data management\9 - Lab_ Data\2 - Data - Redcap import\For import in Redcap\source.csv", varnames(nonames) case(preserve) clear 

drop in 1/1
 
* rename var
rename v1 lims_laboratoire	

gen site= 1 if v5=="TBR"
replace site= 2 if v5=="SAFO"
rename site lims_site1


rename v7 lims_essaiclin 
*rename F lims_site2	
rename v16 lims_essai_clinique	
rename v17 lims_id_participant	
*rename I lims_initiales	
*rename J lims_num_visite	
*rename K lims_num_depistage	
*rename L Lims_Age	
rename v25 lims_age	
*rename N lims_ddn	
gen sex =1 if v27=="M"
replace sex=2 if v27=="F"
rename sex lims_sexe 


*rename P lims_num_reference
*rename Q lims_adres_particip
*rename R lims_zone_locale
*rename S lims_domaine_sante
*rename T lims_tel_fixo
*rename U lims_tel_trav
*rename V lims_tel_cel
*rename W lims_e_mail
*rename X lims_echantil
*rename Y lims_date_capture
rename v45  lims_date_reçu_en_lab
rename v46  lims_heure_reçu_en_lab
rename v56 lims_inspar	
*rename AN Lims_Date_Test	
*rename AO Lims_Heure_Test	
*rename AP Lims_VérifPar	
*rename AQ lims_date_collecte	
*rename AR lims_heure_collecte 
rename v64 lims_mdft_sal0	
rename v65 lims_sal0_colda	
rename v66 lims_sal0_colti
rename v67 lims_sal0_aliqu	
rename v68 lims_sal0_samca	
rename v69 lims_d2o_dose_saliva_h0	

rename v70 lims_mdft_sal3	
rename v71 lims_sal3_colda	
rename v72 lims_sal3_colti	
rename v73 lims_sal3_aliqu	
rename v74 lims_sal3_samcb
	
rename v75 lims_sal4_sal4	
rename v76 lims_sal4_colda	
rename v77 lims_sal4_colti
rename v78 lims_sal4_aliqu
rename v79 lims_sal4_samcc	

rename v80 lims_mdft_sel	
rename v81 lims_sel_colse	
rename v82 lims_sel_colti
rename v83 lims_sel_stoti	
rename v84 lims_sel_aliqu	
rename v85 lims_sel_samcd	

rename v86 lims_mdft_pl
rename v87 lims_pl_colda	
rename v88 lims_pl_colti	
rename v89 lims_pl_centi	
rename v90 lims_pl_stoti	
rename v91 lims_pl_aliqu	
rename v92 lims_pl_samco	




*** Labeling
label variable lims_laboratoire "Laboratoire"
label variable lims_site1 "Site"
label variable lims_essaiclin "EssaiClin"
*label variable lims_de "De"
*label variable lims_numlaborig "NumLabOrig"
*label variable lims_site2 "Site"
label variable lims_essai_clinique "Essai Clinique"
label variable lims_id_participant "ID de Participant"
*label variable lims_initiales "Initiales"
*label variable lims_num_visite "N° de Visite"
*label variable lims_num_depistage "Num de Dépistage"
label variable lims_age "Âge"
*label variable lims_age_jours "Âge Jours"
*label variable lims_ddn "DDN"
label variable lims_sexe "Sexe"
*label variable lims_num_reference "Numéro de Référence"
*label variable lims_adres_particip "Adresse du Participant"
*label variable lims_zone_locale "Zone Locale"
*label variable lims_domaine_sante "Domaine de la Santé"
*label variable lims_tel_fixo "Tel Fixo"
*label variable lims_tel_trav "Tél Trav"
*label variable lims_tel_cel "Tél Cel"
*label variable lims_e_mail "E-mail"
*label variable lims_echantil "Types échantillon"
*label variable lims_date_capture "Date  Capture"
*label variable lims_heure_capture "Heure Capture"
*label variable lims_date_accede "Date  Accédé"
*label variable lims_heure_accede "Heure Accédé"
label variable lims_date_reçu_en_lab "Date  Reçu en Lab"
label variable lims_heure_reçu_en_lab "Heure Reçu en Lab"
*label variable lims_date_prem_imprime "Date  Prem Imprimé"
*label variable lims_heure_prem_imprim "Heure Prem ImpriM"
*label variable lims_diagnostic "Diagnostic"
*label variable lims_mdf_icd10 "ICD10"
*label variable lims_inf_prec "Inf/Préc"
*label variable lims_therapie "Thérapie"
*label variable lims_remarques "Remarques"
*label variable lims_codedetest "CodeDeTest"

label variable lims_inspar "InsPar"
*label variable lims_date_verifies "Date  VeRIFIeS"
*label variable lims_heure_verifies "Heure VeRIFIeS"
*label variable lims_verifpar_ "VerifPar "
*label variable lims_date_collecte "Date  COLLECTE"
*label variable lims_heure_collecte "Heure COLLECTE"
*label variable lims_machine_collecte "Machine COLLECTE"
*label variable lims_repete_collecte " RepètE COLLECTE"
label variable lims_mdft_sal0 "SAL0 : Saliva H0"
label variable lims_sal0_colda "COLDA: Date de collecte"
*label variable lims_sal0_colti "COLTI: Temps de collecte"
*label variable lims_sal0_centi "CENTI: Temps de centrifugation"
*label variable lims_sal0_stoti "STOTI: Temps de stockage"
label variable lims_sal0_aliqu "ALIQU: Nombre d'aliquots"
label variable lims_sal0_samca "SAMCA: Remarque échantillon"
label variable lims_d2o_dose_saliva_h0 "D2O Dose Saliva H0"

label variable lims_mdft_sal3 "SAL3 : Saliva H3"
label variable lims_sal3_colda "COLDA: Date de collecte"
label variable lims_sal3_colti "COLTI: Temps de collecte"
*label variable lims_sal3_centi "CENTI: Temps de centrifugation"
*label variable lims_sal3_stoti "STOTI: Temps de stockage"
label variable lims_sal3_aliqu "ALIQU: Nombre d'aliquots"
label variable lims_sal3_samcb "SAMCB: Remarque échantillon"
label variable lims_sal4_sal4 "SAL4 : Saliva H4"
label variable lims_sal4_colda "COLDA: Date de collecte"
label variable lims_sal4_colti "COLTI: Temps de collecte"
*label variable lims_sal4_centi "CENTI: Temps de centrifugation"
*label variable lims_sal4_stoti "STOTI: Temps de stockage"
label variable lims_sal4_aliqu "ALIQU: Nombre d'aliquots"
label variable lims_sal4_samcc "SAMCC: Remarque échantillon"
label variable lims_mdft_sel "SEL  : Selles"
label variable lims_sel_colse "COLSE: Date de collecte"
label variable lims_sel_colti "COLTI: Temps de collecte"
label variable lims_sel_stoti "STOTI: Temps de stockage"
label variable lims_sel_aliqu "ALIQU: Nombre d'aliquots"
label variable lims_sel_samcd "SAMCD: Remarque échantillon"
label variable lims_mdft_pl "PL   : Plasma"
label variable lims_pl_colda "COLDA: Date de collecte"
label variable lims_pl_colti "COLTI: Temps de collecte"
label variable lims_pl_centi "CENTI: Temps de centrifugation"
label variable lims_pl_stoti "STOTI: Temps de stockage"
label variable lims_pl_aliqu "ALIQU: Nombre d'aliquots"
label variable lims_pl_samco "SAMCO: Remarque échantillon"
**

**#
gen patid=lims_id_participant
gen redcap_event_name="initiation__mois_3_arm_4" if v19=="M3[1]"
replace redcap_event_name="initiation__mois_3_arm_4" if v19=="M3 WASHOUT[16]"

replace redcap_event_name="suivi__mois_6__sit_arm_4" if v19=="M6[2]"
replace redcap_event_name="suivi__mois_6__sit_arm_4" if v19=="M6 WASHOUT[9]"

replace redcap_event_name="suivi__mois_9__sit_arm_4" if v19=="M9[3]"
replace redcap_event_name="suivi__mois_9__sit_arm_4" if v19=="M9 WASHOUT[13]"


replace redcap_event_name="suivi__mois_12__si_arm_4" if v19=="M12[4]"
replace redcap_event_name="suivi__mois_12__si_arm_4" if v19=="M12 WASHOU[10]"



replace redcap_event_name="suivi__mois_15__si_arm_4" if v19=="M15[5]"
replace redcap_event_name="suivi__mois_15__si_arm_4" if v19=="M15 WASHOU[14]"


replace redcap_event_name="suivi__mois_18__si_arm_4" if v19=="M18[6]"
*replace redcap_event_name="suivi__mois_18__si_arm_4" if v19=="M18 WASHOU[15]"
replace redcap_event_name="suivi__mois_18__si_arm_4" if v19=="M18 WASHOU[11]"

replace redcap_event_name="suivi__mois_21__si_arm_4" if v19=="M21[7]"
replace redcap_event_name="suivi__mois_21__si_arm_4" if v19=="M21 WASHOU[15]"

replace redcap_event_name="suivi__mois_24__si_arm_4" if v19=="M24[8]"
replace redcap_event_name="suivi__mois_24__si_arm_4" if v19=="M24 WASHOU[12]"

*gen redcap_repeat_instrument=""
*gen redcap_repeat_instance=""
gen redcap_data_access_group=""
gen lims_tab_id="LIMS"
*


*drop D E L P Q R S T U V W AE AF AG AH AI AJ AK AL AN AO AP AS AT BY Y Z AA AB BX F I K N X J
*drop B C D E F G H I  K L M N O  R S T U V W X  Z AA AB AC AD AE AF AG AH AI AJ AK AL AM AN AO AP AQ AR  AU AV AW AX AY AZ BA BB BC  BE BF BG BH BI BJ BK  CO

drop v2 v3 v4 v5 v6 v8 v9 v10 v11 v12 v13 v14 v15 v18 v19 v20 v21 v22 v23 v24 v26 v27 v28 v29 v30 v31 v32 v33 v34 v35 v36 v37 v38 v39 v40 v41 v42 v43 v44  v47 v48 v49 v50 v51 v52 v53 v54 v55  v57 v58 v59 v60 v61 v62 v63 v93

*gen test=2
*ren test  labo_prlvements_biologiques_sousetude_mdf_lims_complete
*drop CC

* Repar jan date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Janv", "/01/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Janv", "/01/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Janv", "/01/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Janv", "/01/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Janv", "/01/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Janv", "/01/", .) 

* Repar feb date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Févr", "/02/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Févr", "/02/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Févr", "/02/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Févr", "/02/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Févr", "/02/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Févr", "/02/", .) 


* Repar march date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Mars", "/03/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Mars", "/03/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Mars", "/03/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Mars", "/03/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Mars", "/03/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Mars", "/03/", .) 

* Repar april date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Avr", "/04/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Avr", "/04/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Avr", "/04/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Avr", "/04/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Avr", "/04/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Avr", "/04/", .) 

* Repar MAY date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Mai", "/05/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Mai", "/05/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Mai", "/05/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Mai", "/05/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Mai", "/05/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Mai", "/05/", .) 

* Repar JUNE date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Juin", "/06/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Juin", "/06/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Juin", "/06/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Juin", "/06/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Juin", "/06/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Juin", "/06/", .) 

* Repar JULY date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Juil", "/07/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Juil", "/07/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Juil", "/07/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Juil", "/07/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Juil", "/07/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Juil", "/07/", .) 

* Repar August date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Août", "/08/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Août", "/08/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Août", "/08/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Août", "/08/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Août", "/08/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Août", "/08/", .) 

* Repar SEP date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Sept", "/09/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Sept", "/09/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Sept", "/09/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Sept", "/09/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Sept", "/09/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Sept", "/09/", .) 

* Repar OCT date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Oct", "/10/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Oct", "/10/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Oct", "/10/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Oct", "/10/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Oct", "/10/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Oct", "/10/", .) 

* Repar NOV date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Nov", "/11/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Nov", "/11/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Nov", "/11/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Nov", "/11/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Nov", "/11/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Nov", "/11/", .) 

* Repar August date that was in frenc car
replace lims_date_reçu_en_lab = subinstr(lims_date_reçu_en_lab, "Déc", "/12/", .) 
replace lims_sal0_colda = subinstr(lims_sal0_colda, "Déc", "/12/", .) 
replace lims_sal3_colda = subinstr(lims_sal3_colda, "Déc", "/12/", .) 
replace lims_sal4_colda = subinstr(lims_sal4_colda, "Déc", "/12/", .) 
replace lims_sel_colse = subinstr(lims_sel_colse, "Déc", "/12/", .) 
replace lims_pl_colda = subinstr(lims_pl_colda, "Déc", "/12/", .) 

drop in 1

gen lims_date_reçu_en_lab_var = date(lims_date_reçu_en_lab , "DMY")
gen lims_sal0_colda_var = date(lims_sal0_colda , "DMY")
gen lims_sal3_colda_var = date(lims_sal3_colda , "DMY")
gen lims_sal4_colda_var = date(lims_sal4_colda , "DMY")
gen lims_sel_colse_var = date(lims_sel_colse , "DMY")
gen lims_pl_colda_colse_var = date(lims_pl_colda , "DMY")
     
drop lims_date_reçu_en_lab lims_sal0_colda lims_sal3_colda lims_sal4_colda lims_sel_colse lims_pl_colda

rename lims_date_reçu_en_lab* lims_date_reçu_en_lab
rename lims_sal0_colda* lims_sal0_colda
rename lims_sal3_colda* lims_sal3_colda
rename lims_sal4_colda* lims_sal4_colda
rename lims_sel_colse* lims_sel_colse
rename lims_pl_colda* lims_pl_colda

format  %tdCCYY-NN-DD lims_date_reçu_en_lab lims_sal0_colda lims_sal3_colda lims_sal4_colda lims_sel_colse lims_pl_colda

gen redcap_repeat_instrument="labo_prlvements_biologiques_sousetude_mdf_lims"
gsort patid  redcap_event_name
bys patid  redcap_event_name (lims_date_reçu_en_lab):  gen  redcap_repeat_instance=_n


*order patid redcap_repeat_instrument redcap_event_name redcap_repeat_instance redcap_data_access_group lims_tab_id lims_laboratoire lims_site1 lims_essaiclin lims_essai_clinique lims_id_participant lims_age lims_sexe *
order  patid redcap_repeat_instrument redcap_event_name redcap_repeat_instance redcap_data_access_group lims_tab_id lims_laboratoire lims_site1 lims_essaiclin lims_essai_clinique lims_id_participant lims_age lims_sexe lims_date_reçu_en_lab lims_heure_reçu_en_lab lims_inspar lims_mdft_sal0 lims_sal0_colda lims_sal0_colti lims_sal0_aliqu lims_sal0_samca lims_d2o_dose_saliva_h0 lims_mdft_sal3 lims_sal3_colda lims_sal3_colti lims_sal3_aliqu lims_sal3_samcb lims_sal4_sal4 lims_sal4_colda lims_sal4_colti lims_sal4_aliqu lims_sal4_samcc lims_mdft_sel lims_sel_colse lims_sel_colti lims_sel_stoti lims_sel_aliqu lims_sel_samcd lims_mdft_pl lims_pl_colda lims_pl_colti lims_pl_centi lims_pl_stoti lims_pl_aliqu lims_pl_samco

drop  v94 v95 v96 v97 v98 v99 v100 v101
*drop v94 v95 v96 v97 v98 v99 v100 v101 v102 v103

ren lims_heure_reçu_en_lab lims_heure_reu_en_lab

ren lims_date_reçu_en_lab lims_date_reu_en_lab

save "D:\MSF\GRP-EPI-PROJ-Microbiome-directed Food (MDF) Trial - Documents\Dossier_Interne_Epicentre\MDF_Data management\9 - Lab_ Data\2 - Data - Redcap import\For import in Redcap\Ready_Data_26_08_13.dta", replace

export delimited using "D:\MSF\GRP-EPI-PROJ-Microbiome-directed Food (MDF) Trial - Documents\Dossier_Interne_Epicentre\MDF_Data management\9 - Lab_ Data\2 - Data - Redcap import\For import in Redcap\Ready_Data_26_08_13.csv", replace
