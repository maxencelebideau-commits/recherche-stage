"""Lettre de motivation locale (sans IA) pour une offre.

La lettre ne s'appuie que sur des expériences réelles du CV : elle choisit celles qui
correspondent aux thèmes de l'offre et cite les missions de l'offre, mais n'affirme
jamais une compétence demandée qui n'est pas dans le CV."""
import re
from datetime import date

import analyse
import cv_adapt

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]

# Expériences du CV racontées en une phrase, avec les thèmes qu'elles illustrent.
EXPERIENCES = [
    {"themes": {"industrie": 3, "terrain": 3, "qualite": 2, "equipe": 1, "logistique": 1},
     "texte": "Lors de mon stage ouvrier à l'usine Stellantis de Poissy (juillet 2026), j'ai travaillé sur une ligne "
              "d'assemblage automobile, au rythme de la chaîne, au contact des opérateurs et des chefs d'équipe."},
    {"themes": {"simulation": 3, "mesure": 3, "acoustique": 3, "batiment": 2, "data": 2, "mecanique": 2,
                "projet": 1, "conseil": 2, "equipe": 1},
     "texte": "À Centrale Lyon, j'ai mené en équipe la correction acoustique d'un amphithéâtre en plein air : "
              "identification d'un problème d'écho, quantification par des mesures sur site et une simulation "
              "numérique (SketchUp, CATT-Acoustic, traitement des données sous MATLAB), puis conception et mise "
              "en place de solutions correctives."},
    {"themes": {"projet": 3, "negociation": 3, "equipe": 2, "logistique": 1, "conseil": 1},
     "texte": "Responsable site du week-end d'intégration de Centrale Lyon, un événement de plus de 750 participants, "
              "j'ai recherché le lieu, négocié et signé le contrat d'hébergement, en coordination avec les pôles "
              "communication et logistique."},
    {"themes": {"budget": 3, "projet": 2, "equipe": 1},
     "texte": "Au sein du Bureau des Sports, je participe à la gestion administrative et financière de 18 clubs "
              "sportifs et à l'organisation d'événements inter-associations."},
    {"themes": {"logistique": 3},
     "texte": "Lors d'un stage chez Acanthe (Rueil-Malmaison), j'ai géré des stocks et traité des commandes en "
              "entrepôt."},
]

# Ce que chaque thème a réellement apporté (complète « Ces expériences m'ont familiarisé avec … »).
APPORTS = {
    "conseil": "une démarche structurée : identifier un problème, le quantifier puis proposer des solutions",
    "data": "l'exploitation de données pour étayer une décision",
    "simulation": "la modélisation et la simulation numérique",
    "mesure": "la conduite de mesures sur le terrain",
    "acoustique": "la résolution d'un problème technique concret, du diagnostic à la solution",
    "batiment": "un projet d'ingénierie appliqué à un ouvrage réel",
    "mecanique": "la conception de solutions techniques",
    "industrie": "la réalité d'une production industrielle en grande série",
    "terrain": "les contraintes du terrain",
    "qualite": "les exigences de cadence et de qualité",
    "projet": "l'organisation et la coordination d'un projet",
    "negociation": "la négociation avec des partenaires extérieurs",
    "equipe": "le travail en équipe",
    "budget": "le suivi administratif et financier",
    "logistique": "la gestion des flux et des stocks",
}

MOTIVATION = {
    "energie": "La transition énergétique est un domaine qui m'attire particulièrement ; ce stage serait pour moi "
               "l'occasion de découvrir concrètement ses enjeux aux côtés de vos équipes.",
    "conseil": "Le conseil m'attire pour la diversité des problématiques rencontrées et le travail au contact des "
               "clients ; ce stage serait pour moi l'occasion de découvrir ce métier de l'intérieur.",
    "industrie": "L'ingénierie industrielle m'attire pour son lien direct avec le terrain ; ce stage me permettrait "
                 "d'approfondir ce que j'ai découvert en usine.",
}


