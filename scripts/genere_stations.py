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
    url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
    headers = {"User-Agent": "prixcarb/1.0 (contact: krinou@gmail.com)"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"Aucun géocodage trouvé pour: {address}")

    return float(data[0]["lat"]), float(data[0]["lon"])


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
def xml_coord_to_float(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        if "." in value:
            return float(value)
        # Format officiel prix-carburants : latitude/longitude souvent en entier * 100000
        return float(value) / 100000.0
    except Exception:
        return None


def dep_from_cp(cp):
    cp = (cp or "").strip()
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
    adresse = (pdv.get("adresse") or "").strip()
    ville = (pdv.get("ville") or "").strip()
    lat = xml_coord_to_float(pdv.get("latitude"))
    lon = xml_coord_to_float(pdv.get("longitude"))
    prices = extract_prices(pdv)
    selected_price = prices.get(fuel_tag, {}).get("valeur", "")
    enseigne = cache.get(sid, {}).get("enseigne", "")

    distance_km = None
    if ref_lat is not None and ref_lon is not None and lat is not None and lon is not None:
        distance_km = round(haversine(ref_lat, ref_lon, lat, lon), 2)

    return {
        "id": sid,
        "dep": dep,
        "enseigne": enseigne,
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


# -------------------------------
# Programme principal
# -------------------------------
def main():
    if not os.path.exists(XML_FILE):
        raise FileNotFoundError(f"Fichier XML introuvable: {XML_FILE}")

    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    cache = load_cache()

    pdvs = list(root.findall("pdv"))
    if DEPS:
        pdvs = [pdv for pdv in pdvs if dep_from_cp(pdv.get("cp", "")) in DEPS]

    sids = [str(pdv.get("id", "")).strip() for pdv in pdvs if pdv.get("id")]
    updated = update_cache_parallel(
        sids,
        cache,
        max_workers=MAX_WORKERS,
        timeout=TIMEOUT,
    )
    if updated:
        save_cache(cache)

    ref_lat = ref_lon = None
    if ADRESSE_REF:
        print(f"Géocodage : {ADRESSE_REF}")
        ref_lat, ref_lon = geocode_address(ADRESSE_REF)

    stations_out = [
        build_station_record(pdv, cache, FUEL_TAG, ref_lat=ref_lat, ref_lon=ref_lon)
        for pdv in pdvs
    ]

    # Tri : d'abord prix choisi dispo, puis distance si connue, puis enseigne
    def sort_key(item):
        prix_brut = item.get("prix")
        try:
            prix_num = float(str(prix_brut).replace(",", ".")) if prix_brut not in (None, "") else 999999
        except Exception:
            prix_num = 999999
        distance = item.get("distance_km")
        distance_num = distance if distance is not None else 999999
        enseigne = item.get("enseigne") or ""
        return (prix_num, distance_num, enseigne.lower())

    stations_out.sort(key=sort_key)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(stations_out, f, ensure_ascii=False, indent=2)

    print(f"{len(stations_out)} stations écrites dans {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
