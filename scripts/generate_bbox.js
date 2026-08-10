const fs = require("fs");
const path = require("path");

const dossier = "data/latest";
const resultat = [];

for (let d = 1; d <= 95; d++) {

    const dep = String(d).padStart(2, "0");
    const fichier = path.join(dossier, `${dep}.json`);

    if (!fs.existsSync(fichier))
        continue;

    const stations = JSON.parse(
        fs.readFileSync(fichier, "utf8")
    );

    if (!stations.length)
        continue;

    let minLat = 999;
    let maxLat = -999;
    let minLon = 999;
    let maxLon = -999;

    stations.forEach(st => {

        const lat = Number(st.latitude);
        const lon = Number(st.longitude);

        if (!Number.isFinite(lat) ||
            !Number.isFinite(lon))
            return;

        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);

        minLon = Math.min(minLon, lon);
        maxLon = Math.max(maxLon, lon);

    });

    resultat.push({
        dep,
        nbStations: stations.length,
        minLat: Number(minLat.toFixed(5)),
        maxLat: Number(maxLat.toFixed(5)),
        minLon: Number(minLon.toFixed(5)),
        maxLon: Number(maxLon.toFixed(5))
    });

    console.log(
        dep,
        stations.length,
        "stations"
    );
}

fs.writeFileSync(
    "data/departements_bbox.json",
    JSON.stringify(resultat, null, 2),
    "utf8"
);

console.log(
    `departements_bbox.json généré (${resultat.length} départements)`
);
