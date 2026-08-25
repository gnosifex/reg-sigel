#!/usr/bin/env python3
"""Leitplanke des automatischen Ingests — als CI-Prüfung statt als Zusage.

Die Aufnahme-Routine darf genau dreierlei: neue Records anlegen, bestehende
Records um Aliasse und Evidenz **ergänzen**, und die Ausgabe neu bauen. Alles
andere — Werkzeuge, Workflows, README, Gliederung, Prüfquellen, Änderungen an
bestehenden Feldern, Löschungen — ist Maintainer-Sache.

Bislang stand das nur im Auftragstext der Routine. Ein Auftragstext ist eine
Bitte; dieser Guard ist eine Bedingung: Er liest den Diff des Pull Requests
gegen die Basis und beendet den Lauf mit Exit 1, sobald etwas darin liegt,
was die Routine nicht anlegen darf. Ob eine Änderung *gemeint* war, spielt
keine Rolle — der Guard prüft, was im Diff steht.

Aufruf:
    python3 tools/intake_guard.py --basis origin/main
    python3 tools/intake_guard.py --selbsttest

Nur Stdlib, kein Netz. `git` muss erreichbar sein.
"""

import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tools", "tests")

# Konfiguration der Kurationsschicht — sie traegt keine Records und wird nie
# vom Ingest angefasst. Wer die Pruefquellen kontrolliert, kontrolliert das
# Register.
KONFIG_DATEIEN = ("kuration/gruppen.json", "kuration/pruefquellen.json")
# Erzeugnisse des Builds. Sie duerfen sich aendern, weil `build.py` sie
# schreibt; ob sie zur Kuration passen, prueft der Build-Workflow.
GENERATE = ("dist/sigel.json", "dist/SIGEL.md", "docs/index.html")


# --- Diff lesen ------------------------------------------------------------

def git(*args):
    lauf = subprocess.run(["git", "-C", REPO, *args],
                          capture_output=True, text=True, timeout=120)
    if lauf.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {lauf.stderr.strip()}")
    return lauf.stdout


def aenderungen_lesen(basis, spitze):
    """(status, pfad, altpfad) je geänderter Datei — Basis ist der Mergepunkt."""
    roh = git("diff", "--name-status", "-M", f"{basis}...{spitze}")
    out = []
    for zeile in roh.splitlines():
        if not zeile.strip():
            continue
        teile = zeile.split("\t")
        status = teile[0]
        if status.startswith("R") and len(teile) >= 3:
            out.append((status[0], teile[2], teile[1]))
        else:
            out.append((status[0], teile[1], None))
    return out


def datei_bei(ref, pfad):
    try:
        return git("show", f"{ref}:{pfad}")
    except RuntimeError:
        return None


# --- Der additive Vergleich ------------------------------------------------

def additiv_pruefen(vorher, nachher):
    """Ist `nachher` eine reine Ergänzung von `vorher`? Rückgabe: Befundliste.

    Erlaubt ist genau zweierlei: ein neuer Alias-Eintrag, und eine neue
    Evidenz-ID in einem bestehenden Alias. Jedes andere Feld muss Zeichen
    für Zeichen gleich bleiben — auch `status`, auch `haerte`.
    """
    befunde = []
    if not isinstance(vorher, dict) or not isinstance(nachher, dict):
        return ["Record ist kein JSON-Objekt."]

    entfallen = sorted(set(vorher) - set(nachher))
    if entfallen:
        befunde.append(f"Felder entfallen: {', '.join(entfallen)}")
    neue_felder = sorted(set(nachher) - set(vorher))
    if neue_felder:
        befunde.append(f"neue Felder: {', '.join(neue_felder)}")

    for feld in sorted(set(vorher) & set(nachher)):
        if feld == "aliasse":
            continue
        if vorher[feld] != nachher[feld]:
            befunde.append(f"Feld `{feld}` geändert")

    alt = vorher.get("aliasse") or []
    neu = nachher.get("aliasse") or []
    if not isinstance(neu, list):
        return befunde + ["`aliasse` ist keine Liste."]
    neu_nach_form = {}
    for a in neu:
        if not isinstance(a, dict) or not a.get("form"):
            befunde.append("Alias-Eintrag ohne `form`")
            continue
        neu_nach_form[a["form"]] = a
    for a in alt:
        form = a.get("form")
        gegenstueck = neu_nach_form.get(form)
        if gegenstueck is None:
            befunde.append(f"Alias `{form}` entfernt")
            continue
        for feld in ("sprache",):
            if a.get(feld) != gegenstueck.get(feld):
                befunde.append(f"Alias `{form}`: `{feld}` geändert")
        alte_ev = a.get("evidenz") or []
        neue_ev = gegenstueck.get("evidenz") or []
        if alte_ev != neue_ev[:len(alte_ev)]:
            befunde.append(f"Alias `{form}`: bestehende Evidenz geändert")
    return befunde


# --- Die Regel je Datei ----------------------------------------------------

