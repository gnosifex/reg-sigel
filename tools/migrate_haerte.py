#!/usr/bin/env python3
"""Traegt den Haertegrad in jeden curation-Record ein — idempotent, netzfrei.

Der Haertegrad sagt, wie fest die Kurzform an ihre Quelle gebunden ist:
`amtlich` (vom Normgeber/Herausgeber foermlich vergeben), `herausgeberueblich`
(der Herausgeber verwendet die Form selbst), `verkehrsueblich` (breite Praxis
ohne amtliche Vergabe), `hausform` (Konvention dieses Registers).

Die Zuordnung unten ist kuratierte Einschaetzung, keine Messung — genau das
haelt `haerte_geprueft.methode: einschaetzung` fest. Ein Record, der bereits
einen Haertegrad traegt, wird nicht ueberschrieben: Handpflege gewinnt.

Aufruf:
    python3 tools/migrate_haerte.py [--pruefen]

`--pruefen` schreibt nicht, sondern meldet nur, was zu tun waere.
"""

import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATION = os.path.join(REPO, "curation")
GRUPPEN_DATEI = os.path.join(CURATION, "groups.json")

GEPRUEFT = {"datum": "2026-08-25", "methode": "einschaetzung"}

# --- Zuordnung ------------------------------------------------------------
# amtlich: die Kurzform ist foermlich vergeben — juris-Abkuerzung deutscher
# Gesetze, Dokumentkennzeichen des Herausgebers, Normnummer.
AMTLICH = {
    "ao", "hgb", "kwg", "zag",                       # jurabk
    "eba-gl-2019-02", "eba-gl-2019-04",
    "eba-gl-2021-05", "eba-gl-2022-03",              # EBA-Dokumentkennzeichen
    "edsa-07-2020",                                  # EDSA-Leitliniennummer
    "iso-iec-27001-2022", "iso-iec-27002-2022",      # Normnummern
    "nist-sp-800-40r4",                              # NIST-Publikationsnummer
}

# herausgeberueblich: keine foermliche Vergabe, aber der Herausgeber fuehrt
# die Form selbst in seinen Publikationen.
HERAUSGEBERUEBLICH = {
    "marisk", "zag-marisk", "bait",                  # BaFin
    "bsi-c5",                                        # BSI
    "cvss", "epss",                                  # FIRST
    "cis-controls",                                  # CIS
    "pci-dss",                                       # PCI SSC
    "sdm",                                           # DSK
    "enisa-tig",                                     # ENISA
}

# verkehrsueblich: breite Praxis fuer EU-Rechtsakte, die selbst keine
# Kurzform vergeben.
VERKEHRSUEBLICH = {"dora", "crr", "crd", "dsgvo", "ai-act"}

# hausform: eigene Konvention dieses Registers, nirgends sonst gebraeuchlich.
HAUSFORM = {
    "rts-rmf", "rts-tppol", "rts-subcontracting",
    "its-informationsregister", "its-vorfallmeldung",
}

ZUORDNUNG = {}
for menge, stufe in ((AMTLICH, "amtlich"),
                     (HERAUSGEBERUEBLICH, "herausgeberueblich"),
                     (VERKEHRSUEBLICH, "verkehrsueblich"),
                     (HAUSFORM, "hausform")):
    for rid in menge:
        ZUORDNUNG[rid] = stufe

# Feldreihenfolge des Schemas; `haerte` steht bei Sigel und Name, weil es
# die Kurzform qualifiziert, nicht das Dokument.
FELDREIHENFOLGE = ("id", "sigel", "name", "haerte", "haerte_geprueft",
                   "gruppe", "identitaet", "fassung",
                   "links", "aliasse", "ersetzt", "ersetzt_durch", "status")


def umformen(record, notizen):
    rid = record["id"]
    haerte = record.get("haerte")
    if not haerte:
        haerte = ZUORDNUNG.get(rid)
        if haerte is None:
            notizen.append(f"{rid}: WARNUNG keine Zuordnung — bleibt ohne "
                           f"haerte, der Build meldet das als Fehler")
        else:
            notizen.append(f"{rid}: haerte = {haerte}")

    neu = {}
    for feld in FELDREIHENFOLGE:
        if feld == "haerte":
            if haerte is not None:
                neu["haerte"] = haerte
            continue
        if feld == "haerte_geprueft":
            if haerte is not None:
                neu["haerte_geprueft"] = (record.get("haerte_geprueft")
                                          or dict(GEPRUEFT))
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

    for pfad in sorted(glob.glob(os.path.join(CURATION, "*.json"))):
        if os.path.abspath(pfad) == os.path.abspath(GRUPPEN_DATEI):
            continue
        with open(pfad, encoding="utf-8") as f:
            alt = json.load(f)
        neu = umformen(alt, notizen)
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
    print(f"Migration Haerte: {geaendert} Records {verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
