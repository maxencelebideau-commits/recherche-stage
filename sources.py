"""Connecteurs vers les sites carrières des entreprises.

Chaque connecteur renvoie une liste d'offres « légères » :
    {"uid", "titre", "url", "lieu", "contrat", "publie_le", "description_html" ou "detail": callable}
"detail" n'est appelé que pour les offres nouvelles (évite de recharger chaque page)."""
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from analyse import STAGE_RE, norm

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36",
      "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}
TIMEOUT = 25
MOTS_STAGE = ["stage", "stagiaire", "intern"]


def _get(url, **kw):
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- SmartRecruiters (API publique)

def smartrecruiters(p):
    societe = p["societe"]
    base = f"https://api.smartrecruiters.com/v1/companies/{societe}/postings"
    vus = {}
    for q in MOTS_STAGE + ["internship"]:
        offset = 0
        while offset < 500:
            data = _get(base, params={"q": q, "limit": 100, "offset": offset, "country": "fr"}).json()
            for o in data.get("content", []):
                vus[o["id"]] = o
            offset += 100
            if offset >= data.get("totalFound", 0):
                break
    res = []
    for o in vus.values():
        loc = o.get("location") or {}
        lieu = loc.get("fullLocation") or ", ".join(x for x in [loc.get("city"), loc.get("region")] if x)
        ref = o.get("ref") or f"{base}/{o['id']}"

        def detail(ref=ref):
            d = _get(ref).json()
            secs = (d.get("jobAd") or {}).get("sections") or {}
            html = "".join(f"<h3>{s.get('title', '')}</h3>{s.get('text', '')}"
                           for k in ("jobDescription", "qualifications", "additionalInformation", "companyDescription")
                           if (s := secs.get(k)) and s.get("text"))
            return {"description_html": html, "url": d.get("postingUrl") or d.get("applyUrl")}

        res.append({"uid": o["id"], "titre": o.get("name", ""), "lieu": lieu,
                    "url": f"https://jobs.smartrecruiters.com/{societe}/{o['id']}",
                    "contrat": " ".join(filter(None, [(o.get("typeOfEmployment") or {}).get("label"),
                                                      (o.get("experienceLevel") or {}).get("label")])),
                    "publie_le": (o.get("releasedDate") or "")[:10], "detail": detail})
    return res


# ---------------------------------------------------------------- Workday

def _facettes_france(facets):
    """Cherche dans les facettes Workday la valeur « France » (pays / lieu)."""
    for f in facets or []:
        param = f.get("facetParameter", "")
        for v in f.get("values", []):
            if "values" in v:  # groupe imbriqué
                trouve = _facettes_france([{"facetParameter": v.get("facetParameter", param), "values": v["values"]}])
                if trouve:
                    return trouve
            elif norm(v.get("descriptor", "")) == "france" and "ountry" in param:
                return {param: [v["id"]]}
    return {}


def workday(p):
    host, tenant, site = p["host"], p["tenant"], p["site"]
    api = f"https://{host}/wday/cxs/{tenant}/{site}"
    hdr = {"Content-Type": "application/json", "Accept": "application/json"}
    vus = {}
    for q in ["stage", "stagiaire", "intern"]:
        corps = {"limit": 20, "offset": 0, "searchText": q, "appliedFacets": {}}
        premiere = requests.post(f"{api}/jobs", json=corps, headers={**UA, **hdr}, timeout=TIMEOUT)
        premiere.raise_for_status()
        data = premiere.json()
        fr = _facettes_france(data.get("facets"))
        if fr:
            corps["appliedFacets"] = fr
            data = requests.post(f"{api}/jobs", json=corps, headers={**UA, **hdr}, timeout=TIMEOUT).json()
        while True:
            for o in data.get("jobPostings", []):
                vus[o["externalPath"]] = o
            corps["offset"] += 20
            if corps["offset"] >= min(data.get("total", 0) or 0, 300) or not data.get("jobPostings"):
                break
            data = requests.post(f"{api}/jobs", json=corps, headers={**UA, **hdr}, timeout=TIMEOUT).json()
    res = []
    for path, o in vus.items():
        def detail(path=path):
            d = _get(f"{api}{path}", headers={"Accept": "application/json"}).json().get("jobPostingInfo", {})
            lieux = [d.get("location", "")] + (d.get("additionalLocations") or [])
            return {"description_html": d.get("jobDescription", ""), "lieu": ", ".join(x for x in lieux if x),
                    "url": d.get("externalUrl") or f"https://{host}/{site}{path}",
                    "contrat": d.get("timeType", "")}
        res.append({"uid": path, "titre": o.get("title", ""), "lieu": o.get("locationsText", ""),
                    "url": f"https://{host}/{site}{path}", "publie_le": o.get("postedOn", ""), "detail": detail})
    return res


