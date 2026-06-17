
# -*- coding: utf-8 -*-

import datetime
import json
import os
import xml.etree.ElementTree as ET

from cache_utils import load_cache, save_cache, update_cache_parallel

XML_FILE = os.environ.get("XML_FILE", "PrixCarburants_instantane.xml")
BASE_DIR = os.environ.get("BASE_DIR", "data")
LATEST_DIR = os.path.join(BASE_DIR, "latest")
MAX_WORKERS = int(os.environ.get("SCRAPE_WORKERS", "8"))
TIMEOUT = int(os.environ.get("SCRAPE_TIMEOUT", "10"))
FORCE_REFRESH = os.environ.get("FORCE_REFRESH_ENSEIGNE", "false").lower() == "true"


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

    return None


def dep_from_cp(cp):
    cp = (cp or "").strip()
    if len(cp) >= 3 and cp[:3] in {"971", "972", "973", "974", "975", "976", "977", "978"}:
        return cp[:3]
    if len(cp) >= 2:
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


def build_station_record(pdv, cache):
    sid = str(pdv.get("id", "")).strip()
    cp = (pdv.get("cp") or "").strip()
    return {
        "id": sid,
        "dep": dep_from_cp(cp),
        "enseigne": cache.get(sid, {}).get("enseigne", ""),
        "adresse": (pdv.get("adresse") or "").strip(),
        "cp": cp,
        "ville": (pdv.get("ville") or "").strip(),
        "latitude": xml_coord_to_float(pdv.get("latitude"), "lat"),
        "longitude": xml_coord_to_float(pdv.get("longitude"), "lon"),
        "carburants": extract_prices(pdv),
    }


def main():
    today = datetime.date.today().isoformat()
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(LATEST_DIR, exist_ok=True)

    if not os.path.exists(XML_FILE):
        raise FileNotFoundError(f"Fichier XML introuvable: {XML_FILE}")

    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    pdvs = root.findall("pdv")

    cache = load_cache()
    sids = [str(pdv.get("id", "")).strip() for pdv in pdvs]
    cache = update_cache_parallel(
        sids,
        cache,
        max_workers=MAX_WORKERS,
        force_refresh=FORCE_REFRESH,
        timeout=TIMEOUT,
    )
    save_cache(cache)

    by_dep = {}
    for pdv in pdvs:
        record = build_station_record(pdv, cache)
        dep = record["dep"] or "inconnu"
        by_dep.setdefault(dep, []).append(record)

    dated_dir = os.path.join(BASE_DIR, today)
    os.makedirs(dated_dir, exist_ok=True)

    for dep, items in by_dep.items():
        latest_path = os.path.join(LATEST_DIR, f"{dep}.json")
        dated_path = os.path.join(dated_dir, f"{dep}.json")

        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        with open(dated_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
