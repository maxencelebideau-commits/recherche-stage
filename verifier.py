"""Vérifie les sites carrières des entreprises suivies, enregistre les offres de stage
et envoie une notification sur le téléphone (ntfy) pour chaque nouvelle offre pertinente.

Usage : python verifier.py            (toutes les entreprises)
        python verifier.py wavestone  (une seule entreprise, par identifiant)"""
import hashlib
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

import analyse
import sources
import stockage

MAX_DETAILS = 60  # fiches détaillées chargées au plus par entreprise et par passage


def _id(entreprise_id, uid):
    return hashlib.sha1(f"{entreprise_id}|{uid}".encode()).hexdigest()[:12]


def a_afficher(o):
    return o.get("stage") and o.get("pertinente") and o.get("lieu_statut") != "hors"


def a_notifier(o, cfg):
    return (a_afficher(o) and o["compat"]["statut"] in cfg["notifier_compat"]
            and o["lieu_statut"] in cfg["notifier_lieux"])


def notifier(o, cfg):
    lignes = [f"📍 {o['lieu'] or analyse.LIEU_LABEL[o['lieu_statut']]}  ·  {analyse.COMPAT_LABEL[o['compat']['statut']]}"]
    if o["compat"]["detail"]:
        lignes.append(o["compat"]["detail"])
    if o.get("but"):
        lignes.append("🎯 " + o["but"][:300])
    for m in o.get("missions", [])[:3]:
        lignes.append("• " + m[:160])
    actions = [{"action": "view", "label": "Voir l'offre / postuler", "url": o["url"]}]
    if cfg.get("site_url"):
        actions.append({"action": "view", "label": "CV adapté", "url": f"{cfg['site_url'].rstrip('/')}/cv/{o['id']}.html"})
    requests.post(cfg["ntfy_serveur"], timeout=15, json={
        "topic": cfg["ntfy_sujet"],
        "title": f"{o['entreprise']} – {o['titre']}"[:200],
        "message": "\n".join(lignes)[:3500],
        "click": o["url"],
        "tags": ["briefcase"],
        "priority": 4,
        "actions": actions,
    }).raise_for_status()


def verifier_entreprise(e, toutes, cfg, notif=True):
    """Met à jour `toutes` (dict des offres) pour l'entreprise e. Renvoie un résumé."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    brutes = sources.recuperer(e["source"])
    premiere_fois = not stockage.etat().get(e["id"], {}).get("initialise")
    vus, nouvelles, details = set(), [], 0
    for b in brutes:
        oid = _id(e["id"], b["uid"])
        vus.add(oid)
        if oid in toutes:
            toutes[oid]["en_ligne"] = True
            continue
        # Préfiltre sur le titre / lieu avant de charger la fiche complète.
        if not analyse.est_stage(b["titre"], b.get("contrat", ""), b.get("description_html", "")[:2000] if b.get("description_html") else "") \
                and e["source"]["type"] != "html":
            continue
        if b.get("lieu") and analyse.lieu_statut(b["lieu"]) == "hors":
            continue
        if "detail" in b:
            if details >= MAX_DETAILS:
                continue
            details += 1
            try:
                b.update({k: v for k, v in b.pop("detail")().items() if v})
            except Exception as ex:  # fiche inaccessible : on garde l'offre sans description
                b.pop("detail", None)
                b.setdefault("description_html", "")
                print(f"  ! fiche illisible {b['url']}: {ex}")
        a = analyse.analyser(b["titre"], b.get("lieu", ""), b.get("description_html", ""), b.get("contrat", ""))
        o = {"id": oid, "entreprise_id": e["id"], "entreprise": e["nom"], "titre": b["titre"], "url": b["url"],
             "lieu": b.get("lieu", "")[:150], "publie_le": b.get("publie_le", ""), "trouve_le": maintenant,
             "en_ligne": True, "suivi": "a_traiter", "initial": premiere_fois,
             "texte": analyse.html_vers_texte(b.get("description_html", ""))[:20000], **a}
        toutes[oid] = o
        if a_afficher(o):
            nouvelles.append(o)
    for oid, o in toutes.items():
        if o["entreprise_id"] == e["id"] and oid not in vus:
            o["en_ligne"] = False
    envoyees = 0
    if notif and not premiere_fois and cfg["ntfy_sujet"]:
        for o in nouvelles:
            if a_notifier(o, cfg):
                try:
                    notifier(o, cfg)
                    envoyees += 1
                except requests.RequestException as ex:
                    print(f"  ! notification échouée : {ex}")
    return {"trouvees": len(brutes), "stages": sum(1 for o in toutes.values()
                                                   if o["entreprise_id"] == e["id"] and o["en_ligne"] and a_afficher(o)),
            "nouvelles": len(nouvelles), "notifiees": envoyees, "premiere_fois": premiere_fois}


def verifier(ids=None, notif=True, journal=print):
    cfg = stockage.config()
    ents = [e for e in stockage.entreprises() if e.get("actif", True) and (not ids or e["id"] in ids)]

    def une(e):
        toutes_e = {k: v for k, v in stockage.offres().items() if v["entreprise_id"] == e["id"]}
        try:
            r = verifier_entreprise(e, toutes_e, cfg, notif)
            return e, toutes_e, r, None
        except Exception as ex:
            return e, toutes_e, None, f"{type(ex).__name__}: {ex}"

    with ThreadPoolExecutor(max_workers=6) as pool:
        resultats = list(pool.map(une, ents))

    toutes, etat = stockage.offres(), stockage.etat()
    maintenant = datetime.now().isoformat(timespec="seconds")
    for e, offres_e, r, err in resultats:
        if err:
            etat[e["id"]] = {**etat.get(e["id"], {}), "derniere": maintenant, "erreur": err}
            journal(f"✗ {e['nom']} : {err}")
            continue
        for k, v in offres_e.items():  # garde le suivi modifié dans l'app pendant la vérification
            if k in toutes:
                v["suivi"] = toutes[k].get("suivi", v["suivi"])
        toutes.update(offres_e)
        etat[e["id"]] = {"derniere": maintenant, "initialise": True, "erreur": None, **r}
        journal(f"✓ {e['nom']} : {r['trouvees']} offres lues, {r['stages']} stages pertinents en ligne, "
                f"{r['nouvelles']} nouveaux, {r['notifiees']} notifiés")
    stockage.ecrire("offres.json", toutes)
    stockage.ecrire("etat.json", etat)
    return resultats


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--journal" in sys.argv or sys.stdout is None:  # lancé par la tâche planifiée (pythonw, sans console)
        sys.stdout = sys.stderr = open(stockage.DATA / "verification.log", "a", encoding="utf-8")
        print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} ===")
    elif hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        verifier(args or None)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    finally:
        sys.stdout.flush()
