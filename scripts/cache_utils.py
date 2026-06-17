
# -*- coding: utf-8 -*-

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

ENSEIGNE_CACHE_FILE = os.environ.get("ENSEIGNE_CACHE_FILE", "enseigne_cache.json")
HEADERS = {
    "User-Agent": os.environ.get(
        "PRIXCARB_USER_AGENT",
        "prixcarb/1.0 (contact: krinou@gmail.com)",
    )
}


def normalize_cache(cache):
    """
    Normalise les anciens formats du cache.
    - "12345": "Total" -> {"12345": {"enseigne": "Total"}}
    - valeurs non dict -> transformées en dict minimal
    """
    if not isinstance(cache, dict):
        return {}

    normalized = {}
    for sid, value in cache.items():
        sid = str(sid)
        if isinstance(value, dict):
            normalized[sid] = {
                "enseigne": (value.get("enseigne") or "").strip()
            }
        else:
            normalized[sid] = {
                "enseigne": (str(value).strip() if value is not None else "")
            }
    return normalized


def load_cache(cache_file=ENSEIGNE_CACHE_FILE):
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            print(f"Erreur lecture cache : {e}")
            cache = {}
    else:
        cache = {}

    return normalize_cache(cache)


def save_cache(cache, cache_file=ENSEIGNE_CACHE_FILE):
    cache = normalize_cache(cache)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur écriture cache : {e}")


def extract_enseigne_from_soup(soup):
    """
    Extraction simple et robuste de l'enseigne.
    Ajuste ici si la structure HTML du site change.
    """
    # Cas observé dans ton code initial
    block = soup.find("div", class_="fr-pb-3v")
    if block:
        parts = list(block.stripped_strings)
        if parts and parts[0].lower().startswith("marque"):
            parts = parts[1:]
        if parts:
            return parts[0].strip()

    text = " ".join(soup.stripped_strings)
    for marker in ["Marque", "Enseigne"]:
        idx = text.lower().find(marker.lower())
        if idx != -1:
            tail = text[idx + len(marker):].strip(" :.-
	")
            if tail:
                return tail.split()[0].strip()

    return ""


def fetch_station_html(sid, session=None, timeout=10):
    url = f"https://www.prix-carburants.gouv.fr/station/{sid}"
    getter = session.get if session is not None else requests.get
    response = getter(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_enseigne_for_sid(sid, session=None, timeout=10):
    sid = str(sid)
    try:
        html = fetch_station_html(sid, session=session, timeout=timeout)
        soup = BeautifulSoup(html, "html.parser")
        enseigne = extract_enseigne_from_soup(soup)
        return sid, enseigne
    except Exception as e:
        print(f"Erreur récupération enseigne id {sid} : {e}")
        return sid, ""


def get_enseigne(sid, cache, force_refresh=False, session=None, timeout=10):
    sid = str(sid)
    cache = normalize_cache(cache)

    if not force_refresh and sid in cache and cache[sid].get("enseigne"):
        return cache[sid].get("enseigne", "")

    sid, enseigne = fetch_enseigne_for_sid(sid, session=session, timeout=timeout)
    cache[sid] = {"enseigne": enseigne}
    return enseigne


def update_cache_parallel(sids, cache, max_workers=8, force_refresh=False, timeout=10):
    """
    Met à jour le cache en parallèle uniquement pour les SID nécessaires.
    Une seule sauvegarde doit être faite ensuite via save_cache(cache).
    """
    cache = normalize_cache(cache)
    sids = [str(sid) for sid in sids if str(sid).strip()]

    to_fetch = []
    for sid in sids:
        if force_refresh or not cache.get(sid, {}).get("enseigne"):
            to_fetch.append(sid)

    if not to_fetch:
        return cache

    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_enseigne_for_sid, sid, session, timeout): sid
                for sid in to_fetch
            }
            for future in as_completed(futures):
                sid, enseigne = future.result()
                cache[sid] = {"enseigne": enseigne}

    return cache
