#!/usr/bin/env python3
"""Récupère les séances de tes cinémas sur Allociné et écrit site/data.js (et data.json).

Usage : python scrape.py [nombre_de_jours]   (7 jours par défaut)
Aucune dépendance : bibliothèque standard uniquement.
"""
import json, sys, time, datetime as dt
import urllib.request, urllib.error
from pathlib import Path

BASE = "https://www.allocine.fr"
# identifiant Allociné : (nom affiché, ville)
CINEMAS = {
    "P6909": ("Pathé Vaise", "Lyon 9e"),
    "P0012": ("Pathé Bellecour", "Lyon 2e"),
    "W6902": ("UGC Confluence", "Lyon 2e"),
    "P3757": ("Comoedia", "Lyon 7e"),
    "P0015": ("Lumière Bellecour", "Lyon 2e"),
    "P0017": ("Lumière Terreaux", "Lyon 1er"),
    "W6903": ("Lumière La Fourmi", "Lyon 3e"),
    "P0039": ("Le Lem", "Tassin"),
    "P0725": ("Alpha", "Charbonnières"),
    "P9596": ("Le Strapontin", "Sain-Bel"),
    "P0618": ("CinéDuchère", "Lyon 9e"),
}
VERSIONS = {
    "multiple": "VF", "multiple_st": "VF ST", "multiple_sme": "VF SME",
    "original": "VO", "original_st": "VOST", "original_sme": "VO SME",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": BASE + "/seance/",
}


def get_json(path, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(BASE + path, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                time.sleep(2)
                continue
            raise


def film_summary(m):
    theater = [x for x in (m.get("releases") or [])
               if "THEATER" in ((x.get("releaseTags") or {}).get("tagTypes") or [])]
    date_of = lambda x: ((x or {}).get("releaseDate") or {}).get("date")
    rerelease = next((x for x in theater if x.get("name") == "ReRelease"), None)
    original = next((x for x in theater if x.get("name") == "Released"), None)
    director = next((c for c in (m.get("credits") or [])
                     if (c.get("position") or {}).get("name") == "DIRECTOR"), None)
    person = (director or {}).get("person") or {}
    title = m.get("title")
    return {
        "t": title,
        "ot": m.get("originalTitle") if m.get("originalTitle") != title else None,
        "y": (m.get("data") or {}).get("productionYear"),
        "rt": m.get("runtime"),
        "g": [g.get("translate") for g in (m.get("genres") or [])],
        "d": (f"{person.get('firstName') or ''} {person.get('lastName') or ''}".strip() or None),
        "p": (m.get("poster") or {}).get("url"),
        "sc": ((m.get("stats") or {}).get("userRating") or {}).get("score"),
        "rr": date_of(rerelease),
        "rel": date_of(original),
    }


def main():
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    today = dt.date.today()
    days = [(today + dt.timedelta(days=i)).isoformat() for i in range(n_days)]
    films, sessions, errors = {}, [], []

    for cid in CINEMAS:
        for day in days:
            page, total = 1, 1
            while page <= total:
                try:
                    j = get_json(f"/_/showtimes/theater-{cid}/d-{day}/p-{page}/")
                except Exception as e:  # noqa: BLE001
                    errors.append((cid, day, page, str(e)))
                    break
                total = (j.get("pagination") or {}).get("totalPages") or 1
                for res in j.get("results") or []:
                    m = res["movie"]
                    fid = m["internalId"]
                    if fid not in films:
                        films[fid] = {k: v for k, v in film_summary(m).items() if v is not None}
                    for key, label in VERSIONS.items():
                        for s in (res.get("showtimes") or {}).get(key) or []:
                            ticketing = ((s.get("data") or {}).get("ticketing") or [])
                            default = next((t for t in ticketing if t.get("provider") == "default"), None)
                            url = ((default or {}).get("urls") or [None])[0]
                            sessions.append([cid, fid, s["startsAt"][:16], label, url])
                page += 1
                time.sleep(0.4)

    if not sessions:
        sys.exit("Aucune séance récupérée. Erreurs : " + repr(errors[:3]))

    out = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "cinemas": {cid: {"name": n, "town": t} for cid, (n, t) in CINEMAS.items()},
        "films": films,
        "sessions": sessions,
    }
    site = Path(__file__).resolve().parent.parent / "site"
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    (site / "data.json").write_text(payload, encoding="utf-8")
    # data.js permet d'ouvrir index.html directement (double clic), sans serveur
    target = site / "data.js"
    target.write_text("window.__DATA=" + payload + ";", encoding="utf-8")
    print(f"{len(films)} films, {len(sessions)} séances, {len(errors)} erreurs -> {target}")
    for e in errors[:5]:
        print("  erreur :", e)


if __name__ == "__main__":
    main()
