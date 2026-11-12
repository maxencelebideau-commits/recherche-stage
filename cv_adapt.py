"""Adaptation locale (sans IA) du CV à une offre.

Le CV n'est jamais enrichi de compétences absentes : on réordonne, on met en avant
ce qui correspond à l'offre et on rédige une accroche à partir d'éléments réels du CV."""
import copy
import html
import re
import unicodedata

import analyse
import stockage

# Atouts réels du CV, mobilisés dans l'accroche selon les thèmes de l'offre.
ATOUTS = {
    "industrie": "une immersion en usine automobile chez Stellantis (production en grande série)",
    "terrain": "une première expérience terrain sur ligne d'assemblage",
    "qualite": "une sensibilité aux contraintes de cadence et de qualité acquise chez Stellantis",
    "simulation": "la pratique de la simulation numérique (CATT-Acoustic, MATLAB)",
    "mesure": "des campagnes de mesures sur site menées en projet",
    "data": "le traitement et l'analyse de données sous MATLAB et Excel",
    "acoustique": "un projet complet de correction acoustique, du diagnostic à la solution",
    "batiment": "un projet d'ingénierie appliqué à un ouvrage réel (amphithéâtre)",
    "mecanique": "la conception de solutions techniques correctives",
    "projet": "la coordination d'un événement de plus de 750 participants",
    "negociation": "la négociation et la signature d'un contrat d'hébergement",
    "budget": "la gestion administrative et financière de 18 clubs sportifs",
    "logistique": "une expérience en gestion de stocks et de flux",
    "equipe": "l'habitude du travail en équipe, en usine comme en projet",
    "conseil": "une démarche d'analyse : identifier un problème, le quantifier, proposer des solutions",
    "communication": "une aisance dans la synthèse et la présentation (PowerPoint, Canva)",
}
CIBLE = {
    "energie": "dans le domaine de l'énergie et de la transition énergétique",
    "conseil": "en conseil",
    "industrie": "en ingénierie industrielle",
}


def _themes_cv(cv):
    """Solidité de chaque thème dans le CV : nombre d'éléments, de puces et de logiciels qui l'illustrent."""
    t = {}
    for s in cv["sections"]:
        for it in s["items"]:
            for x in it["themes"] + [th for p in it["puces"] for th in p["themes"]]:
                t[x] = t.get(x, 0) + 1
    for l in cv["logiciels"]:
        for x in l["themes"]:
            t[x] = t.get(x, 0) + 1
    return t


