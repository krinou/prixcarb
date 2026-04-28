import os
import json
import datetime
import xml.etree.ElementTree as ET

# Date du jour (UTC)
today = datetime.date.today().isoformat()

BASE_DIR = f"data/{today}"
LATEST_DIR = "data/latest"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(LATEST_DIR, exist_ok=True)

print("Génération pour la date :", today)

# Exemple : charger le XML déjà téléchargé ou le télécharger ici
xml_file = "PrixCarburants_instantane.xml"
tree = ET.parse(xml_file)
root = tree.getroot()

# Départements 01 à 95 (à adapter si besoin)
for dep in range(1, 96):
    dep_code = f"{dep:02d}"
    stations = []

    for pdv in root.findall("pdv"):
        cp = pdv.get("cp")
        if not cp or not cp.startswith(dep_code):
            continue

        station = {
            "id": pdv.get("id"),
            "lat": float(pdv.get("latitude")) / 100000,
            "lon": float(pdv.get("longitude")) / 100000,
            "cp": cp,
            "ville": pdv.findtext("ville") or "",
            "prix": {},
            "maj_gouv": {}
        }

        for p in pdv.findall("prix"):
            carb = p.get("nom")
            station["prix"][carb] = float(p.get("valeur")) / 1000
            station["maj_gouv"][carb] = p.get("maj")

        stations.append(station)

    out = {
        "departement": dep_code,
        "date": today,
        "stations": stations
    }

    out_file = f"{BASE_DIR}/dep-{dep_code}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Copie vers latest
    latest_file = f"{LATEST_DIR}/dep-{dep_code}.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"✅ dep-{dep_code}.json généré ({len(stations)} stations)")
