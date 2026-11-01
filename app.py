"""Application « Recherche de stage » : http://localhost:5000"""
import re
import threading
import unicodedata
import webbrowser
from datetime import datetime

import requests
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

import analyse
import cv_adapt
import sources
import stockage
import verifier

app = Flask(__name__)
app.jinja_env.globals.update(LIEU_LABEL=analyse.LIEU_LABEL, COMPAT_LABEL=analyse.COMPAT_LABEL,
                             DOMAINE_LABEL=analyse.DOMAINE_LABEL)

verif = {"en_cours": False, "journal": [], "fin": None}


def _lancer_verification(ids=None):
    if verif["en_cours"]:
        return False
    verif.update(en_cours=True, journal=[], fin=None)

    def tache():
        try:
            verifier.verifier(ids, journal=verif["journal"].append)
        except Exception as ex:
            verif["journal"].append(f"Erreur : {ex}")
        finally:
            verif.update(en_cours=False, fin=datetime.now().isoformat(timespec="seconds"))

    threading.Thread(target=tache, daemon=True).start()
    return True


def _slug(nom):
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "entreprise"


# ---------------------------------------------------------------- pages

@app.route("/")
def accueil():
    ents = {e["id"]: e for e in stockage.entreprises()}
    liste = [o for o in stockage.offres().values()
             if verifier.a_afficher(o) and o["entreprise_id"] in ents]
    ordre = {"ok": 0, "proche": 1, "inconnu": 2, "ko": 3}
    liste.sort(key=lambda o: o["trouve_le"], reverse=True)  # plus récentes d'abord, à compatibilité égale
    liste.sort(key=lambda o: (not o["en_ligne"], ordre[o["compat"]["statut"]]))
    offres_js = [{k: o.get(k) for k in ("id", "entreprise", "entreprise_id", "titre", "url", "lieu", "lieu_statut",
                                        "compat", "domaines", "but", "missions", "trouve_le", "publie_le", "en_ligne",
                                        "suivi", "initial")} for o in liste]
    return render_template("accueil.html", offres=offres_js, entreprises=sorted(ents.values(), key=lambda e: e["nom"]),
                           etat=stockage.etat(), verif=verif)


@app.route("/cv")
@app.route("/cv/<oid>")
def cv(oid=None):
    offre = None
    if oid:
        offre = stockage.offres().get(oid) or abort(404)
    cv_, infos = cv_adapt.adapter(offre)
    photo = url_for("static", filename=cv_["photo"]) if cv_.get("photo") else None
    return render_template("cv.html", cv=cv_, offre=offre, infos=infos, photo_url=photo, site=False)


@app.route("/cv/<oid>/analyse")
def cv_analyse(oid):
    offre = stockage.offres().get(oid) or abort(404)
    return jsonify(cv_adapt.adapter(offre)[1])


@app.route("/entreprises")
def entreprises():
    return render_template("entreprises.html", entreprises=sorted(stockage.entreprises(), key=lambda e: e["nom"]),
                           etat=stockage.etat(), offres=stockage.offres())


@app.post("/entreprises/ajouter")
def entreprise_ajouter():
    nom, url = request.form["nom"].strip(), request.form["url"].strip()
    ents = stockage.entreprises()
    base, eid, n = _slug(nom), _slug(nom), 2
    while any(e["id"] == eid for e in ents):
        eid, n = f"{base}-{n}", n + 1
    ents.append({"id": eid, "nom": nom, "secteur": request.form.get("secteur", "").strip(),
                 "lieu": request.form.get("lieu", "").strip(), "pourquoi": request.form.get("pourquoi", "").strip(),
                 "url_carrieres": url, "source": sources.detecter(url), "actif": True})
    stockage.ecrire("entreprises.json", ents)
    _lancer_verification([eid])
    return redirect(url_for("entreprises"))


@app.post("/entreprises/<eid>/supprimer")
def entreprise_supprimer(eid):
    stockage.ecrire("entreprises.json", [e for e in stockage.entreprises() if e["id"] != eid])
    stockage.ecrire("offres.json", {k: v for k, v in stockage.offres().items() if v["entreprise_id"] != eid})
    return redirect(url_for("entreprises"))


@app.post("/entreprises/<eid>/basculer")
def entreprise_basculer(eid):
    ents = stockage.entreprises()
    for e in ents:
        if e["id"] == eid:
            e["actif"] = not e.get("actif", True)
    stockage.ecrire("entreprises.json", ents)
    return redirect(url_for("entreprises"))


@app.route("/reglages", methods=["GET", "POST"])
def reglages():
    cfg = stockage.config()
    message = None
    if request.method == "POST":
        if request.form.get("action") == "test":
            try:
                requests.post(cfg["ntfy_serveur"], timeout=15, json={
                    "topic": cfg["ntfy_sujet"], "title": "Recherche de stage – test",
                    "message": "Les notifications fonctionnent ! Touchez-moi pour ouvrir l'app de recherche.",
                    "tags": ["white_check_mark"], "click": "https://ntfy.sh"}).raise_for_status()
                message = "Notification de test envoyée : regarde ton téléphone."
            except requests.RequestException as ex:
                message = f"Échec de l'envoi : {ex}"
        else:
            cfg["ntfy_sujet"] = request.form["ntfy_sujet"].strip() or cfg["ntfy_sujet"]
            cfg["notifier_compat"] = request.form.getlist("notifier_compat")
            cfg["notifier_lieux"] = request.form.getlist("notifier_lieux")
            stockage.ecrire("config.json", cfg)
            message = "Réglages enregistrés."
    return render_template("reglages.html", cfg=cfg, message=message)


# ---------------------------------------------------------------- API

@app.post("/api/verifier")
def api_verifier():
    ids = request.json.get("ids") if request.is_json else None
    return jsonify(lance=_lancer_verification(ids))


@app.get("/api/verification")
def api_verification():
    return jsonify(verif)


@app.post("/api/offre/<oid>/suivi")
def api_suivi(oid):
    toutes = stockage.offres()
    if oid not in toutes:
        abort(404)
    toutes[oid]["suivi"] = request.json["suivi"]
    stockage.ecrire("offres.json", toutes)
    return jsonify(ok=True)


if __name__ == "__main__":
    stockage.config()
    import sys
    if "--sans-navigateur" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(port=5000, debug=False)
