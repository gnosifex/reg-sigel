#!/usr/bin/env python3
"""Ingest einer Sigel-Meldung aus einem GitHub-Issue — in zwei Modi.

Der Weg ist dreistufig und die beiden Modi teilen ihn auf:

* ``--vorpruefung`` laeuft in der Action. Sie prueft deterministisch
  (Pflichtfelder, Feldlaengen, Syntax), ruft die gemeldete Quelle ab und
  belegt den Wortlaut, haelt die Domain gegen `curation/trusted-sources.json`
  — und **schreibt nichts**. Ergebnis ist das **Artefakt**: ein
  maschinenlesbares JSON plus menschlicher Pruefbericht.
* ``--uebernehmen`` laeuft in der taeglichen Aufnahme-Routine. Ihre
  Eingabe ist **das Artefakt, nie der Issue-Text**: Der Rohtext ist
  angreifergesteuert, das Artefakt ist geprueft und quellenverifiziert.
  Sie erzeugt den curation- und den raw-Record, **additiv-only**, und ruft
  ``build.py`` als letztes Gate. Committet wird nicht hier.

Aufruf:
    python3 tools/intake.py --vorpruefung [--body-datei X] [--ergebnis Y]
    python3 tools/intake.py --uebernehmen --artefakt A [--gruppe G]
                            [--rang N] [--dry-run] [--ergebnis Y]

Eingabe der Vorpruefung ist der Issue-Body: aus ``ISSUE_BODY`` (Action) oder
aus ``--body-datei`` (lokale Tests); Issue-Nummer aus ``ISSUE_NUMBER``.
Eingabe der Uebernahme ist ``--artefakt`` — die Datei traegt entweder das
nackte Artefakt-JSON oder den Kommentartext der Action samt Marker.
``--dry-run`` arbeitet auf einer Kopie des Repos in einem Temp-Verzeichnis
und laesst den Bestand unberuehrt.

Nur Stdlib; Netzzugriff ausschliesslich auf die gemeldete Quelle.
"""

import argparse
import datetime
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Meldeformular ---------------------------------------------------------
# Zwei Felder, mehr nicht. Alles Weitere — Referenzform, Vollbezeichnung,
# Identitaetsanker, Herausgeber, Einordnung — ermittelt die Kette selbst aus
# der verifizierten Quelle bzw. aus `curation/trusted-sources.json`. Was ein
# Fremder schreiben darf, ist damit auf das Noetigste zusammengezogen: eine
# Kurzform und die URL, an der sie steht.
# Die Schluessel sind die Labels des Issue-Formulars; GitHub schreibt sie als
# "### <Label>" in den Body. Wer ein Label im Formular aendert, aendert es hier.
FELDER = {
    "sigel": "Short form (siglum)",
    "quelle": "Source URL",
}
PFLICHTFELDER = tuple(FELDER)
LEERMARKER = ("_No response_", "_Keine Angabe_", "_No response_.")

# --- Feldlaengen -----------------------------------------------------------
# Melder-Input ist die Angriffsflaeche der Automatik. 25 Zeichen tragen jedes
# Bestandssigel (laengstes: „ISO/IEC 27002:2022“, 18) und auch beschreibende
# Formen wie „ITS Informationsregister“ (24); 200 tragen jede Herausgeber-URL.
# Ein Verstoss ist eine Ablehnung, keine Nachfrage.
FELD_LIMITS = {
    "sigel": 25,
    "quelle": 200,
}
MELDER_FLAECHE = sum(FELD_LIMITS.values())

# --- Syntax der Identitaetsanker -------------------------------------------
# Den Anker liefert nicht mehr der Melder, sondern die Aufnahme-Routine aus
# gezielten Lookups. Geprueft wird er trotzdem — auch die Routine irrt.
CELEX_BASIS = re.compile(r"^\d{5}[A-Z]{1,2}\d{4}(\(\d{2}\))?$")
CELEX_KONSOLIDIERT = re.compile(r"^0\d{4}[A-Z]{1,2}\d{4}-\d{8}$")
ANKER_TYPEN = ("celex", "jurabk", "doc_ref", "version")
ANKER_SYNTAX = {
    "jurabk": re.compile(r"^[a-z0-9_]{2,40}$"),
    "doc_ref": re.compile(r"^[\w\s./()–—:,-]{2,120}$"),
    "version": re.compile(r"^[\w.:–—\s-]{1,40}$"),
}
SIGEL_SYNTAX = re.compile(r"^[^\n\r|]{2,25}$")

# Die Domain-Allowlist steht nicht im Code, sondern in
# `curation/trusted-sources.json` — sie ist kuratierte Vertrauensentscheidung
# und wird wie die Gliederung gepflegt, nicht wie eine Konstante.

