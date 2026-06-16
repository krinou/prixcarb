import os
import xml.etree.ElementTree as ET
import math
import requests
import time
import json
from bs4 import BeautifulSoup

# --- fichier cache enrichi ---
ENSEIGNE_CACHE_FILE = "enseigne_cache.json"

HEADERS = {"User-Agent": "prixcarb/1.0 (contact: krinou@gmail.com)"}

# --- chargement cache ---
def load_cache():
    if os.path.exists(ENSEIGNE_CACHE_FILE):
       try:
          with open(ENSEIGNE_CACHE_FILE, "r", encoding="utf-8") as f:
               cache = json.load(f)
       except Exception as e:
          print("Erreur lecture cache:", e)
          cache = {} 
    else:
        cache = {}
        
    new_cache, changed = normalize_cache(cache)
    if changed:
       print("Cache normalisé → mise à jour")
       save_cache(new_cache)

    return new_cache


def normalize_cache(cache):
    """
    Convertit automatiquement les anciens formats (string)
    vers le nouveau format dict enrichi
    """
    changed = False
    new_cache = {}
    
    for sid, value in cache.items():
        # ancien format : "TotalEnergies"
        if isinstance(value, str):
           new_cache[sid] = {"enseigne": value}
           changed = True
        else:
           new_cache[sid] = value
 
    if changed:
        print("🔄 Cache normalisé (ancien format → nouveau format)")

    return new_cache, changed

# --- sauvegarde cache ---
def save_cache(cache):
    try:
        with open(ENSEIGNE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Erreur écriture cache: ", e)

# --- géocodage ---
def geocode_address(address):
    if not address:
        raise ValueError("Adresse vide")

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}

    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")

    data = r.json()
    if not data:
        raise ValueError(f"Aucun résultat pour : {address}")

    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])

    time.sleep(1)
    return lat, lon

# --- extraction enseigne ---
def extract_enseigne_from_soup(soup):
    block = soup.find("div", class_="fr-pb-3v")
    if block:
        parts = list(block.stripped_strings)
        if parts and parts[0].lower().startswith("marque"):
            parts = parts[1:]
        if parts:
            return parts[0].strip()
    return ""

# --- récupération enseigne avec cache ---
def get_enseigne(sid, cache):

    if sid in cache and "enseigne" in cache[sid]:
        return cache[sid]["enseigne"]

    url = f"https://www.prix-carburants.gouv.fr/station/{sid}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return ""

        soup = BeautifulSoup(r.text, "html.parser")
        enseigne = extract_enseigne_from_soup(soup)

        updated = False

        if sid not in cache:
           cache[sid] = {}
           updated = True

        if "enseigne" not in cache[sid] or cache[sid]["enseigne"] != enseigne:
           cache[sid]["enseigne"] = enseigne
           updated = True

        if updated:
           save_cache(cache)

        return enseigne

    except Exception:
        print(f"Erreur récupération enseigne id {sid}")
        return ""

# --- paramètres workflow ---
DEPS = set(os.environ.get("INPUT_DEPARTEMENTS", "").split(","))
FUEL_TAG = os.environ.get("INPUT_CARBURANT", "E10")
ADRESSE_REF = os.environ.get("INPUT_ADRESSE", "")

print(f"Géocodage : {ADRESSE_REF}")
REF_LAT, REF_LON = geocode_address(ADRESSE_REF)

# --- paramètres calcul ---
CONSO = 10
VOLUME = 50

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)

    return 2 * R * math.asin(math.sqrt(a))

# --- chargement XML ---
xml_file = "PrixCarburants_instantane.xml"
tree = ET.parse(xml_file)
root = tree.getroot()

# --- chargement cache ---
cache = load_cache()

stations_out = []

for pdv in root.findall("pdv"):

    cp = pdv.get("cp")
    if not cp or cp[:2] not in DEPS:
        continue

    sid = pdv.get("id")

    adresse = pdv.findtext("adresse") or ""
    ville = pdv.findtext("ville") or ""
    lat = float(pdv.get("latitude")) / 100000
    lon = float(pdv.get("longitude")) / 100000

    # --- récup enseigne ---
    enseigne = get_enseigne(sid, cache)
