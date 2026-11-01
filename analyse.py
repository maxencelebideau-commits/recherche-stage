"""Analyse d'une offre : stage ou non, lieu, compatibilité avec mai–juillet 2027,
domaines, missions et but de l'offre."""
import re
import unicodedata

from bs4 import BeautifulSoup


def norm(s):
    """Minuscules, sans accents, espaces normalisés."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def html_vers_texte(h):
    return BeautifulSoup(h or "", "html.parser").get_text("\n", strip=True)


# ---------------------------------------------------------------- stage ?

STAGE_RE = re.compile(r"\b(stage|stages|stagiaire|intern|internship|trainee|summer job)\b")
EXCLU_TITRE_RE = re.compile(
    r"\b(alternance|alternant|alternante|apprenti|apprentie|apprentissage|cdi|cdd|these|doctorat|phd|"
    r"post-?doc|freelance|doctoral)\b")
VIE_RE = re.compile(r"\bV\.?I\.?E\b")


def est_stage(titre, contrat="", debut_texte=""):
    t = norm(titre)
    if STAGE_RE.search(t):
        return True
    if EXCLU_TITRE_RE.search(t) or VIE_RE.search(titre or ""):
        return False
    if STAGE_RE.search(norm(contrat)):
        return True
    # Titre neutre ("Assistant ingénieur H/F") : on regarde le début du texte.
    return bool(re.search(r"\b(stage|stagiaire|internship)\b", norm(debut_texte)[:600]))


# ---------------------------------------------------------------- lieu

COMMUNES_92 = [
    "antony", "asnieres", "bagneux", "bois-colombes", "boulogne", "bourg-la-reine", "chatenay-malabry",
    "chatillon", "chaville", "clamart", "clichy", "colombes", "courbevoie", "fontenay-aux-roses", "garches",
    "gennevilliers", "issy", "la garenne-colombes", "le plessis-robinson", "levallois", "malakoff",
    "marnes-la-coquette", "meudon", "montrouge", "nanterre", "neuilly", "puteaux", "rueil", "saint-cloud",
    "sceaux", "sevres", "suresnes", "vanves", "vaucresson", "ville-d'avray", "villeneuve-la-garenne",
]
ZONE_RE = re.compile(r"\b(paris|la defense|hauts-de-seine|" + "|".join(re.escape(c) for c in COMMUNES_92) + r")\b")
CP_RE = re.compile(r"\b(75|92)\d{3}\b")
HORS_PARIS_RE = re.compile(r"saclay|massy|orsay|palaiseau|marne-la-vallee|velizy|guyancourt|saint-quentin")


def lieu_statut(lieu, texte=""):
    """'ok' (Paris / 92), 'idf' (Île-de-France sans précision), 'inconnu' ou 'hors'."""
    l = norm(lieu)
    if l and HORS_PARIS_RE.search(l) and not re.search(r"\bparis\b(?!-saclay)", l.replace("paris-saclay", "")):
        return "hors"
    if ZONE_RE.search(l) or CP_RE.search(l):
        return "ok"
    if "ile-de-france" in l or "ile de france" in l:
        return "idf"
    if l and l not in ("france", "fr", "remote", "teletravail"):
        return "hors"
    t = norm(texte[:4000])
    if ZONE_RE.search(t) or CP_RE.search(t):
        return "ok"
    return "inconnu"


LIEU_LABEL = {"ok": "Paris / 92", "idf": "Île-de-France", "inconnu": "Lieu non précisé", "hors": "Hors zone"}


# ---------------------------------------------------------------- dates / durée

MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre",
        "novembre", "decembre"]
MOIS_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]
NOMBRES = {"un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
           "dix": 10, "douze": 12, "two": 2, "three": 3, "four": 4, "five": 5}
N = r"(\d{1,2}|un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|douze|two|three|four|five)"


def _n(x):
    return int(x) if x.isdigit() else NOMBRES[x]


def durees(t):
    res = []
    for m in re.finditer(N + r"\s*(?:a|-|–|ou|/|to)\s*" + N + r"\s*(?:mois|months?)\b", t):
        lo, hi = _n(m.group(1)), _n(m.group(2))
        if 1 <= lo <= hi <= 12:
            res.append((lo, hi))
    t = re.sub(N + r"\s*(?:a|-|–|ou|/|to)\s*" + N + r"\s*(?:mois|months?)\b", " ", t)
    for m in re.finditer(r"\b" + N + r"\s*(?:mois|months?)\b(?! d.?experience)", t):
        n = _n(m.group(1))
        if 1 <= n <= 12:
            res.append((n, n))
    return res


def debut(t):
    """Mois de début mentionné (1-12) et année éventuelle."""
    noms = "|".join(MOIS + MOIS_EN)
    m = re.search(r"(?:debut|demarrage|a partir d[eu]|des|start(?:ing)?(?: date)?|disponible)\s*:?\s*(?:le |en |in |of )?"
                  r"(?:\d{1,2}(?:er)? )?(" + noms + r")\s*(20\d\d)?", t)
    if not m:
        m = re.search(r"\b(" + noms + r")\s+(2027)\b", t)
    if not m:
        return None, None
    nom = m.group(1)
    mois = (MOIS.index(nom) if nom in MOIS else MOIS_EN.index(nom)) + 1
    return mois, (int(m.group(2)) if m.group(2) else None)


def compatibilite(titre, texte):
    """Compatibilité avec un stage de 3 mois mai–juillet 2027.
    statut : 'ok' | 'proche' | 'inconnu' | 'ko'."""
    t = norm(titre + "\n" + texte)
    ds = durees(t)
    notes = []
    if any(lo <= 3 <= hi for lo, hi in ds):
        statut = "ok"
    elif any(lo <= 4 and hi >= 2 for lo, hi in ds):
        statut = "proche"
    elif ds:
        statut = "ko"
    elif re.search(r"cesure|gap year|fin d.?etudes|\bpfe\b|\btfe\b|end of studies|final year", t):
        statut = "ko"
        notes.append("Stage de fin d'études / césure (souvent 6 mois)")
    elif re.search(r"2e annee|2eme annee|deuxieme annee|assistant ingenieur|stage d.?application|stage d.?ete|"
                   r"summer intern|stage court", t):
        statut = "ok"
        notes.append("Stage court / 2e année")
    else:
        statut = "inconnu"
    if ds:
        lo, hi = min(d[0] for d in ds), max(d[1] for d in ds)
        notes.insert(0, f"Durée : {lo} mois" if lo == hi else f"Durée : {lo} à {hi} mois")

    mois, annee = debut(t)
    if mois:
        nom = MOIS[mois - 1].replace("fevrier", "février").replace("aout", "août").replace("decembre", "décembre")
        notes.append(f"Début : {nom}{' ' + str(annee) if annee else ''}")
        if not (4 <= mois <= 6) and statut == "ok":
            statut = "proche"
        if annee and annee < 2027 and statut in ("ok", "proche", "inconnu"):
            statut = "ko"
    return {"statut": statut, "detail": " · ".join(notes)}


COMPAT_LABEL = {"ok": "Compatible mai–juil.", "proche": "À vérifier (durée/date proche)",
                "inconnu": "Durée non précisée", "ko": "Incompatible (6 mois / dates)"}


# ---------------------------------------------------------------- domaines et thèmes

# Thèmes communs à l'analyse de l'offre et à l'adaptation du CV.
THEMES = {
    "energie": ("Énergie & transition", r"energ\w*|renouvelable\w*|solaire|photovolta\w*|eolien\w*|hydrogen\w*|hydrogene|"
                r"nucleaire|nuclear|reseaux? electrique\w*|electricite|electricity|power plant\w*|decarbon\w*|bas.carbone|"
                r"carbone|carbon|climat\w*|climate|batterie\w*|stockage d.energie|smart grid\w*|utilities|"
                r"efficacite energetique|transition energetique|gaz|biomasse|geothermi\w*|mobilite electrique"),
    "conseil": ("Conseil", r"conseil|consulting|consultant\w*|cabinet|strategi\w*|strategy|transformation|"
                r"benchmark\w*|recommandation\w*|etude\w* de marche|due diligence|business case|missions? clients?"),
    "industrie": ("Industrie & production", r"industri\w*|production|usine|manufactur\w*|assemblage|atelier|lean|"
                  r"amelioration continue|performance industrielle|ingenieur methodes|procedes? industriels?|"
                  r"automobile|maintenance|aeronauti\w*|ferroviaire"),
    "mecanique": ("Mécanique & conception", r"mecani\w*|mechanical|conception|design engineer|cao|cad|catia|"
                  r"solidworks|dimensionnement|structure\w*|materiaux|thermique|thermal|fluide\w*|elements finis|"
                  r"calcul\w*"),
    "qualite": ("Qualité", r"qualite|quality|non.conformit\w*|controle qualite|normes?|iso ?9001"),
    "logistique": ("Logistique & supply chain", r"logisti\w*|supply chain|stocks?|approvisionnement\w*|flux|achats|"
                   r"procurement"),
    "simulation": ("Simulation & modélisation", r"simulation\w*|modelisation\w*|modeling|modelling|numerique\w*|"
                   r"matlab|python|optimisation|optimization|calcul\w*"),
    "mesure": ("Mesures & essais", r"mesures?|essais?|instrumentation|tests?|experimentation\w*|campagne\w*"),
    "data": ("Analyse de données", r"donnees|data|analyse\w*|excel|tableau\w* de bord|dashboard\w*|reporting|power ?bi|"
             r"kpi\w*|indicateur\w*|statisti\w*"),
    "acoustique": ("Acoustique & vibrations", r"acousti\w*|vibration\w*|bruit"),
    "batiment": ("Bâtiment & infrastructures", r"batiment\w*|building\w*|construction|genie civil|infrastructure\w*|"
                 r"ouvrage\w*|btp|urbain\w*|ville\w*|immobilier"),
    "projet": ("Gestion de projet", r"gestion de projet|project management|pilotage|planning|coordination|coordonner|"
               r"pmo|suivi de projet|organisation|organiser"),
    "negociation": ("Négociation & relation fournisseurs", r"negociation\w*|negocier|contrats?|fournisseur\w*|"
                    r"commercial\w*"),
    "budget": ("Gestion budgétaire", r"budget\w*|financ\w*|couts?|chiffrage\w*|rentabilite"),
    "equipe": ("Travail en équipe", r"equipe\w*|team\w*|collaborat\w*|transverse\w*"),
    "terrain": ("Expérience terrain", r"terrain|chantier\w*|sur site|on site|field"),
    "communication": ("Communication", r"communication|presentation\w*|redaction|rediger|powerpoint|synthese"),
}
THEMES_RE = {k: re.compile(r"\b(" + v[1] + r")\b") for k, v in THEMES.items()}

# Les trois familles de stages visées (filtre de pertinence).
DOMAINES = {"energie": ["energie"], "conseil": ["conseil"],
            "industrie": ["industrie", "mecanique", "qualite", "logistique"]}
DOMAINE_LABEL = {"energie": "Énergie", "conseil": "Conseil", "industrie": "Industrie / méca"}

HORS_SUJET_TITRE_RE = re.compile(
    r"\b(rh|ressources humaines|human resources|marketing|juriste|juridique|legal|comptab\w*|paie|payroll|"
    r"talent acquisition|recrut\w*|recruitment|graphiste|community manager|social media|assistant\w* de direction|"
    r"office manager|evenementiel|communication|e-commerce|graphi\w*|learning|relations? ecoles?|sales|"
    r"designer|ux|ui)\b")


def themes_offre(titre, texte):
    """Nombre d'occurrences de chaque thème (le titre compte triple)."""
    nt, nx = norm(titre), norm(texte)
    res = {}
    for k, rx in THEMES_RE.items():
        n = 3 * len(rx.findall(nt)) + len(rx.findall(nx))
        if n:
            res[k] = n
    return res