# Wie viele Fundstellen-Ausschnitte das Artefakt traegt. Die Ausschnitte
# stammen aus dem abgerufenen Quelltext, nicht aus der Meldung.
MAX_KONTEXTE = 3

UA = ("reg-sigel-intake/1.0 (+https://github.com/gnosifex/reg-sigel; "
      "Quellpruefung einer gemeldeten Kurzform)")
MAX_BYTES = 8 * 1024 * 1024
RATE_GRENZE = 10
COMMIT_MARKER = "auto-intake:"

# --- Das Artefakt ----------------------------------------------------------
# Die Routine arbeitet nie mit dem Issue, sondern ausschliesslich mit dem
# Ergebnis der Vorpruefung: Der Rohtext ist angreifergesteuert, das Artefakt
# ist syntaxgeprueft, laengenbegrenzt und an der Quelle verifiziert. Die
# Action postet es unter diesem Marker als eigenen Bot-Kommentar; nur ein
# Kommentar mit diesem Marker und dem Autor `github-actions[bot]` gilt.
ARTEFAKT_MARKER = "<!-- intake-artefakt v1 -->"
ARTEFAKT_AUTOR = "github-actions[bot]"


# --- Hilfen ----------------------------------------------------------------

def heute():
    return datetime.date.today().isoformat()


def slug(text):
    """kebab-case-ID aus einem Sigel — dieselbe Form wie die Bestands-IDs."""
    ersetzt = (text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
               .replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
               .replace("ß", "ss"))
    ersetzt = unicodedata.normalize("NFKD", ersetzt)
    ersetzt = "".join(c for c in ersetzt if not unicodedata.combining(c))
    ersetzt = re.sub(r"[^0-9A-Za-z]+", "-", ersetzt).strip("-").lower()
    return ersetzt


def body_lesen(args):
    if args.body_datei:
        with open(args.body_datei, encoding="utf-8") as f:
            return f.read()
    return os.environ.get("ISSUE_BODY", "")


def felder_lesen(body):
    """Issue-Forms-Markdown ("### Label\\n\\nWert") in ein Feld-Dict."""
    roh = {}
    label = None
    puffer = []
    for zeile in body.replace("\r\n", "\n").split("\n"):
        if zeile.startswith("### "):
            if label is not None:
                roh[label] = "\n".join(puffer).strip()
            label = zeile[4:].strip()
            puffer = []
        elif label is not None:
            puffer.append(zeile)
    if label is not None:
        roh[label] = "\n".join(puffer).strip()

    felder = {}
    for schluessel, beschriftung in FELDER.items():
        wert = roh.get(beschriftung)
        if wert is None or wert.strip() in LEERMARKER or not wert.strip():
            felder[schluessel] = None
        else:
            felder[schluessel] = re.sub(r"\s+", " ", wert.strip())
    return felder


KONFIG_DATEIEN = ("groups.json", "trusted-sources.json")


def records_lesen(curation):
    out = []
    for pfad in sorted(glob.glob(os.path.join(curation, "*.json"))):
        if os.path.basename(pfad) in KONFIG_DATEIEN:
            continue
        with open(pfad, encoding="utf-8") as f:
            out.append((pfad, json.load(f)))
    return out


def gruppen_lesen(curation):
    with open(os.path.join(curation, "groups.json"), encoding="utf-8") as f:
        return [g["id"] for g in json.load(f)["gruppen"]]


def pruefquellen_lesen(curation):
    """Die kuratierte Liste vertrauenswuerdiger Pruefquellen."""
    with open(os.path.join(curation, "trusted-sources.json"),
              encoding="utf-8") as f:
        return json.load(f)["pruefquellen"]


# --- Stufe 1: deterministische Pruefung ------------------------------------

def deterministisch_pruefen(felder):
    """Formale Maengel der Meldung — jeder davon ist eine Ablehnung."""
    fehler = []
    for schluessel in PFLICHTFELDER:
        if not felder.get(schluessel):
            fehler.append(f"Required field `{FELDER[schluessel]}` is missing.")
    if fehler:
        return fehler

    for schluessel, grenze in FELD_LIMITS.items():
        wert = felder.get(schluessel) or ""
        if len(wert) > grenze:
            fehler.append(f"Field `{FELDER[schluessel]}` is {len(wert)} "
                          f"characters long; the limit is {grenze}.")
    if fehler:
        return fehler

    sigel = felder["sigel"]
    if not SIGEL_SYNTAX.match(sigel):
        fehler.append(f"Short form `{sigel}` is not a permitted siglum form "
                      f"(2–25 characters, no line breaks, no `|`).")

    url = felder["quelle"]
    zerlegt = urllib.parse.urlsplit(url)
    if zerlegt.scheme not in ("http", "https") or not zerlegt.netloc:
        fehler.append(f"Source URL `{url}` is not an absolute http(s) URL.")
    return fehler


