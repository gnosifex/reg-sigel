#!/usr/bin/env python3
"""Migration curation/ von Schema v1 auf v2 — in place, idempotent, netzfrei.

Fuenf Aenderungen (siehe README, Abschnitt Record-Schema):

1. `identitaet.wert` traegt bei `typ: celex` die BASIS-CELEX (Sektor 3).
   Konsolidierte Codes (Muster `0…-JJJJMMTT`) wandern in die Fassung.
2. `fassung` wird zum Objekt `{stand, konsolidierung, text}`; `text` ist der
   bisherige Freitext unveraendert, `stand` nur bei eindeutig parsebarem
   Stichdatum, sonst null.
3. Ankertypen `jurabk` (deutsche Gesetze) und `version` (Standards ohne
   Dokumentnummer) loesen `offen` bzw. missbrauchtes `doc_ref` ab.
4. Jeder Link und jeder Identitaetsanker traegt `geprueft: {datum, methode}`.
5. Jeder Record traegt `ersetzt` und `ersetzt_durch` (Record-IDs).

Aufruf:
    python3 tools/migrate_v2.py [--pruefen]

`--pruefen` schreibt nicht, sondern meldet nur, was zu tun waere.
Das Skript seedet nie neu — es liest die vorhandenen Kurationsstaende und
schreibt sie umgeformt zurueck.
"""

import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATION = os.path.join(REPO, "curation")
GRUPPEN_DATEI = os.path.join(CURATION, "groups.json")

# --- Verifikationsstand des ersten Laufs (2026-08-25) ---------------------
# Web-Abruf: Link tatsaechlich geoeffnet und bestaetigt.
WEB_ABRUF_LINKS = {"zag", "sdm", "bsi-c5"}
# Mechanisch aus der CELEX gebaut, nicht abgerufen.
KONSTRUIERT_LINKS = {"ai-act", "dsgvo"}
# jurabk-Anker am Portal geprueft.
WEB_ABRUF_IDENT = {"ao", "hgb", "kwg", "zag"}

GEPRUEFT_WEB = {"datum": "2026-08-25", "methode": "web-abruf"}
GEPRUEFT_KONSTRUIERT = {"datum": "2026-08-25", "methode": "konstruiert"}
GEPRUEFT_SEED = {"datum": "2026-08-24", "methode": "seed-doksigel"}

# --- Ankertypen -----------------------------------------------------------
# Deutsche Gesetze: juris-Abkuerzung, Werte stehen bereits in den Records.
JURABK = {"ao", "hgb", "kwg", "zag"}
# Standards ohne Dokumentnummer: Versionslabel aus dem Fassungstext.
VERSION_LABEL = {
    "cvss": "v4.0",
    "epss": "v5",
    "cis-controls": "v8.1",
    "pci-dss": "v4.0.1",
    "bsi-c5": "C5:2026",
    "sdm": "V3.1a",
    "enisa-tig": "v1.0",
}

# --- Fassungs-Parsing -----------------------------------------------------
# Nur diese drei Muster gelten als eindeutiges Stichdatum. Ein nacktes Datum
# ohne Schluesselwort wird NICHT uebernommen (koennte Erlass-, Anwendungs-
# oder Aufhebungsdatum sein), und mehrere abweichende Treffer heben sich auf.
STAND_MUSTER = (
    re.compile(r"\bStand (\d{2})\.(\d{2})\.(\d{4})"),
    re.compile(r"\bvom (\d{2})\.(\d{2})\.(\d{4})"),
    re.compile(r"\bFassung (\d{2})\.(\d{2})\.(\d{4})"),
)

CELEX_KONSOLIDIERT = re.compile(r"^0(\d{4}[A-Z]\d{4})-(\d{8})$")
CELEX_BASIS = re.compile(r"^3\d{4}[A-Z]\d{4}$")

FELDREIHENFOLGE = ("id", "sigel", "name", "haerte", "haerte_geprueft",
                   "gruppe", "identitaet", "fassung",
                   "links", "aliasse", "ersetzt", "ersetzt_durch", "status")

