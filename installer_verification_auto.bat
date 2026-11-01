@echo off
rem Cree une tache Windows qui verifie les offres toutes les heures (sans fenetre)
rem et envoie les notifications sur le telephone. A lancer une seule fois.
cd /d "%~dp0"
for /f "delims=" %%P in ('where pythonw') do (set "PYW=%%P" & goto :trouve)
echo pythonw introuvable : installe Python puis relance ce fichier.
pause
exit /b 1
:trouve
schtasks /create /f /tn "Recherche stage - verification des offres" /sc hourly /mo 1 ^
  /tr "\"%PYW%\" \"%~dp0verifier.py\" --journal"
if errorlevel 1 (
  echo Echec de la creation de la tache.
) else (
  echo.
  echo Tache creee : les offres seront verifiees toutes les heures tant que le PC est allume.
  echo Journal : data\verification.log
  echo Pour la supprimer : desinstaller_verification_auto.bat
)
pause
