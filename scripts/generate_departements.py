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


def dep_from_cp(cp):
    cp = (cp or "").strip()
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
        "enseigne": cache.get(sid, {}).get("enseigne", ""),
        "adresse": (pdv.get("adresse") or "").strip(),
        "cp": cp,
        "ville": (pdv.get("ville") or "").strip(),
        "latitude": pdv.get("latitude", ""),
        "longitude": pdv.get("longitude", ""),
        "carburants": extract_prices(pdv),
    }


def main():
    today = datetime.date.today().isoformat()
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(LATEST_DIR, exist_ok=True)

    print("Génération pour la date :", today)

    if not os.path.exists(XML_FILE):
        raise FileNotFoundError(f"Fichier XML introuvable: {XML_FILE}")

    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    pdvs = list(root.findall("pdv"))

    # 1) Cache commun : charge puis enrichit en parallèle si nécessaire
    cache = load_cache()
    sids = [str(pdv.get("id", "")).strip() for pdv in pdvs if pdv.get("id")]
    updated = update_cache_parallel(
        sids,
        cache,
        max_workers=MAX_WORKERS,
        force_refresh=FORCE_REFRESH,
        timeout=TIMEOUT,
    )
    if updated:
        save_cache(cache)

    # 2) Génération d'un JSON par département
    dep_map = {}
    for pdv in pdvs:
        cp = (pdv.get("cp") or "").strip()
        dep = dep_from_cp(cp)
        if not dep:
            continue
        dep_map.setdefault(dep, []).append(build_station_record(pdv, cache))

    # 3) Écriture des fichiers par département
    for dep_code, stations in sorted(dep_map.items()):
        output_file = os.path.join(LATEST_DIR, f"stations_{dep_code}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(stations, f, ensure_ascii=False, indent=2)
        print(f"{dep_code}: {len(stations)} stations -> {output_file}")


if __name__ == "__main__":
    main()
