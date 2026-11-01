"""Génère le site statique publié sur GitHub Pages (dossier site/).

Le site ne contient ni coordonnées ni photo : elles sont saisies sur le téléphone
et restent dans son stockage local."""
import json
import shutil
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

import analyse
import cv_adapt
import stockage
import verifier

SITE = stockage.RACINE / "site"


def generer():
    shutil.rmtree(SITE, ignore_errors=True)  # peut échouer en partie sous Windows si le dossier est ouvert
    (SITE / "cv").mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(stockage.RACINE / "templates"), autoescape=True)
    gabarit_cv = env.get_template("cv.html")

    ents = {e["id"]: e for e in stockage.entreprises()}
    offres = [o for o in stockage.offres().values()
              if o["en_ligne"] and verifier.a_afficher(o) and o["entreprise_id"] in ents]
    ordre = {"ok": 0, "proche": 1, "inconnu": 2, "ko": 3}
    offres.sort(key=lambda o: o["trouve_le"], reverse=True)
    offres.sort(key=lambda o: ordre[o["compat"]["statut"]])

    liste = []
    for o in offres:
        cv, infos = cv_adapt.adapter(o, public=True)
        (SITE / "cv" / f"{o['id']}.html").write_text(
            gabarit_cv.render(cv=cv, offre=o, infos=infos, photo_url=None, site=True), encoding="utf-8")
        liste.append({**{k: o.get(k) for k in ("id", "entreprise", "entreprise_id", "titre", "url", "lieu",
                                                "lieu_statut", "compat", "domaines", "but", "missions",
                                                "trouve_le", "initial")}, "analyse": infos})
    cv, _ = cv_adapt.adapter(None, public=True)
    (SITE / "cv" / "moi.html").write_text(
        gabarit_cv.render(cv=cv, offre=None, infos=None, photo_url=None, site=True), encoding="utf-8")

    (SITE / "index.html").write_text(env.get_template("site_index.html").render(
        offres=liste, entreprises=sorted(ents.values(), key=lambda e: e["nom"]), etat=stockage.etat(),
        maj=datetime.now().strftime("%d/%m/%Y à %H:%M"), COMPAT_LABEL=analyse.COMPAT_LABEL,
        LIEU_LABEL=analyse.LIEU_LABEL, DOMAINE_LABEL=analyse.DOMAINE_LABEL), encoding="utf-8")
    shutil.copy(stockage.RACINE / "static" / "style.css", SITE / "style.css")
    (SITE / ".nojekyll").write_text("")
    print(f"Site généré : {len(liste)} offres, {SITE}")


if __name__ == "__main__":
    generer()