def titre_propre(titre):
    """« STAGE - AMELIORATION CONTINUE H/F » → « Amelioration continue » : sans H/F ni mention « stage »."""
    t = re.sub(r"\(?\b[HF]\s*/\s*[HF]\b\)?|\(?\b[MF]\s*/\s*[FH]\b\)?", "", titre)
    t = re.sub(r"^\s*(stage|internship)\s*[-–:]\s*", "", t, flags=re.I)
    t = re.sub(r"\s*[-–]\s*(stage( de fin d.?[ée]tudes?)?|internship)\s*$", "", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–")
    if t.isupper():
        t = t.capitalize()
    return t or titre


def _surligner(texte, motifs):
    """Échappe le texte et met en gras les mots-clés de l'offre (comparaison sans accents)."""
    # Normalisation caractère par caractère pour garder les mêmes positions que le texte d'origine.
    sans = "".join((unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode() or c)[:1].lower()
                   for c in texte)
    zones = []
    for rx in motifs:
        for m in rx.finditer(sans):
            if len(m.group(0)) > 3:
                zones.append((m.start(), m.end()))
    zones.sort()
    fusion = []
    for a, b in zones:
        if fusion and a <= fusion[-1][1]:
            fusion[-1] = (fusion[-1][0], max(b, fusion[-1][1]))
        else:
            fusion.append((a, b))
    out, i = [], 0
    for a, b in fusion:
        out += [html.escape(texte[i:a]), "<strong>", html.escape(texte[a:b]), "</strong>"]
        i = b
    out.append(html.escape(texte[i:]))
    return "".join(out)


def adapter(offre=None, public=False):
    """Renvoie (cv adapté, analyse) prêts pour le gabarit cv.html. Sans offre : CV d'origine.
    public=True : sans coordonnées ni photo (site en ligne)."""
    cv = copy.deepcopy(stockage.lire("cv.json") if public else stockage.cv())
    cv.setdefault("contact", [])
    cv.setdefault("photo", None)
    if not offre:
        for s in cv["sections"]:
            for it in s["items"]:
                for p in it["puces"]:
                    p["html"] = html.escape(p["texte"])
        return cv, None

    th = offre.get("themes") or analyse.themes_offre(offre["titre"], offre.get("texte", ""))
    doms = offre.get("domaines") or analyse.domaines(th)
    poids = {k: min(v, 6) for k, v in th.items()}
    motifs = [analyse.THEMES_RE[k] for k in th]

    def score(themes):
        return sum(poids.get(t, 0) for t in themes)

    # Sections (Formation reste en bas), éléments et puces triés par pertinence.
    for s in cv["sections"]:
        for it in s["items"]:
            it["score"] = score(it["themes"]) + sum(score(p["themes"]) for p in it["puces"])
            it["puces"].sort(key=lambda p: -score(p["themes"]))
            for p in it["puces"]:
                p["html"] = _surligner(p["texte"], motifs)
                p["fort"] = score(p["themes"]) > 0
        if not s.get("fixe"):
            s["items"].sort(key=lambda it: -it["score"])
        s["score"] = sum(it["score"] for it in s["items"])
    mobiles = sorted([s for s in cv["sections"] if not s.get("fixe")], key=lambda s: -s["score"])
    cv["sections"] = mobiles + [s for s in cv["sections"] if s.get("fixe")]

    texte_n = analyse.norm(offre.get("texte", ""))
    for l in cv["logiciels"]:
        cite = bool(re.search(r"\b" + re.escape(analyse.norm(l["nom"].split()[0])) + r"\b", texte_n))
        cite = cite or (l["nom"] == "Suite Office" and bool(re.search(r"\b(excel|powerpoint|pack office)\b", texte_n)))
        l["score"] = score(l["themes"]) + (20 if cite else 0)
    cv["logiciels"].sort(key=lambda l: -l["score"])
    for i, l in enumerate(cv["logiciels"]):  # en avant : cités dans l'offre, sinon les 2 plus pertinents
        l["fort"] = l["score"] >= 20 or (i < 2 and l["score"] > 0)

    # Accroche.
    themes_cv = _themes_cv(cv)
    communs = sorted((t for t in th if t in themes_cv and t in ATOUTS), key=lambda t: -th[t])
    atouts = []
    for t in communs:
        if ATOUTS[t] not in atouts:
            atouts.append(ATOUTS[t])
        if len(atouts) == 2:  # au-delà, l'accroche fait déborder le CV d'une page
            break
    dom = max(doms, key=doms.get) if doms else None
    cible = CIBLE.get(dom, "en ingénierie")
    phrase = ", ".join(atouts[:-1]) + (" et " + atouts[-1] if len(atouts) > 1 else (atouts[0] if atouts else ""))
    cv["accroche"] = (f"Élève-ingénieur généraliste en 2<sup>e</sup> année à Centrale Lyon, je recherche un stage de "
                      f"3 mois (mai – juillet 2027) {cible} et souhaite rejoindre {html.escape(offre['entreprise'])}"
                      f" sur le poste « {html.escape(titre_propre(offre['titre']))} ».")
    if phrase:
        cv["accroche"] += f" J'y apporterai {html.escape(phrase)}."
    cv["competences"] = [analyse.THEMES[t][0] for t in communs[:5]]

    # Thèmes peu ou pas illustrés dans le CV (moins de 2 preuves).
    manquants = sorted((t for t in th if themes_cv.get(t, 0) < 2), key=lambda t: -th[t])
    total = sum(poids.values()) or 1
    adequation = round(100 * sum(v * min(1, themes_cv.get(k, 0) / 4) for k, v in poids.items()) / total)
    infos = {
        "adequation": adequation,
        "couverts": [analyse.THEMES[t][0] for t in communs[:6]],
        "manquants": [analyse.THEMES[t][0] for t in manquants],
        "conseils": _conseils(manquants, offre),
    }
    infos["profil"] = profil(offre, infos)
    return cv, infos


# Logiciels souvent demandés, et ceux réellement présents dans le CV.
OUTILS = {"python": "Python", "excel": "Excel", "powerpoint": "PowerPoint", "vba": "VBA", "sql": "SQL",
          "power ?bi": "Power BI", "tableau": "Tableau", "sap": "SAP", "dataiku": "Dataiku", "alteryx": "Alteryx",
          "java": "Java", "c\\+\\+": "C++", "julia": "Julia", "matlab": "MATLAB", "simulink": "Simulink",
          "ansys": "Ansys", "abaqus": "Abaqus", "comsol": "COMSOL", "catia": "CATIA", "solidworks": "SolidWorks",
          "autocad": "AutoCAD", "revit": "Revit", "labview": "LabVIEW", "qgis": "QGIS", "pvsyst": "PVsyst"}
OUTILS_CV = {"Excel", "PowerPoint", "MATLAB"}
NIVEAU_FIN_ETUDES = r"fin d.?etudes|derniere annee|bac ?\+ ?5|master 2|\bm2\b|cesure|futur(e)? diplome"


def profil(offre, infos):
    """Compatibilité de l'offre avec le profil : thèmes du CV, dates, niveau d'études et logiciels demandés."""
    t = analyse.norm(offre["titre"] + "\n" + offre.get("texte", ""))
    forts, attention = [], []
    if infos["couverts"]:
        forts.append("Ton CV illustre : " + ", ".join(infos["couverts"][:4]))
    if infos["manquants"]:
        attention.append("Peu ou pas présent dans ton CV : " + ", ".join(infos["manquants"][:4]))

    statut = offre.get("compat", {}).get("statut", "inconnu")
    note_dates = {"ok": 100, "proche": 60, "inconnu": 50, "ko": 0}[statut]
    if statut == "ok":
        forts.append("Dates compatibles avec 3 mois de mai à juillet 2027")
    elif statut == "ko":
        attention.append("Dates / durée incompatibles (souvent 6 mois)")
    else:
        attention.append("Durée ou dates à confirmer avec l'entreprise")

    note_niveau = 100
    if re.search(NIVEAU_FIN_ETUDES, t):
        note_niveau = 30
        attention.append("Offre plutôt destinée à un stage de fin d'études / bac+5 : tu seras en 2e année")
    elif re.search(r"2e annee|2eme annee|deuxieme annee|bac ?\+ ?4|\bm1\b|assistant ingenieur|stage d.?application", t):
        forts.append("Niveau demandé : 2e année / bac+4, comme toi")

    demandes = [nom for rx, nom in OUTILS.items() if re.search(r"\b" + rx + r"(?!\w)", t)]
    if [n for n in demandes if n in OUTILS_CV]:
        forts.append("Logiciels demandés que tu maîtrises : " + ", ".join(n for n in demandes if n in OUTILS_CV))
    absents = [n for n in demandes if n not in OUTILS_CV]
    if absents:
        attention.append("Logiciels demandés absents de ton CV : " + ", ".join(absents))
    if re.search(r"anglais.{0,20}bilingue|bilingue.{0,20}anglais|bilingual", t):
        attention.append("Anglais bilingue demandé (tu es B2 – C1)")
    elif re.search(r"anglais (courant|professionnel)|fluent|english", t):
        forts.append("Anglais demandé : ton niveau B2 – C1 convient")

    score = round(0.6 * infos["adequation"] + 0.25 * note_dates + 0.15 * note_niveau - min(15, 5 * len(absents)))
    score = max(0, min(100, score))
    verdict = ("Très compatible" if score >= 70 else "Compatible" if score >= 55
               else "Partiellement compatible" if score >= 40 else "Peu compatible")
    return {"score": score, "verdict": verdict, "forts": forts, "attention": attention}


def _conseils(manquants, offre):
    c = []
    if "energie" in manquants:
        c.append("L'offre est centrée sur l'énergie, absente de ton CV : montre ton intérêt dans la lettre "
                 "(cours, lectures, projet perso sur la transition énergétique).")
    if "conseil" in manquants:
        c.append("Pour le conseil, insiste en entretien sur ta démarche du projet acoustique : "
                 "diagnostic → quantification → recommandations.")
    if any(t in manquants for t in ("mecanique", "simulation")):
        c.append("Cite les cours de Centrale (mécanique, modélisation) en lien avec l'offre dans ta lettre.")
    if "data" in manquants:
        c.append("Mentionne ton usage de MATLAB / Excel pour l'analyse de données.")
    if offre.get("compat", {}).get("statut") in ("ko", "inconnu", "proche"):
        c.append("Précise dès le premier message tes dates : 3 mois, de mai à juillet 2027.")
    return c
