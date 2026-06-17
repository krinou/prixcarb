
# -*- coding: utf-8 -*-

import json
import math
import os
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import requests

from cache_utils import load_cache, save_cache, update_cache_parallel

XML_FILE = os.environ.get("XML_FILE", "PrixCarburants_instantane.xml")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "stations.json")
FUEL_TAG = os.environ.get("INPUT_CARBURANT", "E10")
ADRESSE_REF = os.environ.get("INPUT_ADRESSE", "")
DEPS = {
    dep.strip()
    for dep in os.environ.get("INPUT_DEPARTEMENTS", "").split(",")
    if dep.strip()
}
MAX_WORKERS = int(os.environ.get("SCRAPE_WORKERS", "8"))
TIMEOUT = int(os.environ.get("SCRAPE_TIMEOUT", "10"))

HEADERS = {
    "User-Agent": os.environ.get(
        "PRIXCARB_USER_AGENT",
        "prixcarb/1.0 (contact: krinou@gmail.com)",
    )
}

# -------------------------------
# Géocodage / distance
# -------------------------------

def geocode_address(address):
    if not address:
        raise ValueError("Adresse vide")

    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "fr",
    }
    url = "https://nominatim.openstreetmap.org/search?" + urlencode(params)
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    items = response.json()
    if not items:
        raise ValueError(f"Adresse introuvable : {address}")

    item = items[0]
    return float(item["lat"]), float(item["lon"])


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

# -------------------------------
# Outils XML / métier
# -------------------------------

def xml_coord_to_float(value, coord_type=None):
    if value is None:
        return None
    value = str(value).strip().replace(",", ".")
    if not value:
        return None
    try:
        num = float(value)
    except Exception:
        return None

    if coord_type == "lat":
        if -90 <= num <= 90:
            return num
        scaled = num / 100000.0
        if -90 <= scaled <= 90:
            return scaled
        return None

    if coord_type == "lon":
        if -180 <= num <= 180:
            return num
        scaled = num / 100000.0
        if -180 <= scaled <= 180:
            return scaled
        return None

    if -180 <= num <= 180:
        return num
    scaled = num / 100000.0
    if -180 <= scaled <= 180:
        return scaled
    return None


def dep_from_cp(cp):
    cp = (cp or "").strip()
    if len(cp) >= 3 and cp[:3] in {"971", "972", "973", "974", "975", "976", "977", "978"}:
        return cp[:3]
    if len(cp) >= 2:
        # Corse gérée via 20 si CP ex 20000 / 20167 etc.
        return cp[:2]
    return ""


def extract_prices(pdv):
    prices = {}
    for prix in pdv.findall("prix"):
        nom = prix.get("nom", "").strip()
        valeur = prix.get("valeur", "").strip()
        maj = prix.get("maj", "").strip()
        if nom:
            prices[nom] = {
                "valeur": valeur,
                "maj": maj,
            }
    return prices


def build_station_record(pdv, cache, fuel_tag, ref_lat=None, ref_lon=None):
    sid = str(pdv.get("id", "")).strip()
    cp = (pdv.get("cp") or "").strip()
    dep = dep_from_cp(cp)
    adresse = child_text(pdv, "adresse")
    ville = child_text(pdv, "ville")
    lat = xml_coord_to_float(pdv.get("latitude"), "lat")
    lon = xml_coord_to_float(pdv.get("longitude"), "lon")
    prices = extract_prices(pdv)
    selected_price = prices.get(fuel_tag, {}).get("valeur", "")
    enseigne = cache.get(sid, {}).get("enseigne", "")

    distance_km = None
    if (
        ref_lat is not None and ref_lon is not None
        and lat is not None and lon is not None
    ):
        distance_km = round(haversine(ref_lat, ref_lon, lat, lon), 2)

    return {
        "id": sid,
        "dep": dep,
        "station": enseigne,
        "adresse": adresse,
        "cp": cp,
        "ville": ville,
        "latitude": lat,
        "longitude": lon,
        "distance_km": distance_km,
        "carburant_choisi": fuel_tag,
        "prix": selected_price,
        "prixs": prices,
    }

def child_text(node, tag):
    child = node.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""

# -------------------------------
# Programme principal
# -------------------------------

def main():
    if not os.path.exists(XML_FILE):
        raise FileNotFoundError(f"Fichier XML introuvable: {XML_FILE}")

    ref_lat = None
    ref_lon = None
    if ADRESSE_REF.strip():
        ref_lat, ref_lon = geocode_address(ADRESSE_REF.strip())

    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    pdvs = root.findall("pdv")

    if DEPS:
        pdvs = [pdv for pdv in pdvs if dep_from_cp((pdv.get("cp") or "").strip()) in DEPS]

    cache = load_cache()
    sids = [str(pdv.get("id", "")).strip() for pdv in pdvs]
    cache = update_cache_parallel(sids, cache, max_workers=MAX_WORKERS, timeout=TIMEOUT)
    save_cache(cache)

    stations = [
        build_station_record(pdv, cache, FUEL_TAG, ref_lat=ref_lat, ref_lon=ref_lon)
        for pdv in pdvs
    ]

    if ref_lat is not None and ref_lon is not None:
        stations.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"], x["prix"] or "999"))
    else:
        stations.sort(key=lambda x: (x["prix"] or "999", x["cp"], x["id"]))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