def anker_pruefen(typ, wert):
    """Syntax des Identitaetsankers — geliefert von der Routine, nicht vom Melder."""
    if typ not in ANKER_TYPEN:
        return (f"Identity anchor type `{typ}` is not one of the four "
                f"permitted types ({', '.join(ANKER_TYPEN)}).")
    if not wert:
        return "Identity anchor value is missing."
    if typ == "celex":
        if CELEX_KONSOLIDIERT.match(wert):
            basis = "3" + wert[1:].split("-")[0]
            return (f"`{wert}` is a consolidated CELEX number. The registry "
                    f"anchors on the base CELEX — here presumably "
                    f"`{basis}`; the consolidation belongs in "
                    f"`fassung.konsolidierung`.")
        if not CELEX_BASIS.match(wert):
            return f"`{wert}` is not a CELEX identifier (pattern `32013L0036`)."
        return None
    if not ANKER_SYNTAX[typ].match(wert):
        return (f"Identity anchor value `{wert}` does not match the syntax "
                f"of type `{typ}`.")
    return None


def zugang_bestimmen(felder, records):
    """Bekannte Kurzform, neuer Record — oder ein Fall fuer Menschen.

    Die Meldung nennt nur Kurzform und Quelle; der Kollisionscheck laeuft
    deshalb allein ueber Sigel, Aliasse und die abgeleitete Record-ID.
    Existiert die Kurzform bereits, ist die Meldung **nie** eine Aenderung,
    sondern zusaetzliche Evidenz zum bestehenden Record.
    """
    sigel = felder["sigel"]
    neue_id = slug(sigel)

    for pfad, r in records:
        if r.get("sigel") == sigel:
            return {"art": "evidenz", "ziel": r["id"], "pfad": pfad,
                    "grund": f"Siglum `{sigel}` is already held as record "
                             f"`{r['id']}`; this report counts as additional "
                             f"evidence."}
        for alias in r.get("aliasse") or []:
            if alias.get("form") == sigel:
                return {"art": "evidenz", "ziel": r["id"], "pfad": pfad,
                        "grund": f"`{sigel}` is already an alias of record "
                                 f"`{r['id']}`; this report substantiates it."}

    for pfad, r in records:
        if r.get("id") == neue_id:
            return {"art": "maintainer", "ziel": r["id"], "pfad": pfad,
                    "grund": f"The derived record ID `{neue_id}` is taken, "
                             f"but the siglum is a different one."}
    return {"art": "neu", "ziel": neue_id, "pfad": None,
            "grund": f"`{sigel}` is unknown in the registry — new record "
                     f"`{neue_id}`."}


def anker_ziel(records, typ, wert):
    """Traegt ein Record den Anker schon? Dann ist die Kurzform dort Alias."""
    for pfad, r in records:
        ident = r.get("identitaet") or {}
        if ident.get("typ") == typ and ident.get("wert") == wert:
            return pfad, r
    return None, None


# --- Stufe 2: Quellpruefung ------------------------------------------------

