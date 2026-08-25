#!/usr/bin/env python3
"""Fassungs-Check: registrierte Konsolidierung gegen den Cellar-Bestand.

Prueft jeden Record mit `identitaet.typ: celex`, ob die in
`fassung.konsolidierung` registrierte Fassung noch die juengste ist, die
das Cellar der EU-Publikationsstelle fuehrt. Andere Ankertypen sind nicht
abgedeckt — sie haben keine maschinell abfragbare Fassungsliste.

Zwei Wege, in dieser Reihenfolge:

(a) SPARQL gegen https://publications.europa.eu/webapi/rdf/sparql — der
    Standardweg: eine Abfrage je Basisakt, Antwort im Kilobyte-Bereich.
(b) Notice-XML `Accept: application/xml;notice=branch` auf die
    Basis-CELEX — Fallback, rund 3 MB je Akt, Konsolidierungs-CELEX per
    Regex.

`watch` liest nur. Es aendert nie `kuration/` oder `dist/`; ein Befund ist
ein Auftrag an die Handpflege, kein automatischer Nachzug.

Aufruf:
    python3 tools/watch.py [--json <pfad>]

Exit 0, wenn kein Record veraltet ist (unpruefbar bleibt Warnung);
Exit 1, sobald mindestens ein Record veraltet ist.
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KURATION = os.path.join(REPO, "kuration")
GRUPPEN_DATEI = os.path.join(KURATION, "gruppen.json")

SPARQL_ENDPUNKT = "https://publications.europa.eu/webapi/rdf/sparql"
NOTICE_URL = "http://publications.europa.eu/resource/celex/{}"
USER_AGENT = "reg-sigel-watch/0.1"
TAKT_SEKUNDEN = 1.0
TIMEOUT = 90

# Konsolidierte CELEX: Sektor 0 statt 3, dahinter das Fassungsdatum.
KONS_MUSTER = re.compile(r"\b0\d{4}[A-Z]{1,2}\d{4}(?:\(\d+\))?-\d{8}\b")
DATUM_SUFFIX = re.compile(r"-(\d{8})$")

STATUS_AKTUELL = "aktuell"
STATUS_VERALTET = "veraltet"
STATUS_UNPRUEFBAR = "unpruefbar"

_letzter_abruf = [0.0]


def takten():
    """Sequenziell, hoechstens ein Request je Sekunde."""
    wartezeit = TAKT_SEKUNDEN - (time.monotonic() - _letzter_abruf[0])
    if wartezeit > 0:
        time.sleep(wartezeit)
    _letzter_abruf[0] = time.monotonic()


def kons_basis(basis_celex):
    """Basis-CELEX -> Praefix der konsolidierten Fassungen (32013L0036 -> 02013L0036)."""
    return "0" + basis_celex[1:]


def sortier_datum(celex):
    treffer = DATUM_SUFFIX.search(celex)
    return treffer.group(1) if treffer else ""


def abrufen(url, kopfzeilen, daten=None):
    """Ein Abruf im Takt; gibt (bytes, groesse) zurueck."""
    takten()
    anfrage = urllib.request.Request(url, data=daten, headers=kopfzeilen)
    with urllib.request.urlopen(anfrage, timeout=TIMEOUT) as antwort:
        inhalt = antwort.read()
    return inhalt, len(inhalt)


def weg_sparql(basis_celex):
    """Standardweg: Konsolidierungsliste als SPARQL-Ergebnis."""
    praefix = kons_basis(basis_celex)
    abfrage = (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "SELECT DISTINCT ?celex WHERE {\n"
        "  ?work cdm:resource_legal_id_celex ?celex .\n"
        '  FILTER(STRSTARTS(STR(?celex), "%s-"))\n'
        "}\n" % praefix
    )
    url = SPARQL_ENDPUNKT + "?" + urllib.parse.urlencode({
        "query": abfrage,
        "format": "application/sparql-results+json",
    })
    roh, groesse = abrufen(url, {
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT,
    })
    ergebnis = json.loads(roh.decode("utf-8"))
    gefunden = sorted({
        b["celex"]["value"]
        for b in ergebnis["results"]["bindings"]
        if KONS_MUSTER.fullmatch(b["celex"]["value"])
    })
    return gefunden, groesse


def weg_notice(basis_celex):
    """Fallback: Konsolidierungs-CELEX aus dem Notice-XML des Basisakts."""
    # Ohne `Accept-Language` weist das Cellar `notice=branch` mit HTTP 400
    # ab („Invalid content type BRANCH for WORK without language"); die
    # Sprache waehlt nur die Textausgabe, die CELEX-Liste ist dieselbe.
    roh, groesse = abrufen(NOTICE_URL.format(basis_celex), {
        "Accept": "application/xml;notice=branch",
        "Accept-Language": "deu",
        "User-Agent": USER_AGENT,
    })
    text = roh.decode("utf-8", errors="replace")
    praefix = kons_basis(basis_celex) + "-"
    gefunden = sorted({t for t in KONS_MUSTER.findall(text)
                       if t.startswith(praefix)})
    return gefunden, groesse


def fassungen_holen(basis_celex):
    """SPARQL zuerst, Notice als Fallback; liefert (liste, weg, groesse, fehler)."""
    try:
        gefunden, groesse = weg_sparql(basis_celex)
        if gefunden:
            return gefunden, "sparql", groesse, None
        sparql_hinweis = "SPARQL ohne Treffer"
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as e:
        sparql_hinweis = f"SPARQL fehlgeschlagen ({type(e).__name__}: {e})"

    try:
        gefunden, groesse = weg_notice(basis_celex)
        return gefunden, "notice", groesse, sparql_hinweis
    except (urllib.error.URLError, TimeoutError) as e:
        return ([], None, 0,
                f"{sparql_hinweis}; Notice fehlgeschlagen "
                f"({type(e).__name__}: {e})")


def einstufen(registriert, gefunden, weg, fehler):
    """Statuslogik: aktuell, veraltet oder unpruefbar — mit Begruendung."""
    if weg is None:
        return STATUS_UNPRUEFBAR, fehler or "kein Weg lieferte eine Antwort"
    juengste = max(gefunden, key=sortier_datum) if gefunden else None

    if registriert is None:
        if juengste is None:
            return STATUS_AKTUELL, "keine Konsolidierung registriert, keine im Cellar"
        return (STATUS_VERALTET,
                "Record fuehrt keine Konsolidierung, das Cellar schon")
    if juengste is None:
        return STATUS_UNPRUEFBAR, "Cellar liefert keine Konsolidierungen"
    if registriert == juengste:
        return STATUS_AKTUELL, ""
    if registriert in gefunden:
        return STATUS_VERALTET, "juengere Konsolidierung vorhanden"
    return (STATUS_UNPRUEFBAR,
            "registrierte Fassung steht nicht in der Cellar-Liste")


def records_lesen():
    out = []
    for pfad in sorted(glob.glob(os.path.join(KURATION, "*.json"))):
        if os.path.abspath(pfad) == os.path.abspath(GRUPPEN_DATEI):
            continue
        with open(pfad, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def pruefen(records):
    befunde, nicht_abgedeckt = [], {}
    for r in sorted(records, key=lambda x: x["id"]):
        typ = (r.get("identitaet") or {}).get("typ")
        if typ != "celex":
            nicht_abgedeckt[typ] = nicht_abgedeckt.get(typ, 0) + 1
            continue
        basis = r["identitaet"]["wert"]
        registriert = (r.get("fassung") or {}).get("konsolidierung")
        gefunden, weg, groesse, fehler = fassungen_holen(basis)
        status, begruendung = einstufen(registriert, gefunden, weg, fehler)
        befunde.append({
            "id": r["id"],
            "sigel": r["sigel"],
            "basis_celex": basis,
            "registriert": registriert,
            "juengste": (max(gefunden, key=sortier_datum)
                         if gefunden else None),
            "anzahl_fassungen": len(gefunden),
            "status": status,
            "begruendung": begruendung,
            "weg": weg,
            "antwortgroesse": groesse,
        })
    return befunde, nicht_abgedeckt


def bericht(befunde, nicht_abgedeckt, stand):
    zaehler = {STATUS_AKTUELL: 0, STATUS_VERALTET: 0, STATUS_UNPRUEFBAR: 0}
    for b in befunde:
        zaehler[b["status"]] += 1

    zeilen = []
    veraltet = zaehler[STATUS_VERALTET]
    if veraltet:
        kern = (f"{veraltet} von {len(befunde)} EU-Rechtsakten fuehren eine "
                f"ueberholte Konsolidierung.")
    elif zaehler[STATUS_UNPRUEFBAR]:
        kern = (f"Keine ueberholte Konsolidierung; "
                f"{zaehler[STATUS_UNPRUEFBAR]} Record(s) blieben unpruefbar.")
    else:
        kern = (f"Alle {len(befunde)} EU-Rechtsakte stehen auf ihrer "
                f"juengsten Konsolidierung.")
    zeilen += [f"Fassungs-Check gegen das Cellar — Stand {stand}", "", kern, ""]

    breite = max((len(b["sigel"]) for b in befunde), default=6)
    for b in befunde:
        zeilen.append(f"  {b['status']:<11} {b['sigel']:<{breite}}  "
                      f"registriert {b['registriert'] or '—'}  ·  "
                      f"juengste {b['juengste'] or '—'}")
        detail = (f"{b['weg'] or 'kein Weg'}, {b['anzahl_fassungen']} "
                  f"Fassungen, {b['antwortgroesse']} Bytes")
        if b["begruendung"]:
            detail += f" — {b['begruendung']}"
        zeilen.append(f"  {'':<11} {'':<{breite}}  {detail}")

    if nicht_abgedeckt:
        teile = ", ".join(f"{n} × {t}" for t, n
                          in sorted(nicht_abgedeckt.items()))
        zeilen += ["", f"Nicht abgedeckt: {teile} — nur der CELEX-Anker "
                       "fuehrt zu einer abfragbaren Fassungsliste."]

    zeilen += ["", f"Ergebnis: {zaehler[STATUS_AKTUELL]} aktuell, "
                   f"{veraltet} veraltet, "
                   f"{zaehler[STATUS_UNPRUEFBAR]} unpruefbar."]
    return "\n".join(zeilen), zaehler


def main():
    p = argparse.ArgumentParser(description="Fassungs-Check gegen das Cellar")
    p.add_argument("--json", metavar="PFAD",
                   help="Befunde zusaetzlich als JSON ablegen")
    args = p.parse_args()

    stand = time.strftime("%Y-%m-%d")
    records = records_lesen()
    if not records:
        print("FEHLER: keine Records in kuration/", file=sys.stderr)
        return 1

    befunde, nicht_abgedeckt = pruefen(records)
    text, zaehler = bericht(befunde, nicht_abgedeckt, stand)
    print(text)

    if args.json:
        ausgabe = {
            "stand": stand,
            "werkzeug": USER_AGENT,
            "zusammenfassung": zaehler,
            "nicht_abgedeckt": nicht_abgedeckt,
            "befunde": befunde,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(ausgabe, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return 1 if zaehler[STATUS_VERALTET] else 0


if __name__ == "__main__":
    sys.exit(main())
