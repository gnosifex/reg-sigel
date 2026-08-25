#!/usr/bin/env python3
"""Einmaliger Importer: erzeugt aus einer Markdown-Sigeltabelle je Zeile
einen Kurations-Record.

Der Bestand des Registers geht auf einen solchen Lauf zurueck — die
kuratierte Sigeltabelle des Betreibers, Stand 2026-08-24. Das Skript bleibt
als Provenienz im Repo und wird nicht erneut ausgefuehrt: Kurations-Edits
(Aliasse, Identitaeten, Haertegrade) wuerden ueberschrieben.

Erwartet wird eine Markdown-Pipe-Tabelle unter einer Ueberschrift „Gueltige
Sigel“; der Pfad ist Pflichtangabe, weil die Quelle ausserhalb dieses Repos
liegt.

Aufruf:
    python3 tools/seed_aus_sigeltabelle.py --quelle <pfad zur Tabelle> [--force]
"""

import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATION = os.path.join(REPO, "curation")

RE_CELEX = re.compile(r"CELEX[:\s]+([0-9A-Za-z\-]+)")
RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Norm-/Aktenzeichen-Muster, nach Trennschärfe geordnet.
DOC_REF_MUSTER = [
    re.compile(r"EBA/GL/\d{4}/\d{2}"),
    re.compile(r"Rundschreiben\s+\d{2}/\d{4}(?:\s*\([^)]+\))?"),
    re.compile(r"(?:Delegierte\s+Verordnung|Durchführungsverordnung|"
               r"Verordnung|Richtlinie)\s+\(EU\)\s+(?:Nr\.\s*)?\d+/\d+"),
    re.compile(r"ISO/IEC\s+\d+(?::\d{4})?"),
    re.compile(r"(?:NIST\s+)?SP\s+800-[0-9]+[A-Za-z0-9]*"),
    re.compile(r"Leitlinien\s+\d{2}/\d{4}"),
]


def slug(sigel):
    s = re.sub(r"[^0-9A-Za-z]+", "-", sigel.lower())
    return s.strip("-")


def identitaet(fassung, name, sigel):
    m = RE_CELEX.search(fassung)
    if m:
        return {"typ": "celex", "wert": m.group(1)}
    for muster in DOC_REF_MUSTER:
        for feld in (sigel, name, fassung):
            m = muster.search(feld)
            if m:
                return {"typ": "doc_ref", "wert": m.group(0).strip()}
    return {"typ": "offen", "wert": None}


def links(spalte):
    return [{"label": la.strip(), "url": u.strip()}
            for la, u in RE_LINK.findall(spalte)]


def tabelle_lesen(pfad):
    with open(pfad, encoding="utf-8") as f:
        zeilen = f.read().splitlines()
    inhalt, drin = [], False
    for z in zeilen:
        if z.startswith("## "):
            drin = "Gültige Sigel" in z
            continue
        if not drin:
            continue
        if not z.startswith("|"):
            continue
        zellen = [c.strip() for c in z.strip().strip("|").split("|")]
        if len(zellen) < 4:
            continue
        if zellen[0].lower() == "sigel" or set(zellen[0]) <= set("-: "):
            continue
        inhalt.append(zellen[:4])
    return inhalt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quelle", required=True,
                    help="Pfad zur Markdown-Sigeltabelle")
    ap.add_argument("--force", action="store_true",
                    help="vorhandene Records überschreiben")
    args = ap.parse_args()

    rows = tabelle_lesen(args.quelle)
    if not rows:
        print("FEHLER: keine Tabellenzeilen gefunden", file=sys.stderr)
        return 1

    os.makedirs(CURATION, exist_ok=True)
    neu = uebersprungen = 0
    for sigel, name, fassung, link in rows:
        rid = slug(sigel)
        ziel = os.path.join(CURATION, rid + ".json")
        if os.path.exists(ziel) and not args.force:
            uebersprungen += 1
            continue
        record = {
            "id": rid,
            "sigel": sigel,
            "name": name,
            "identitaet": identitaet(fassung, name, sigel),
            "fassung": fassung,
            "links": links(link),
            "aliasse": [],
            "status": "pilot-seed",
        }
        with open(ziel, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=False)
            f.write("\n")
        neu += 1

    print(f"Seed: {neu} Records geschrieben, {uebersprungen} übersprungen "
          f"(vorhanden), Quelle: {args.quelle}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