# ---------------------------------------------------------------- Teamtailor (flux RSS)

def teamtailor(p):
    xml = _get(p["rss"]).content
    root = ET.fromstring(xml)
    ns = {"tt": "https://teamtailor.com/locations"}
    res = []
    for it in root.iter("item"):
        lieux = [", ".join(filter(None, [(l.findtext("tt:city", "", ns) or "").strip(),
                                         (l.findtext("tt:name", "", ns) or "").strip()]))
                 for l in it.findall(".//tt:location", ns)]
        res.append({"uid": it.findtext("guid") or it.findtext("link"), "titre": it.findtext("title", ""),
                    "url": it.findtext("link", ""), "lieu": " / ".join(x for x in lieux if x),
                    "publie_le": it.findtext("pubDate", ""), "description_html": it.findtext("description", "")})
    return res


# ---------------------------------------------------------------- Greenhouse / Lever

def greenhouse(p):
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{p['board']}/jobs", params={"content": "true"}).json()
    return [{"uid": str(o["id"]), "titre": o.get("title", ""), "url": o.get("absolute_url", ""),
             "lieu": (o.get("location") or {}).get("name", ""), "publie_le": (o.get("updated_at") or "")[:10],
             "description_html": BeautifulSoup(o.get("content", ""), "html.parser").get_text()}
            for o in data.get("jobs", [])]


def lever(p):
    data = _get(f"https://api.lever.co/v0/postings/{p['societe']}", params={"mode": "json"}).json()
    return [{"uid": o["id"], "titre": o.get("text", ""), "url": o.get("hostedUrl", ""),
             "lieu": (o.get("categories") or {}).get("location", ""),
             "contrat": (o.get("categories") or {}).get("commitment", ""),
             "description_html": o.get("description", "") + "".join(
                 f"<h3>{l.get('text', '')}</h3><ul>{l.get('content', '')}</ul>" for l in o.get("lists", []))}
            for o in data]


# ---------------------------------------------------------------- Page HTML générique

def _detail_html(url):
    soup = BeautifulSoup(_get(url).text, "html.parser")
    for x in soup(["script", "style", "nav", "header", "footer", "form", "noscript"]):
        x.decompose()
    titre = soup.find("h1")
    zone = soup.find("main") or soup.find("article") or soup.body or soup
    return {"titre_page": titre.get_text(" ", strip=True) if titre else "", "description_html": str(zone)}


LIEN_GENERIQUE_RE = re.compile(r"^(postuler|voir|en savoir plus|lire la suite|details?|apply|more|decouvrir)\b")


