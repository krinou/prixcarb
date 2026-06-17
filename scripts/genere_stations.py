## -*- coding: utf-8 -*-

import json
import math
import os
import xml.etree.ElementTree as ET

from cache_utils import load_cache

XML_FILE = os.environ.get("XML_FILE", "PrixCarburants_instantane.xml")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "stations.json")
FUEL_TAG = os.environ.get("INPUT_CARBURANT", "E10")


def xml_coord_to_float(value, coord_type=None):
    if value is None:
        return None

    s = str(value).strip().replace(",", ".")
    if not s:
        return None

    try:
        num = float(s)
    except:
        return None

    if coord_type == "lat":
        if -90 <= num <= 90:
            return num
        return num / 100000

    if coord_type == "lon":
        if -180 <= num <= 180:
            return num
        return num / 100000

    return None


def haversine(lat1, lon1, lat2, lon2):
    r = 6371
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


def extract_prices(pdv):
    prices = {}

    for prix in pdv.findall("prix"):
        nom = prix.get("nom", "").strip()
        valeur = prix.get("valeur", "").strip()
        maj = prix.get("maj", "").strip()

        if nom:
            prices[nom] = {
                "valeur": valeur,
                "maj": maj
            }

    return prices


def build_station_record(pdv, cache, fuel_tag):
    sid = str(pdv.get("id", "")).strip()

    lat = xml_coord_to_float(pdv.get("latitude"), "lat")
    lon = xml_coord_to_float(pdv.get("longitude"), "lon")

    prices = extract_prices(pdv)
    selected_price = prices.get(fuel_tag, {}).get("valeur", "")

    return {
        "id": sid,
        "enseigne": cache.get(sid, {}).get("enseigne", ""),
        "adresse": (pdv.get("adresse") or "").strip(),
        "cp": (pdv.get("cp") or "").strip(),
        "ville": (pdv.get("ville") or "").strip(),
        "latitude": lat,
        "longitude": lon,
        "carburant_choisi": fuel_tag,
        "prix": selected_price,
        "prixs": prices
    }


def main():
    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    cache = load_cache()

    data = []

    for pdv in root.findall("pdv"):
        data.append(build_station_record(pdv, cache, FUEL_TAG))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