def abrufen(url):
    """Quelle holen; Rueckgabe (text, methode, fehler)."""
    anfrage = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/pdf,application/xhtml+xml,*/*",
        "Accept-Language": "de,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(anfrage, timeout=45) as antwort:
            rohdaten = antwort.read(MAX_BYTES + 1)
            content_type = (antwort.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as e:
        return None, None, f"HTTP {e.code} while fetching the source."
    except Exception as e:                      # Netz, DNS, TLS, Timeout
        return None, None, f"Source not retrievable: {type(e).__name__}: {e}"

    if len(rohdaten) > MAX_BYTES:
        return None, None, (f"Source larger than "
                            f"{MAX_BYTES // (1024 * 1024)} MB — not checked.")

    ist_pdf = rohdaten[:5] == b"%PDF-" or "application/pdf" in content_type
    if ist_pdf:
        if not shutil.which("pdftotext"):
            return None, None, ("PDF source, but `pdftotext` is not "
                                "available in this environment.")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(rohdaten)
            pfad = tmp.name
        try:
            lauf = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8",
                                   pfad, "-"],
                                  capture_output=True, timeout=180)
        finally:
            os.unlink(pfad)
        if lauf.returncode != 0:
            return None, None, "pdftotext could not read the source."
        return lauf.stdout.decode("utf-8", "replace"), "web fetch, pdftotext", None

    text = rohdaten.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return html.unescape(text), "web fetch", None


def normalisieren(text):
    """Weiche Trennstriche und Sonderleerzeichen weg, Weissraum vereinheitlicht.

    PDF-Extrakte und HTML streuen unsichtbare Zeichen zwischen die Buchstaben;
    ohne diesen Schritt scheitert der Wortlaut-Vergleich an Zeichen, die
    niemand sieht.
    """
    for unsichtbar in ("\u00ad", "\u200b", "\ufeff"):
        text = text.replace(unsichtbar, "")
    for leerzeichen in ("\u00a0", "\u2007", "\u202f", "\u2009"):
        text = text.replace(leerzeichen, " ")
    return re.sub(r"\s+", " ", text)


def ausschnitt_bauen(text, start, ende):
    """Ein lesbarer Kontextausschnitt um eine Fundstelle."""
    a = max(0, start - 110)
    b = min(len(text), ende + 110)
    stueck = text[a:b].strip()
    if a > 0:
        stueck = "… " + stueck.split(" ", 1)[-1]
    if b < len(text):
        stueck = stueck.rsplit(" ", 1)[0] + " …"
    return stueck


def wortlaut_finden(text, form, max_kontexte=MAX_KONTEXTE):
    """Wie oft kommt `form` wortgenau vor, und wie liest sie sich dort?

    Rueckgabe (anzahl, kontexte). Die Kontexte schneidet **das Skript** aus
    dem abgerufenen Quelltext — sie sind damit Extraktion aus einer
    verifizierten Quelle und nicht Melder-Input.
    """
    teile = [re.escape(t) for t in form.split(" ") if t]
    if not teile:
        return 0, []
    muster = re.compile(r"(?<![0-9A-Za-zÄÖÜäöüß])" + r"\s+".join(teile)
                        + r"(?![0-9A-Za-zÄÖÜäöüß])")
    anzahl = 0
    kontexte = []
    for treffer in muster.finditer(text):
        anzahl += 1
        if len(kontexte) < max_kontexte:
            kontexte.append(ausschnitt_bauen(text, treffer.start(),
                                             treffer.end()))
    return anzahl, kontexte


def quelle_pruefen(felder):
    """Die Quelle abrufen und den Wortlaut belegen — oder eben nicht."""
    text, methode, fehler = abrufen(felder["quelle"])
    if fehler:
        return {"ok": False, "fehler": fehler, "methode": None,
                "treffer": 0, "kontexte": [], "zeichen": 0}
    text = normalisieren(text)
    anzahl, kontexte = wortlaut_finden(text, felder["sigel"])
    ergebnis = {"ok": anzahl > 0, "methode": methode, "treffer": anzahl,
                "kontexte": kontexte, "zeichen": len(text), "fehler": None,
                "volltext": text}
    if not anzahl:
        ergebnis["fehler"] = (
            f"The short form `{felder['sigel']}` does not occur verbatim in "
            f"the retrieved text of the source ({len(text)} characters "
            f"checked, case-sensitive).")
    return ergebnis


def pruefquelle_fuer(url, pruefquellen):
    """Steht die Fundstelle auf der kuratierten Pruefquellen-Liste?"""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    for eintrag in pruefquellen:
        d = eintrag["domain"].lower()
        if host == d or host.endswith("." + d):
            return eintrag
    return None


# --- Einordnung ------------------------------------------------------------
# Gruppe und Rang stehen nicht mehr in der Meldung: Sie sind kuratorische
# Urteile und kommen deshalb von der Aufnahme-Routine, die sie an der Quelle
# begruendet. Geraten wird nichts — fehlt die Ansage, entscheidet der
# Maintainer.

def einordnung_pruefen(gruppe, rang, gruppen):
    """Gruppe und Rang der Routine gegen die Gliederung halten."""
    if not gruppe:
        return ("The routine assigned no group; the classification is not "
                "guessed.")
    if gruppe not in gruppen:
        return f"Group `{gruppe}` is unknown in `curation/groups.json`."
    if rang is not None and not 1 <= rang <= 7:
        return f"Rank `{rang}` is outside the range 1–7."
    return None


# --- Stufe 3: Record-Erzeugung (nur --uebernehmen) -------------------------

def json_schreiben(pfad, daten):
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


def raw_record(felder, herausgeber, quellbefund, nummer, autor):
    """Der Evidenzbeleg — Herausgeber aus der Pruefquellen-Liste, nie vom Melder."""
    return {
        "herausgeber": herausgeber,
        "quelle": felder["quelle"],
        "abgerufen": heute(),
        "methode": quellbefund["methode"],
        "meldung": {"issue": nummer, "melder": autor},
        "eintraege": [{
            "form": felder["sigel"],
            "kontext": (quellbefund.get("kontexte") or [None])[0],
            "fundstellen": [felder["quelle"]],
        }],
    }


def curation_record(felder, herausgeber, quellbefund, anker, gruppe, rang,
                    referenzform, name, nummer):
    """Der Registereintrag aus dem Artefakt plus den Zuarbeiten der Routine."""
    geprueft = {"datum": heute(), "methode": "web-abruf"}
    anker_belegt = bool(
        anker["wert"]
        and wortlaut_finden(quellbefund.get("volltext") or "",
                            anker["wert"], 1)[0])
    return {
        "id": slug(felder["sigel"]),
        "sigel": felder["sigel"],
        # Der Ingest belegt Formen aus deutschsprachigen Aufsichtsquellen;
        # eine englische Kurzform traegt der Maintainer nach.
        "sprache": "de",
        "referenzform": referenzform,
        "name": name,
        "haerte": "verkehrsueblich",
        "haerte_geprueft": {"datum": heute(), "methode": "einschaetzung"},
        "gruppe": gruppe,
        "rang": rang,
        "identitaet": {
            "typ": anker["typ"],
            "wert": anker["wert"],
            # Der Abruf belegt den Anker nur, wenn er im Quelltext steht;
            # sonst bleibt er ungeprueft statt scheinbar geprueft.
            "geprueft": dict(geprueft) if anker_belegt else None,
        },
        "fassung": {
            "stand": None,
            "konsolidierung": None,
            "text": f"Fassung nicht erhoben — Auto-Intake aus Meldung "
                    f"#{nummer} vom {heute()}",
        },
        "links": [{
            "label": f"{herausgeber} (Meldungsquelle)",
            "url": felder["quelle"],
            "geprueft": dict(geprueft),
        }],
        "aliasse": [],
        "ersetzt": [],
        "ersetzt_durch": [],
        "status": "auto-intake",
    }


def alias_ergaenzen(pfad, form, raw_id):
    """Additiv-only: nur `aliasse` darf wachsen, kein anderes Feld sich ruehren."""
    with open(pfad, encoding="utf-8") as f:
        vorher = json.load(f)
    nachher = json.loads(json.dumps(vorher))
    aliasse = nachher.setdefault("aliasse", [])
    treffer = next((a for a in aliasse if a.get("form") == form), None)
    if treffer is None:
        aliasse.append({"form": form, "sprache": "de", "evidenz": [raw_id]})
    elif raw_id not in (treffer.get("evidenz") or []):
        treffer.setdefault("evidenz", []).append(raw_id)
    else:
        return vorher, None
    ohne_a = {k: v for k, v in vorher.items() if k != "aliasse"}
    ohne_b = {k: v for k, v in nachher.items() if k != "aliasse"}
    if ohne_a != ohne_b:
        raise AssertionError("Additiv-Verletzung: ausserhalb von `aliasse` "
                             "wurde etwas geaendert.")
    return vorher, nachher


def ratenbremse(repo):
    """Wie viele auto-intake-Commits traegt der heutige Tag schon?"""
    try:
        lauf = subprocess.run(
            ["git", "-C", repo, "log", "--since", f"{heute()} 00:00:00",
             "--format=%s"],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return 0
    if lauf.returncode != 0:
        return 0
    return sum(1 for z in lauf.stdout.splitlines()
               if z.startswith(COMMIT_MARKER))


def build_laufen(repo):
    lauf = subprocess.run([sys.executable, os.path.join(repo, "tools",
                                                        "build.py")],
                          capture_output=True, text=True, cwd=repo,
                          timeout=300)
    return lauf.returncode, (lauf.stdout + lauf.stderr).strip()


def arbeitskopie(repo):
    ziel = tempfile.mkdtemp(prefix="sigel-intake-")
    for teil in ("curation", "raw", "dist", "tools"):
        quelle = os.path.join(repo, teil)
        if os.path.isdir(quelle):
            shutil.copytree(quelle, os.path.join(ziel, teil))
    return ziel


# --- Berichte --------------------------------------------------------------

def bericht(ergebnis):
    """Der Artefakt-Kommentar: Marker, Prüfbericht, Artefakt-JSON.

    Der Marker in der ersten Zeile macht den Kommentar maschinell
    auffindbar. Die Routine liest genau diesen Block — nie Titel, Body oder
    Fremdkommentare des Issues.
    """
    kopf = {
        "vorgeprueft-ok": "**Pre-check passed.**",
        "aufgenommen": "**Admitted to the registry.**",
        "abgelehnt": "**Rejected.**",
        "wartet-maintainer": "**Waiting for the maintainer.**",
    }[ergebnis["entscheidung"]]
    zeilen = [ARTEFAKT_MARKER, "", kopf, ""]
    for befund in ergebnis["befunde"]:
        zeilen.append(f"- {befund}")
    if ergebnis.get("dateien"):
        zeilen += ["", "Files written:"]
        zeilen += [f"- `{d}`" for d in ergebnis["dateien"]]
    zeilen += ["", "<details><summary>Artifact (JSON)</summary>", "",
               "```json",
               json.dumps({k: v for k, v in ergebnis.items()
                           if k != "kommentar"},
                          ensure_ascii=False, indent=2),
               "```", "", "</details>", "",
               "_Produced by `tools/intake.py`. The intake routine "
               "processes this artifact only, never the issue text._"]
    return "\n".join(zeilen)


def artefakt_lesen(pfad):
    """Das Artefakt der Vorprüfung — Eingabe von `--uebernehmen`.

    Angenommen wird der Kommentar-Text der Action ebenso wie das nackte
    JSON: Aus dem Kommentar wird der ```json-Block hinter dem Marker
    gezogen. Alles andere ist kein Artefakt und wird abgewiesen.
    """
    with open(pfad, encoding="utf-8") as f:
        roh = f.read()
    text = roh.strip()
    if not text.startswith("{"):
        if ARTEFAKT_MARKER not in roh:
            raise ValueError(f"`{pfad}` does not carry the artifact marker "
                             f"`{ARTEFAKT_MARKER}`.")
        block = re.search(r"```json\n(.*?)\n```", roh, re.S)
        if not block:
            raise ValueError(f"`{pfad}` contains no json block.")
        text = block.group(1)
    daten = json.loads(text)
    if daten.get("modus") != "vorpruefung":
        raise ValueError("The artifact does not come from `--vorpruefung`.")
    if daten.get("entscheidung") != "vorgeprueft-ok":
        raise ValueError(f"The artifact carries the decision "
                         f"`{daten.get('entscheidung')}`, not "
                         f"`vorgeprueft-ok`.")
    if not isinstance(daten.get("felder"), dict):
        raise ValueError("The artifact carries no field set.")
    return daten


def abschliessen(ergebnis, args):
    ergebnis["kommentar"] = bericht(ergebnis)
    ergebnis["schliessen"] = ergebnis["entscheidung"] in ("abgelehnt",
                                                          "aufgenommen")
    ergebnis["label"] = {
        "vorgeprueft-ok": "vorgeprueft-ok",
        "aufgenommen": None,
        "abgelehnt": "abgelehnt",
        "wartet-maintainer": "wartet-maintainer",
    }[ergebnis["entscheidung"]]
    if args.ergebnis:
        with open(args.ergebnis, "w", encoding="utf-8") as f:
            json.dump(ergebnis, f, ensure_ascii=False, indent=2)
    json.dump(ergebnis, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


# --- Ablauf ----------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modus = p.add_mutually_exclusive_group(required=True)
    modus.add_argument("--vorpruefung", action="store_true",
                       help="Prüfen ohne zu schreiben (Action)")
    modus.add_argument("--uebernehmen", action="store_true",
                       help="Records erzeugen und bauen (Routine)")
    p.add_argument("--body-datei", help="Issue-Body aus Datei statt ISSUE_BODY")
    p.add_argument("--artefakt",
                   help="Artefakt der Vorpruefung (Datei); Pflichteingabe "
                        "von --uebernehmen im Routinebetrieb")
    p.add_argument("--ergebnis", help="Ergebnis-JSON zusätzlich hierhin")
    # Zuarbeiten der Aufnahme-Routine. Sie stehen nicht im Meldeformular:
    # Die Routine leitet sie aus der verifizierten Quelle und gezielten
    # Anker-Lookups ab und verantwortet sie.
    p.add_argument("--referenzform", help="amtliche Referenzform (Routine)")
    p.add_argument("--name", help="Vollbezeichnung (Routine)")
    p.add_argument("--anker-typ", dest="anker_typ",
                   choices=ANKER_TYPEN, help="Identitätsanker-Typ (Routine)")
    p.add_argument("--anker-wert", dest="anker_wert",
                   help="Identitätsanker-Wert (Routine)")
    p.add_argument("--gruppe", help="Gruppen-ID (Routine)")
    p.add_argument("--rang", help="Rang 1–7 oder 'null' (Routine)")
    p.add_argument("--dry-run", action="store_true",
                   help="auf einer Kopie arbeiten, Bestand unberührt lassen")
    args = p.parse_args()

    nummer = os.environ.get("ISSUE_NUMBER", "0")
    autor = os.environ.get("ISSUE_AUTHOR", "unbekannt")
    artefakt = None
    if args.artefakt:
        try:
            artefakt = artefakt_lesen(args.artefakt)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"FEHLER: {e}", file=sys.stderr)
            return 1
        nummer = str(artefakt.get("issue") or nummer)
        autor = artefakt.get("melder") or autor
    ergebnis = {
        "modus": "vorpruefung" if args.vorpruefung else "uebernehmen",
        "issue": nummer,
        "melder": autor,
        "entscheidung": None,
        "sigel": None,
        "zugang": None,
        "quelle": None,
        "allowlist": None,
        "befunde": [],
        "dateien": [],
        "felder": None,
    }

    vorgabe_rang = None
    if args.rang not in (None, "", "null", "keiner"):
        if not str(args.rang).isdigit() or not 1 <= int(args.rang) <= 7:
            ergebnis["entscheidung"] = "wartet-maintainer"
            ergebnis["befunde"].append(f"Rank input `{args.rang}` is not "
                                       f"permitted (1–7 or `null`).")
            return abschliessen(ergebnis, args)
        vorgabe_rang = int(args.rang)

    if artefakt is not None:
        felder = {k: artefakt["felder"].get(k) for k in FELDER}
    else:
        felder = felder_lesen(body_lesen(args))
    ergebnis["sigel"] = felder.get("sigel")
    ergebnis["felder"] = felder

    # Stufe 1 — Form der Meldung
    fehler = deterministisch_pruefen(felder)
    if fehler:
        ergebnis["entscheidung"] = "abgelehnt"
        ergebnis["befunde"] = fehler
        ergebnis["befunde"].append(
            "The registry admits on source evidence: a report is checked only "
            "when it is complete, syntactically clean and names the place of "
            "occurrence.")
        return abschliessen(ergebnis, args)

    repo = arbeitskopie(REPO) if (args.uebernehmen and args.dry_run) else REPO
    curation = os.path.join(repo, "curation")
    records = records_lesen(curation)
    gruppen = gruppen_lesen(curation)
    pruefquellen = pruefquellen_lesen(curation)

    zugang = zugang_bestimmen(felder, records)
    ergebnis["zugang"] = zugang["art"]
    ergebnis["befunde"].append(zugang["grund"])
    if zugang["art"] == "maintainer":
        ergebnis["entscheidung"] = "wartet-maintainer"
        return abschliessen(ergebnis, args)

    # Stufe 2 — die Quelle belegt den Wortlaut oder nichts gilt
    quellbefund = quelle_pruefen(felder)
    ergebnis["quelle"] = {k: quellbefund[k] for k in
                          ("ok", "methode", "treffer", "kontexte", "zeichen",
                           "fehler")}
    if not quellbefund["ok"]:
        ergebnis["entscheidung"] = "abgelehnt"
        ergebnis["befunde"].append(quellbefund["fehler"])
        return abschliessen(ergebnis, args)
    ergebnis["befunde"].append(
        f"Source fetched ({quellbefund['methode']}, "
        f"{quellbefund['zeichen']} characters); `{felder['sigel']}` occurs "
        f"{quellbefund['treffer']}× verbatim. First occurrence: "
        f"`{quellbefund['kontexte'][0]}`")

    # Stufe 3 — Herkunft entscheidet ueber Automatik
    quelle_eintrag = pruefquelle_fuer(felder["quelle"], pruefquellen)
    ergebnis["pruefquelle"] = quelle_eintrag
    ergebnis["allowlist"] = quelle_eintrag is not None
    if quelle_eintrag is None:
        ergebnis["entscheidung"] = "abgelehnt"
        host = urllib.parse.urlsplit(felder["quelle"]).hostname
        ergebnis["befunde"].append(
            f"`{host}` is not listed in `curation/trusted-sources.json`. A "
            f"short form counts as substantiated only through an approved "
            f"trusted source, so this report is rejected. To have the domain "
            f"considered, propose it with the `trusted-source-proposal` form; "
            f"the trust layer is decided by the maintainer alone.")
        return abschliessen(ergebnis, args)
    ergebnis["befunde"].append(
        f"Source is a curated trusted source: `{quelle_eintrag['domain']}` "
        f"({quelle_eintrag['herausgeber']}, {quelle_eintrag['typ']}).")

    if args.vorpruefung:
        ergebnis["entscheidung"] = "vorgeprueft-ok"
        ergebnis["befunde"].append(
            "The daily intake routine will enter the record; the pre-check "
            "itself wrote nothing.")
        return abschliessen(ergebnis, args)

    # --- ab hier nur --uebernehmen ---
    # Die Zuarbeiten der Routine kommen erst hier ins Spiel — die Action
    # kennt sie nicht und braucht sie nicht.
    gruppe, rang = args.gruppe, vorgabe_rang
    anker = {"typ": args.anker_typ, "wert": args.anker_wert}
    if zugang["art"] == "neu":
        maengel = [m for m in (
            anker_pruefen(anker["typ"], anker["wert"]),
            einordnung_pruefen(gruppe, rang, gruppen),
            None if args.referenzform else
            "The routine determined no official reference form.",
            None if args.name else
            "The routine determined no full title.",
        ) if m]
        if maengel:
            ergebnis["entscheidung"] = "wartet-maintainer"
            ergebnis["befunde"] += maengel
            ergebnis["befunde"].append(
                "A new record needs an anchor, a classification and a title. "
                "What the routine cannot establish reliably at the source it "
                "does not guess — the maintainer decides it.")
            return abschliessen(ergebnis, args)
        # Traegt ein Bestandsrecord denselben Anker, ist die gemeldete
        # Kurzform dort eine weitere Schreibform, kein neues Dokument.
        alias_pfad, alias_record = anker_ziel(records, anker["typ"],
                                              anker["wert"])
        if alias_record is not None:
            zugang = {"art": "alias", "ziel": alias_record["id"],
                      "pfad": alias_pfad,
                      "grund": f"Anchor `{anker['typ']}:{anker['wert']}` "
                               f"belongs to record `{alias_record['id']}`; "
                               f"`{felder['sigel']}` becomes an alias there."}
            ergebnis["zugang"] = "alias"
            ergebnis["befunde"].append(zugang["grund"])
        else:
            ergebnis["befunde"].append(
                f"Classification by the routine: group `{gruppe}`, rank "
                f"{'—' if rang is None else rang}, anchor "
                f"`{anker['typ']}:{anker['wert']}`.")

    getan = ratenbremse(REPO)
    if getan >= RATE_GRENZE:
        ergebnis["entscheidung"] = "wartet-maintainer"
        ergebnis["befunde"].append(
            f"Rate limit: {getan} auto-intake commits already exist today "
            f"(limit {RATE_GRENZE}).")
        return abschliessen(ergebnis, args)

    raw_id = f"{heute()}-intake-{nummer}-{slug(felder['sigel'])}"
    raw_pfad = os.path.join(repo, "raw", raw_id + ".json")
    if os.path.exists(raw_pfad):
        ergebnis["entscheidung"] = "wartet-maintainer"
        ergebnis["befunde"].append(
            f"`raw/{raw_id}.json` already exists — this report was already "
            f"processed today.")
        return abschliessen(ergebnis, args)

    # Rueckabwicklung vorbereiten: Originalzustaende merken
    protokoll = []

    def merken(pfad):
        alt = None
        if os.path.exists(pfad):
            with open(pfad, "rb") as f:
                alt = f.read()
        protokoll.append((pfad, alt))

    for name in ("sigel.json", "SIGEL.md"):
        merken(os.path.join(repo, "dist", name))

    try:
        merken(raw_pfad)
        json_schreiben(raw_pfad, raw_record(
            felder, quelle_eintrag["herausgeber"], quellbefund, nummer,
            autor))
        ergebnis["dateien"].append(os.path.relpath(raw_pfad, repo))

        if zugang["art"] == "neu":
            neu = curation_record(
                felder, quelle_eintrag["herausgeber"], quellbefund, anker,
                gruppe, rang, args.referenzform, args.name, nummer)
            kur_pfad = os.path.join(curation, zugang["ziel"] + ".json")
            merken(kur_pfad)
            json_schreiben(kur_pfad, neu)
            ergebnis["dateien"].append(os.path.relpath(kur_pfad, repo))
        elif zugang["art"] == "alias":
            ziel = os.path.join(curation, zugang["ziel"] + ".json")
            merken(ziel)
            _, nachher = alias_ergaenzen(ziel, felder["sigel"], raw_id)
            if nachher is not None:
                json_schreiben(ziel, nachher)
                ergebnis["dateien"].append(os.path.relpath(ziel, repo))
        # "evidenz": der raw-Record allein genuegt — die Statistik des Builds
        # zaehlt ihn dem bestehenden Record von selbst zu.

        code, ausgabe = build_laufen(repo)
        if code != 0:
            raise RuntimeError(f"build.py failed (exit {code}):\n{ausgabe}")
        ergebnis["build"] = ausgabe.splitlines()[-1] if ausgabe else ""
        for name in ("sigel.json", "SIGEL.md"):
            ergebnis["dateien"].append(f"dist/{name}")
    except Exception as e:
        for pfad, alt in reversed(protokoll):
            if alt is None:
                if os.path.exists(pfad):
                    os.unlink(pfad)
            else:
                with open(pfad, "wb") as f:
                    f.write(alt)
        ergebnis["entscheidung"] = "wartet-maintainer"
        ergebnis["dateien"] = []
        ergebnis["befunde"].append(
            f"Intake rolled back, the registry is unchanged: {e}")
        if args.dry_run and repo != REPO:
            shutil.rmtree(repo, ignore_errors=True)
        return abschliessen(ergebnis, args)

    ergebnis["entscheidung"] = "aufgenommen"
    ergebnis["commit_betreff"] = (f"{COMMIT_MARKER} {felder['sigel']} "
                                  f"(#{nummer})")
    if args.dry_run:
        ergebnis["befunde"].append(
            f"Dry run on a copy ({repo}); the registry is untouched.")
        shutil.rmtree(repo, ignore_errors=True)
    else:
        ergebnis["befunde"].append(
            "Records written and `build.py` green — the routine commits the "
            "result.")
    return abschliessen(ergebnis, args)


if __name__ == "__main__":
    sys.exit(main())