def html(p):
    """Lit une page listant les offres et garde les liens qui ressemblent à des stages.
    p = {"url": page des offres, "motif": regex optionnelle sur l'URL des fiches d'offre,
         "pages": nombre de pages à parcourir via ?page=N (0 = première)}"""
    motif = re.compile(p["motif"]) if p.get("motif") else None
    res, vus, liens_vus = [], set(), set()
    for n in range(p.get("pages", 1)):
        url_page = p["url"] if n == 0 else p["url"] + ("&" if "?" in p["url"] else "?") + f"page={n}"
        page = _get(url_page)
        soup = BeautifulSoup(page.text, "html.parser")
        hote = urlparse(page.url).netloc
        nouveaux_liens = 0
        for a in soup.find_all("a", href=True):
            url = urljoin(page.url, a["href"]).split("#")[0]
            txt = a.get_text(" ", strip=True)
            if url in vus or url.rstrip("/") == page.url.rstrip("/"):
                continue
            lien_offre = bool(motif.search(url)) if motif else (
                urlparse(url).netloc == hote and len(urlparse(url).path) > 8)
            if not lien_offre:
                continue
            if url not in liens_vus:
                liens_vus.add(url)
                nouveaux_liens += 1
            # Lien « Postuler » ou vide : le titre est dans le bloc parent.
            parent = a.find_parent(["li", "article", "tr"]) or a.find_parent("div")
            entete = parent.find(["h2", "h3", "h4", "h5", "strong"]) if parent else None
            if (not txt or LIEN_GENERIQUE_RE.match(norm(txt))) and entete:
                txt = entete.get_text(" ", strip=True)
            contexte = parent.get_text(" ", strip=True) if parent else ""
            if not txt or not STAGE_RE.search(norm(txt + " " + url.replace("-", " ") + " " + contexte[:300])):
                continue
            vus.add(url)
            titre = txt if len(txt) < 160 else txt[:157] + "…"

            def detail(url=url):
                d = _detail_html(url)
                return {"description_html": d["description_html"],
                        **({"titre": d["titre_page"]} if d["titre_page"] else {})}

            # Pas de lieu fiable dans une page générique : il sera déduit du texte de la fiche.
            res.append({"uid": url, "titre": titre, "url": url, "lieu": "", "detail": detail})
        if n and not nouveaux_liens:  # plus aucune nouvelle offre : fin de la pagination
            break
    return res


# ---------------------------------------------------------------- Flux schema.org JobPosting (jobs.feed.json)

def flux_json(p):
    data = _get(p["url"]).json()
    res = []
    for el in data.get("dataFeedElement", []):
        o = el.get("item", el)
        locs = o.get("jobLocation") or []
        locs = locs if isinstance(locs, list) else [locs]
        lieu = ", ".join(filter(None, [((l.get("address") or {}).get("addressLocality") or "") for l in locs]))
        contrat = o.get("employmentType") or ""
        res.append({"uid": str((o.get("identifier") or {}).get("value") or o.get("url")), "titre": o.get("title", "").strip(),
                    "url": o.get("url", ""), "lieu": lieu,
                    "contrat": " ".join(contrat) if isinstance(contrat, list) else contrat,
                    "publie_le": (o.get("datePosted") or "")[:10], "description_html": o.get("description", "")})
    return res


CONNECTEURS = {"smartrecruiters": smartrecruiters, "workday": workday, "teamtailor": teamtailor,
               "greenhouse": greenhouse, "lever": lever, "html": html, "flux_json": flux_json}


def recuperer(source):
    return CONNECTEURS[source["type"]](source)


# ---------------------------------------------------------------- détection automatique

def detecter(url):
    """Déduit le type de source à partir de l'URL de la page carrières donnée par l'utilisateur."""
    u = urlparse(url if "://" in url else "https://" + url)
    host, chemin = u.netloc.lower(), [x for x in u.path.split("/") if x]
    if "smartrecruiters.com" in host and chemin:
        return {"type": "smartrecruiters", "societe": chemin[0]}
    if "myworkdayjobs.com" in host and chemin:
        site = [c for c in chemin if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", c)][0]
        return {"type": "workday", "host": host, "tenant": host.split(".")[0], "site": site}
    if "greenhouse.io" in host and chemin:
        return {"type": "greenhouse", "board": chemin[0]}
    if "lever.co" in host and chemin:
        return {"type": "lever", "societe": chemin[0]}
    url = u.geturl()
    try:
        page = _get(url)
        if "/jobs.feed.json" in page.text:
            racine = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"
            return {"type": "flux_json", "url": racine + "/jobs.feed.json"}
        if "teamtailor" in page.text:
            racine = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"
            return {"type": "teamtailor", "rss": racine + "/jobs.rss"}
        m = re.search(r"https?://(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)", page.text)
        if m:
            return {"type": "smartrecruiters", "societe": m.group(1)}
        m = re.search(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)", page.text)
        if m:
            return {"type": "workday", "host": f"{m.group(1)}.{m.group(2)}.myworkdayjobs.com",
                    "tenant": m.group(1), "site": m.group(3)}
    except requests.RequestException:
        pass
    return {"type": "html", "url": url}