# Spaetere Schemafelder, die diese Migration nicht erzeugt, aber unveraendert
# durchreicht — sonst fielen sie beim Lauf auf einem neueren Bestand weg.
DURCHREICHEN = ("haerte", "haerte_geprueft", "gruppe")


def stand_aus_text(text):
    """ISO-Stichdatum, wenn genau ein Muster genau einen Wert liefert."""
    treffer = set()
    for muster in STAND_MUSTER:
        for tag, monat, jahr in muster.findall(text):
            treffer.add(f"{jahr}-{monat}-{tag}")
    if len(treffer) == 1:
        return treffer.pop()
    return None


def identitaet_v2(rid, ident, notizen):
    typ, wert = ident.get("typ"), ident.get("wert")
    konsolidierung = None

    if rid in JURABK:
        if typ != "jurabk":
            notizen.append(f"{rid}: identitaet.typ {typ} -> jurabk")
        typ = "jurabk"
    elif rid in VERSION_LABEL:
        label = VERSION_LABEL[rid]
        if typ != "version" or wert != label:
            notizen.append(f"{rid}: identitaet {typ}:{wert} -> version:{label}")
        typ, wert = "version", label
    elif typ == "celex" and wert:
        m = CELEX_KONSOLIDIERT.match(wert)
        if m:
            basis = "3" + m.group(1)
            konsolidierung = wert
            notizen.append(f"{rid}: CELEX {wert} -> Basis {basis}, "
                           f"Konsolidierung in die Fassung")
            wert = basis
        elif not CELEX_BASIS.match(wert):
            notizen.append(f"{rid}: WARNUNG CELEX '{wert}' passt auf kein "
                           f"bekanntes Muster — unveraendert uebernommen")

    if rid in WEB_ABRUF_IDENT:
        geprueft = dict(GEPRUEFT_WEB)
    else:
        geprueft = dict(GEPRUEFT_SEED)

    return {"typ": typ, "wert": wert, "geprueft": geprueft}, konsolidierung


def fassung_v2(rid, roh, konsolidierung, notizen):
    if isinstance(roh, dict):          # bereits v2
        text = roh.get("text", "")
        alt_kons = roh.get("konsolidierung")
        konsolidierung = konsolidierung or alt_kons
    else:
        text = roh
    stand = stand_aus_text(text)
    if stand:
        notizen.append(f"{rid}: fassung.stand = {stand}")
    return {"stand": stand, "konsolidierung": konsolidierung, "text": text}


def links_v2(rid, links):
    if rid in WEB_ABRUF_LINKS:
        geprueft = GEPRUEFT_WEB
    elif rid in KONSTRUIERT_LINKS:
        geprueft = GEPRUEFT_KONSTRUIERT
    else:
        geprueft = GEPRUEFT_SEED
    out = []
    for link in links:
        neu = {"label": link["label"], "url": link["url"]}
        neu["geprueft"] = link.get("geprueft") or dict(geprueft)
        out.append(neu)
    return out


def migrieren(record, notizen):
    rid = record["id"]
    ident, konsolidierung = identitaet_v2(rid, record["identitaet"], notizen)
    neu = {
        "id": rid,
        "sigel": record["sigel"],
        "name": record["name"],
        "identitaet": ident,
        "fassung": fassung_v2(rid, record["fassung"], konsolidierung, notizen),
        "links": links_v2(rid, record.get("links", [])),
        "aliasse": record.get("aliasse", []),
        "ersetzt": record.get("ersetzt", []),
        "ersetzt_durch": record.get("ersetzt_durch", []),
        "status": record["status"],
    }
    for feld in DURCHREICHEN:
        if feld in record:
            neu[feld] = record[feld]
    neu = {feld: neu[feld] for feld in FELDREIHENFOLGE if feld in neu}

    unbekannt = set(record) - set(FELDREIHENFOLGE)
    for feld in sorted(unbekannt):
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
        neu = migrieren(alt, notizen)
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
    print(f"Migration v2: {geaendert} Records {verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