def domaines(themes, seuil=3):
    """Domaines nettement présents (une mention dans le titre suffit, elle compte triple)."""
    scores = {d: sum(themes.get(t, 0) for t in ts) for d, ts in DOMAINES.items()}
    return {d: s for d, s in scores.items() if s >= seuil}


def pertinente(titre, doms):
    return bool(doms) and not HORS_SUJET_TITRE_RE.search(norm(titre))


# ---------------------------------------------------------------- missions / but

MISSION_RE = re.compile(r"mission|taches|responsabilit|vos activites|ce que (vous ferez|tu feras)|votre role|ton role|"
                        r"your role|what you.ll do|responsibilities|descriptif du poste|description du poste|"
                        r"au sein de|le poste|the role|job description|vous serez amene|tu seras amene")
FIN_MISSION_RE = re.compile(r"profil|competences|qualifications|vous etes|tu es|requirements|who you are|"
                            r"pourquoi nous rejoindre|avantages|benefits|deroulement|processus|about us|qui sommes|"
                            r"votre formation|ce que nous|what we offer|informations compl|savoir.etre")


def _est_titre(el):
    txt = el.get_text(" ", strip=True)
    if not txt or len(txt) > 90:
        return False
    if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return True
    if el.name in ("p", "div", "span") and el.find(["strong", "b"]) and len(el.find(["strong", "b"]).get_text(strip=True)) >= len(txt) - 3:
        return True
    return txt.endswith(":") and len(txt) < 70


