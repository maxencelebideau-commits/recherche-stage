@echo off
rem Supprime la tache de verification automatique des offres.
schtasks /delete /f /tn "Recherche stage - verification des offres"
pause