def _citation(texte, n=150):
    """Extrait court d'une mission de l'offre, coupé proprement, pour être cité entre guillemets."""
    texte = re.sub(r"\s+", " ", texte).strip(" .,;:-–•")
    if len(texte) > n:
        texte = texte[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return texte


# Phrases de présentation ou d'avantages RH, à ne pas citer comme missions.
GENERIQUE_RE = re.compile(r"^(vous|au sein|accompagn|dans le cadre|jamais|pour |ainsi|en tant que|tout au long|"
                          r"rejoign|developpez|apprenez|explorez|beneficiez|de |d'|la persona|nous |notre |chez )")


def _missions_a_citer(offre, th):
    """Deux missions concrètes de l'offre, de préférence liées aux thèmes de ton CV."""
    candidates = []
    for i, m in enumerate(offre.get("missions", [])):
        n = analyse.norm(m).strip()
        if not 20 <= len(m) <= 170 or m.rstrip().endswith(":") or GENERIQUE_RE.match(n):
            continue
        pertinence = sum(1 for t in th if analyse.THEMES_RE[t].search(n))
        candidates.append((-pertinence, i, m))
    return [_citation(m) for _, _, m in sorted(candidates)[:2]]


def _de(nom):
    return ("d'" if analyse.norm(nom)[:1] in "aeiouyh" else "de ") + nom


def _liste(elements):
    return ", ".join(elements[:-1]) + " et " + elements[-1] if len(elements) > 1 else elements[0]


def generer(offre):
    """Renvoie la lettre sous forme de paragraphes (texte brut) et la compatibilité avec le profil."""
    _, infos = cv_adapt.adapter(offre, public=True)
    th = offre.get("themes") or analyse.themes_offre(offre["titre"], offre.get("texte", ""))
    doms = offre.get("domaines") or analyse.domaines(th)
    titre = re.sub(r"^(stage|internship)\s*[:\-–]?\s*", "", cv_adapt.titre_propre(offre["titre"]), flags=re.I)
    titre = titre[:1].upper() + titre[1:]
    entreprise = offre["entreprise"]

    paragraphes = [
        f"Élève-ingénieur généraliste en 2e année à l'École Centrale de Lyon, je vous adresse ma candidature pour "
        f"le stage « {titre} » au sein {_de(entreprise)}, pour une durée de trois mois, de mai à juillet 2027."]

    missions = _missions_a_citer(offre, th)
    if missions:
        paragraphes.append("Les missions que vous décrivez, notamment "
                           + _liste([f"« {m} »" for m in missions]) + ", ont retenu mon attention.")
    else:
        paragraphes.append("Votre offre a retenu toute mon attention.")
    dom = max(doms, key=doms.get) if doms else None
    if dom in MOTIVATION:
        paragraphes[-1] += " " + MOTIVATION[dom]

    # Les deux expériences du CV les plus proches de l'offre (trois si la troisième est aussi pertinente).
    def score(e):
        return sum(min(th.get(t, 0), 6) * p for t, p in e["themes"].items())
    classees = sorted(EXPERIENCES, key=lambda e: -score(e))
    choisies = [e for e in classees[:3] if score(e) > 0][:3]
    if len(choisies) == 3 and score(choisies[2]) < score(choisies[0]) / 2:
        choisies = choisies[:2]
    if len(choisies) < 2:
        choisies = (choisies + [e for e in EXPERIENCES[:2] if e not in choisies])[:2]
    paragraphes.append(" ".join(e["texte"] for e in choisies))

    # Apports réels de ces expériences, dans l'ordre d'importance pour l'offre.
    themes_exp = {t for e in choisies for t in e["themes"]}
    apports = []
    for t in sorted(themes_exp & set(APPORTS), key=lambda t: -th.get(t, 0)):
        if th.get(t, 0) and APPORTS[t] not in apports:
            apports.append(APPORTS[t])
        if len(apports) == 3:
            break
    if not apports:
        apports = [APPORTS["projet"], APPORTS["equipe"]]
    paragraphes[-1] += f" Ces expériences m'ont familiarisé avec {_liste(apports)}."

    paragraphes.append("Disponible pour un stage de trois mois, de mai à juillet 2027, je serais heureux de vous "
                       "présenter plus en détail ma motivation lors d'un entretien.")
    paragraphes.append("Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.")

    aujourd_hui = date.today()
    return {
        "objet": f"Candidature – Stage « {titre} » (3 mois, mai – juillet 2027)",
        "date": f"Le {aujourd_hui.day} {MOIS[aujourd_hui.month - 1]} {aujourd_hui.year}",
        "paragraphes": paragraphes,
    }, infos