def missions_et_but(description_html, max_puces=7):
    """Retourne (but, [missions]) extraits de la description."""
    soup = BeautifulSoup(description_html or "", "html.parser")
    for x in soup(["script", "style"]):
        x.decompose()
    blocs = [el for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "div"])
             if el.name != "div" or not el.find(["p", "li", "div", "h2", "h3", "h4"])]
    missions, but, dedans = [], "", False
    for el in blocs:
        txt = el.get_text(" ", strip=True)
        if not txt or (el.name != "li" and el.find_parent("li")) or txt.lstrip("-•–· ").strip() in missions:
            continue
        if _est_titre(el) and el.name != "li":
            n = norm(txt)
            if dedans and (FIN_MISSION_RE.search(n) or missions):
                if FIN_MISSION_RE.search(n):
                    break
            if MISSION_RE.search(n) and not FIN_MISSION_RE.search(n):
                dedans = True
                continue
        if dedans:
            if el.name == "li" or txt.startswith(("-", "•", "–", "·")):
                missions.append(txt.lstrip("-•–· ").strip())
            elif not but and 40 <= len(txt) <= 450:
                but = txt
            elif 30 <= len(txt) <= 300 and len(missions) < max_puces and but:
                missions.append(txt)
            if len(missions) >= max_puces:
                break
    if not missions:
        missions = [li.get_text(" ", strip=True) for li in soup.find_all("li")
                    if 25 <= len(li.get_text(" ", strip=True)) <= 300][:max_puces]
    if not but:
        for p in soup.find_all(["p", "div"]):
            txt = p.get_text(" ", strip=True)
            if 60 <= len(txt) <= 450 and not p.find(["p", "div", "li"]) and MISSION_RE.search(norm(txt)):
                but = txt
                break
    if not but and missions:
        but = missions[0]
    if not missions and not but:
        texte = soup.get_text(" ", strip=True)
        but = (texte[:400] + "…") if len(texte) > 400 else texte
    return but, missions[:max_puces]


def analyser(titre, lieu, description_html, contrat=""):
    texte = html_vers_texte(description_html)
    th = themes_offre(titre, texte)
    doms = domaines(th)
    but, missions = missions_et_but(description_html)
    return {
        "stage": est_stage(titre, contrat, texte),
        "lieu_statut": lieu_statut(lieu, texte),
        "compat": compatibilite(titre, texte),
        "themes": th,
        "domaines": doms,
        "pertinente": pertinente(titre, doms),
        "but": but,
        "missions": missions,
    }
