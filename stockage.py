"""Lecture / écriture des fichiers JSON du dossier data/."""
import json
import os
import secrets
import threading
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DATA = RACINE / "data"
_verrou = threading.RLock()


def lire(nom, defaut=None):
    f = DATA / nom
    with _verrou:
        if not f.exists():
            return defaut
        return json.loads(f.read_text(encoding="utf-8"))


def ecrire(nom, valeur):
    f = DATA / nom
    tmp = f.with_suffix(".tmp")
    with _verrou:
        tmp.write_text(json.dumps(valeur, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, f)


def config():
    c = lire("config.json")
    if not c:
        c = {"ntfy_sujet": "stage-maxence-" + secrets.token_hex(4), "ntfy_serveur": "https://ntfy.sh",
             "notifier_compat": ["ok", "proche", "inconnu"], "notifier_lieux": ["ok", "idf", "inconnu"]}
        ecrire("config.json", c)
    # Sur GitHub, le sujet ntfy (secret) et l'adresse du site viennent des variables d'environnement.
    # Sans secret NTFY_SUJET sur GitHub, sujet vide = pas de notification.
    c["ntfy_sujet"] = os.environ.get("NTFY_SUJET") or ("" if os.environ.get("GITHUB_ACTIONS") else c["ntfy_sujet"])
    c["site_url"] = os.environ.get("SITE_URL") or c.get("site_url", "")
    return c


def cv():
    """CV public (cv.json) complété par les coordonnées et la photo, gardées hors du dépôt."""
    c = lire("cv.json")
    c.update(lire("contact_prive.json", {"contact": [], "photo": None}))
    return c


def entreprises():
    return lire("entreprises.json", [])


def offres():
    return lire("offres.json", {})


def etat():
    return lire("etat.json", {})