def datei_pruefen(status, pfad, altpfad, basis, spitze):
    """Ein Befund je unzulässiger Änderung; leere Liste heißt: erlaubt."""
    if status == "D":
        return [f"`{pfad}`: gelöscht — der Ingest löscht nie."]
    if status == "R":
        return [f"`{pfad}`: umbenannt (aus `{altpfad}`) — der Ingest "
                f"benennt nie um."]

    if pfad in GENERATE:
        return []
    if pfad in KONFIG_DATEIEN:
        return [f"`{pfad}`: Konfiguration der Kurationsschicht — sie ändert "
                f"allein der Maintainer."]

    if pfad.startswith("raw/"):
        if status == "A":
            return []
        return [f"`{pfad}`: bestehende Evidenz geändert — `raw/` ist "
                f"append-only."]

    if pfad.startswith("kuration/"):
        if status == "A":
            return []
        vorher_roh = datei_bei(basis, pfad)
        nachher_roh = datei_bei(spitze, pfad)
        if vorher_roh is None or nachher_roh is None:
            return [f"`{pfad}`: Fassung nicht lesbar — nicht bewertbar."]
        try:
            vorher, nachher = json.loads(vorher_roh), json.loads(nachher_roh)
        except json.JSONDecodeError as e:
            return [f"`{pfad}`: kein gültiges JSON ({e})."]
        befunde = additiv_pruefen(vorher, nachher)
        return [f"`{pfad}`: {b}" for b in befunde]

    return [f"`{pfad}`: liegt außerhalb von `kuration/`, `raw/`, `dist/` und "
            f"`docs/` — der Ingest fasst nichts davon an."]


def pruefen(basis, spitze):
    befunde = []
    aenderungen = aenderungen_lesen(basis, spitze)
    for status, pfad, altpfad in aenderungen:
        befunde += datei_pruefen(status, pfad, altpfad, basis, spitze)
    return aenderungen, befunde


# --- Selbsttest ------------------------------------------------------------
# Zwei Faelle, wie bei `intake.py`: einer, der durchgehen muss, und einer,
# der nicht durchgehen darf. Geprueft wird der tragende Teil — der feldweise
# Vergleich; der Rest des Guards ist Wegfindung im Diff.

SELBSTTESTS = (
    ("guard-additiv", True,
     "Neuer Alias plus neue Evidenz an einem bestehenden Alias."),
    ("guard-feldaenderung", False,
     "Ein bestehendes Feld wurde geändert."),
)


def selbsttest():
    fehlgeschlagen = 0
    for name, erwartet_ok, beschreibung in SELBSTTESTS:
        ordner = os.path.join(TESTS, name)
        with open(os.path.join(ordner, "vorher.json"), encoding="utf-8") as f:
            vorher = json.load(f)
        with open(os.path.join(ordner, "nachher.json"), encoding="utf-8") as f:
            nachher = json.load(f)
        befunde = additiv_pruefen(vorher, nachher)
        ok = not befunde
        zeichen = "OK  " if ok == erwartet_ok else "FEHL"
        print(f"{zeichen} {name}: {beschreibung}")
        for b in befunde:
            print(f"       Befund: {b}")
        if ok != erwartet_ok:
            fehlgeschlagen += 1
    if fehlgeschlagen:
        print(f"\n{fehlgeschlagen} Selbsttest(s) fehlgeschlagen.",
              file=sys.stderr)
        return 1
    print(f"\n{len(SELBSTTESTS)} Selbsttests bestanden.")
    return 0


# --- Ablauf ----------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--basis", default="origin/main",
                   help="Vergleichspunkt (Default: origin/main)")
    p.add_argument("--spitze", default="HEAD",
                   help="zu prüfender Stand (Default: HEAD)")
    p.add_argument("--selbsttest", action="store_true",
                   help="die beiden Fixtures prüfen, sonst nichts")
    args = p.parse_args()

    if args.selbsttest:
        return selbsttest()

    try:
        aenderungen, befunde = pruefen(args.basis, args.spitze)
    except RuntimeError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 1

    print(f"intake-guard: {len(aenderungen)} geänderte Datei(en) gegen "
          f"`{args.basis}`.")
    for status, pfad, altpfad in aenderungen:
        print(f"  {status} {pfad}" + (f" (aus {altpfad})" if altpfad else ""))
    if befunde:
        print("\nDer Diff enthält Änderungen, die der automatische Ingest "
              "nicht vornehmen darf:", file=sys.stderr)
        for b in befunde:
            print(f"  - {b}", file=sys.stderr)
        print("\nErlaubt sind allein: neue Dateien unter `kuration/` (außer "
              "gruppen.json und pruefquellen.json) und `raw/`, rein additive "
              "Ergänzungen an bestehenden kuration-Records (neue Aliasse, "
              "neue Evidenz-IDs) sowie der neu gebaute Stand von `dist/` und "
              "`docs/`.", file=sys.stderr)
        return 1
    print("\nAlles innerhalb der Leitplanken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
