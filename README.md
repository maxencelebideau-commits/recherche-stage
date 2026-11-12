# Recherche de stage – mai à juillet 2027

Application locale qui surveille les sites carrières des entreprises choisies, garde les stages
à Paris / 92 dans l'énergie, le conseil et l'industrie, t'envoie une notification sur ton téléphone
pour chaque nouvelle offre et affiche ton CV adapté à côté de chaque offre.

## Démarrer

1. Double-clique sur **`lancer_app.bat`** : l'app s'ouvre sur http://localhost:5000
2. Onglet **Notifications** : installe l'app *ntfy* sur ton téléphone et abonne-toi au sujet affiché, puis « Envoyer un test ».
3. Double-clique une fois sur **`installer_verification_auto.bat`** : les offres sont vérifiées toutes les heures,
   même app fermée (PC allumé). Pour arrêter : `desinstaller_verification_auto.bat`.

Prérequis : Python 3.11 avec `pip install flask requests beautifulsoup4` (déjà fait sur ce PC).

## Version en ligne (iPhone) avec GitHub

Le workflow `.github/workflows/verifier.yml` tourne toutes les heures sur GitHub (PC éteint possible) :
il vérifie les offres, envoie les notifications ntfy, enregistre `data/offres.json` et publie le site
sur `https://<ton-pseudo>.github.io/<nom-du-depot>/`.

- **Secret à créer** dans le dépôt : *Settings → Secrets and variables → Actions → New repository secret*,
  nom `NTFY_SUJET`, valeur = ton sujet ntfy. Sans lui, aucune notification n'est envoyée.
- **Pages** : *Settings → Pages → Source : GitHub Actions*.
- Le site est public mais ne contient ni coordonnées ni photo : saisis-les une fois dans « Mes coordonnées »
  sur l'iPhone, elles restent sur le téléphone. Le suivi « postulé / ignoré » est aussi gardé sur le téléphone.
- Pour ajouter une entreprise en ligne : modifie `data/entreprises.json` sur github.com (le site se régénère).
- N'installe pas aussi la tâche Windows : tu recevrais chaque notification en double.

## Les pages

| Page | Rôle |
|---|---|
| **Offres** | Toutes les offres en ligne, avec le but, les missions et la compatibilité avec mai–juillet. Clique sur une offre pour voir le CV adapté à droite. « Voir l'offre et postuler » ouvre l'annonce. Le suivi (à traiter / postulé / ignorer) est enregistré. |
| **Entreprises** | Ajouter une entreprise : colle l'adresse de sa page d'offres, le type de site est détecté (SmartRecruiters, Workday, Teamtailor, Greenhouse, Lever, flux JSON, sinon lecture de la page). |
| **Mon CV** | Ton CV d'origine. Le CV adapté s'ouvre via « Ouvrir / PDF » puis « Enregistrer en PDF ». |
| **Notifications** | Sujet ntfy, test, et choix des offres notifiées. |

## Comment le CV est adapté (sans IA)

- une accroche personnalisée (entreprise, poste, domaine) qui reprend 2 atouts **réels** de ton CV ;
- des compétences clés communes à l'offre et à ton CV ;
- les sections, expériences et puces réordonnées selon l'offre, mots-clés de l'offre en gras ;
- les logiciels cités dans l'offre mis en avant ;
- un panneau « Adéquation » : ce qui est couvert, ce qui manque, et des conseils pour la lettre.

## Lettre de motivation et compatibilité (sans IA)

Chaque offre a sa lettre (bouton « Lettre », aussi dans la notification) :
- elle cite deux missions concrètes de l'offre et ne raconte que tes expériences réelles les plus proches
  (phrases dans `lettre.py`, à garder fidèles au CV) ; elle n'affirme jamais une compétence demandée absente du CV ;
- clique dans la lettre pour la modifier (gardé sur l'appareil), puis « Enregistrer en PDF » ou « Copier le texte ».

La **compatibilité avec ton profil** (en %) combine les thèmes de l'offre illustrés par ton CV, les dates
(3 mois mai–juillet), le niveau demandé (fin d'études / bac+5 ou 2e année) et les logiciels demandés absents du CV.

Rien n'est inventé : pour modifier le contenu du CV, édite `data/cv.json`
(chaque élément porte des `themes` qui servent au classement).

## Fichiers

- `app.py` : serveur web · `verifier.py` : vérification + notifications · `sources.py` : connecteurs par site
- `analyse.py` : filtres (stage, lieu, dates, domaines) et extraction des missions · `cv_adapt.py` : adaptation du CV
- `data/entreprises.json`, `data/offres.json`, `data/config.json`, `data/verification.log`

Vérification manuelle en ligne de commande : `python verifier.py` (ou `python verifier.py wavestone`).
