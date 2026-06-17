## -*- coding: utf-8 -*-

import json
import xml.etree.ElementTree as ET
from cache_utils import load_cache

XML_FILE = "PrixCarburants_instantane.xml"


def xml_coord_to_float(value, coord_type=None):
    if value is None:
        return None

    s = str(value).strip().replace(",", ".")

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


def build_station_record(pdv, cache):
    sid = str(pdv.get("id", "")).strip()

    lat = xml_coord_to_float(pdv.get("latitude"), "lat")
    lon = xml_coord_to_float(pdv.get("longitude"), "lon")

    return {
        "id": sid,
        "enseigne": cache.get(sid, {}).get("enseigne", ""),
        "adresse": (pdv.get("adresse") or "").strip(),
        "cp": (pdv.get("cp") or "").strip(),
        "ville": (pdv.get("ville") or "").strip(),
        "latitude": lat,
        "longitude": lon
    }


def main():
    cache = load_cache()

    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    data = []

    for pdv in root.findall("pdv"):
        data.append(build_station_record(pdv, cache))

    with open("departements.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
