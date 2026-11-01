@echo off
rem Ouvre l'application de recherche de stage dans le navigateur (http://localhost:5000).
rem Ferme cette fenetre pour arreter l'application.
cd /d "%~dp0"
python app.py
pause
