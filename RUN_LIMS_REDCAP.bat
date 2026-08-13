@echo off
REM ==========================================================================
REM  LIMS -> REDCap MDF  -  lanceur Windows (v1.0)
REM
REM  Utilisation :
REM    1. placer l'extraction LIMS .xlsx dans le dossier  input\
REM    2. double-cliquer sur ce fichier
REM
REM  La fenetre reste ouverte a la fin (elle ne se ferme pas automatiquement).
REM ==========================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM Choix de l'interpreteur Python (py -3 si disponible, sinon python)
set "PYEXE=python"
where py >nul 2>nul && set "PYEXE=py -3"

%PYEXE% "run_pipeline.py"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo [Termine sans erreur bloquante.]
) else (
    echo [Termine avec des reserves - code %RC%. Voir le tableau de bord et le journal ci-dessus.]
)
echo.
echo Appuyez sur une touche pour fermer cette fenetre...
pause >nul
endlocal
