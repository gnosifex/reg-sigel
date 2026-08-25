#!/usr/bin/env python3
"""Traegt die Gruppenzuordnung in jeden kuration-Record ein — idempotent.

Das Register ordnet seine Quellen nach absteigender regulatorischer
Verbindlichkeit; die Gruppen selbst stehen mit Titel und tragender Aussage in
`kuration/gruppen.json`, ihre Reihenfolge dort ist die Ausgabereihenfolge.
Dieses Skript verteilt nur die Record-IDs auf die Gruppen.

Ein Record, der bereits eine Gruppe traegt, wird nicht ueberschrieben:
Handpflege gewinnt.

Aufruf:
    python3 tools/migrate_gruppen.py [--pruefen]

`--pruefen` schreibt nicht, sondern meldet nur, was zu tun waere.
"""

import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KURATION = os.path.join(REPO, "kuration")
GRUPPEN_DATEI = os.path.join(KURATION, "gruppen.json")

# --- Zuordnung ------------------------------------------------------------
GRUPPEN_INHALT = {
    "eu-verordnungen": ("dora", "crr", "dsgvo", "ai-act"),
    "eu-durchfuehrung": ("rts-rmf", "rts-tppol", "rts-subcontracting",
                         "its-informationsregister", "its-vorfallmeldung"),
    "eu-richtlinien": ("crd",),
    "eu-leitlinien": ("eba-gl-2019-02", "eba-gl-2019-04", "eba-gl-2021-05",
                      "eba-gl-2022-03", "edsa-07-2020"),
    "nationale-gesetze": ("ao", "hgb", "kwg", "zag"),
    "nationale-aufsicht": ("marisk", "zag-marisk", "bait"),
    "standards-praktiken": ("iso-iec-27001-2022", "iso-iec-27002-2022",
                            "bsi-c5", "nist-sp-800-40r4", "sdm", "enisa-tig",
                            "cvss", "epss", "cis-controls", "pci-dss"),
}

ZUORDNUNG = {rid: gruppe
             for gruppe, rids in GRUPPEN_INHALT.items()
             for rid in rids}

FELDREIHENFOLGE = ("id", "sigel", "name", "haerte", "haerte_geprueft",
                   "gruppe", "identitaet", "fassung",
                   "links", "aliasse", "ersetzt", "ersetzt_durch", "status")


def umformen(record, notizen, bekannt):
    rid = record["id"]
    gruppe = record.get("gruppe")
    if gruppe and gruppe not in bekannt:
        # Die Gliederung wurde umgebaut; eine Gruppe, die es nicht mehr gibt,
        # ist keine Handpflege, die zu schuetzen waere.
        notizen.append(f"{rid}: Gruppe '{gruppe}' entfallen — neu zugeordnet")
        gruppe = None
    if not gruppe:
        gruppe = ZUORDNUNG.get(rid)
        if gruppe is None:
            notizen.append(f"{rid}: WARNUNG keine Zuordnung — bleibt ohne "
                           f"gruppe, der Build meldet das als Fehler")
        else:
            notizen.append(f"{rid}: gruppe = {gruppe}")

    neu = {}
    for feld in FELDREIHENFOLGE:
        if feld == "gruppe":
            if gruppe is not None:
                neu["gruppe"] = gruppe
            continue
        if feld in record:
            neu[feld] = record[feld]
    for feld in sorted(set(record) - set(FELDREIHENFOLGE)):
        neu[feld] = record[feld]
        notizen.append(f"{rid}: unbekanntes Feld '{feld}' unveraendert behalten")
    return neu


def main():
    nur_pruefen = "--pruefen" in sys.argv
    notizen, geaendert = [], 0

    with open(GRUPPEN_DATEI, encoding="utf-8") as f:
        bekannt = {g["id"] for g in json.load(f)["gruppen"]}
    unbekannt = set(GRUPPEN_INHALT) - bekannt
    if unbekannt:
        print(f"FEHLER: Zuordnung nennt Gruppen, die gruppen.json nicht "
              f"kennt: {sorted(unbekannt)}", file=sys.stderr)
        return 1

    for pfad in sorted(glob.glob(os.path.join(KURATION, "*.json"))):
        if os.path.abspath(pfad) == os.path.abspath(GRUPPEN_DATEI):
            continue
        with open(pfad, encoding="utf-8") as f:
            alt = json.load(f)
        neu = umformen(alt, notizen, bekannt)
        if neu == alt:
            continue
        geaendert += 1
        if not nur_pruefen:
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump(neu, f, ensure_ascii=False, indent=2)
                f.write("\n")

    for n in notizen:
        print(n)
    verb = "waeren zu aendern" if nur_pruefen else "geaendert"
    print(f"Migration Gruppen: {geaendert} Records {verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
