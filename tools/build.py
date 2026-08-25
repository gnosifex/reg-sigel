#!/usr/bin/env python3
"""Deterministischer Build: curation/ + raw/ -> dist/sigel.json und dist/SIGEL.md

Kein Netzzugriff. Validierungsfehler beenden den Lauf mit Exit-Code 1;
Warnungen (offene Identität) sind kein Fehler.

Aufruf:
    python3 tools/build.py
"""

import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATION = os.path.join(REPO, "curation")
GRUPPEN_DATEI = os.path.join(CURATION, "groups.json")
PRUEFQUELLEN_DATEI = os.path.join(CURATION, "trusted-sources.json")
# Konfigurationsdateien der Kurationsschicht — sie tragen keine Sigel und
# werden deshalb nie als Record gelesen.
KONFIG_DATEIEN = (GRUPPEN_DATEI, PRUEFQUELLEN_DATEI)
RAW = os.path.join(REPO, "raw")
DIST = os.path.join(REPO, "dist")
DOCS = os.path.join(REPO, "docs")

STAND = "2026-08-25"
QUELLE_SEED = "kuratierter Seed des Betreibers, Stand 2026-08-24"
REPO_URL = "https://github.com/gnosifex/reg-sigel"
LIZENZ_URL = "https://creativecommons.org/licenses/by/4.0/"
KERNAUSSAGE = ("Das Register ordnet seine Quellen nach absteigender "
               "regulatorischer Verbindlichkeit — von unmittelbar geltendem "
               "EU-Recht über europäische und nationale Aufsichtsvorgaben bis "
               "zu freiwilligen Standards.")

PFLICHTFELDER = ("id", "sigel", "sprache", "referenzform", "name",
                 "haerte", "haerte_geprueft",
                 "gruppe", "rang", "identitaet", "fassung",
                 "links", "aliasse", "ersetzt", "ersetzt_durch", "status")
# Jede Schreibform traegt ihre Sprache: die kanonische in `sprache` des
# Records, jede Nebenform in `sprache` ihres Alias-Eintrags. Deutsche
# und englische Kurzform derselben Quelle sind damit unterscheidbar,
# ohne dass die Form selbst geraten werden muss.
SPRACHEN = ("de", "en")
# Verbindlichkeits-Rang: 1 bindendes
# Recht der eigenen Rechtsordnung … 7 rollende Webkommunikation; null ist
# die "—"-Zeile der Hierarchie (Standards ohne Rechtsbindung).
RANG_WERTE = (1, 2, 3, 4, 5, 6, 7, None)
IDENT_TYPEN = ("celex", "jurabk", "doc_ref", "version", "offen")
FASSUNGS_FELDER = ("stand", "konsolidierung", "text")
PRUEF_METHODEN = ("web-abruf", "konstruiert", "seed-doksigel",
                  "spiegel-provenienz")
# Der Haertegrad wird eingeschaetzt, nicht abgerufen — eigener Methodenraum,
# damit ein Link nie „einschaetzung" fuehren kann und umgekehrt.
# Gruppen fuehren beide Sprachfassungen; die Site baut daraus ihre Seiten.
GRUPPEN_FELDER = ("id", "titel", "aussage", "titel_en", "aussage_en")
HAERTE_METHODEN = ("einschaetzung",)
HAERTE_STUFEN = ("amtlich", "herausgeberueblich", "verkehrsueblich",
                 "hausform")
ISO_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Prüfquellen sind reine Domains — kein Schema, kein Pfad, kein Port.
PRUEFQUELLEN_FELDER = ("domain", "herausgeber", "typ", "aufgenommen",
                       "freigabe")
DOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?"
                    r"(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")

# Abgeleitete Links entstehen erst zur Ausgabezeit und tragen deshalb kein
# Pruefdatum: Sie sind aus der Fassung gerechnet, nicht abgerufen.
ABGELEITET_URL = ("https://eur-lex.europa.eu/legal-content/DE/TXT/"
                  "?uri=CELEX:{}")
ABGELEITET_LABEL = "EUR-Lex DE (konsolidiert)"
ABGELEITET_GEPRUEFT = {"datum": None, "methode": "abgeleitet-aus-fassung"}


def geprueft_pruefen(datei, wo, wert, fehler, methoden=PRUEF_METHODEN,
                     pflicht=False):
    """`geprueft` ist entweder null oder {datum: ISO, methode: bekannt}."""
    if wert is None:
        if pflicht:
            fehler.append(f"{datei}: {wo}.geprueft fehlt")
        return
    if not isinstance(wert, dict):
        fehler.append(f"{datei}: {wo}.geprueft ist kein Objekt")
        return
    unbekannt = set(wert) - {"datum", "methode"}
    if unbekannt:
        fehler.append(f"{datei}: {wo}.geprueft hat unbekannte Felder "
                      f"{sorted(unbekannt)}")
    datum = wert.get("datum")
    if not isinstance(datum, str) or not ISO_DATUM.match(datum):
        fehler.append(f"{datei}: {wo}.geprueft.datum '{datum}' ist kein "
                      f"ISO-Datum")
    if wert.get("methode") not in methoden:
        fehler.append(f"{datei}: {wo}.geprueft.methode "
                      f"'{wert.get('methode')}' unzulaessig")


def records_lesen():
    out = []
    konfig = {os.path.abspath(p) for p in KONFIG_DATEIEN}
    for pfad in sorted(glob.glob(os.path.join(CURATION, "*.json"))):
        if os.path.abspath(pfad) in konfig:
            continue
        with open(pfad, encoding="utf-8") as f:
            out.append((os.path.basename(pfad), json.load(f)))
    return out


def gruppen_lesen():
    """Gliederung des Registers; die Reihenfolge der Datei ist die Ausgabe."""
    with open(GRUPPEN_DATEI, encoding="utf-8") as f:
        return json.load(f)["gruppen"]


def gruppen_pruefen(gruppen, fehler):
    """Jede Gruppe traegt beide Sprachfassungen — die Site baut aus ihnen."""
    for i, g in enumerate(gruppen):
        for feld in GRUPPEN_FELDER:
            if not g.get(feld):
                fehler.append(f"groups.json: Gruppe {g.get('id') or i} "
                              f"ohne '{feld}'")
        unbekannt = set(g) - set(GRUPPEN_FELDER)
        if unbekannt:
            fehler.append(f"groups.json: Gruppe {g.get('id') or i} hat "
                          f"unbekannte Felder {sorted(unbekannt)}")


def pruefquellen_lesen():
    """Kuratierte Prüfquellen — Vertrauensliste des Intake, keine Records."""
    with open(PRUEFQUELLEN_DATEI, encoding="utf-8") as f:
        return json.load(f)["pruefquellen"]


def pruefquellen_pruefen(pruefquellen, fehler):
    """Pflichtfelder und Eindeutigkeit — der Intake haengt an dieser Liste."""
    gesehen = {}
    for i, q in enumerate(pruefquellen):
        for feld in PRUEFQUELLEN_FELDER:
            if not q.get(feld):
                fehler.append(f"trusted-sources.json: Eintrag {i} ohne '{feld}'")
        unbekannt = set(q) - set(PRUEFQUELLEN_FELDER)
        if unbekannt:
            fehler.append(f"trusted-sources.json: Eintrag {i} hat unbekannte "
                          f"Felder {sorted(unbekannt)}")
        domain = (q.get("domain") or "").lower()
        if not domain:
            continue
        if domain != q.get("domain"):
            fehler.append(f"trusted-sources.json: Domain '{q['domain']}' ist "
                          f"nicht kleingeschrieben")
        if not DOMAIN.match(domain):
            fehler.append(f"trusted-sources.json: '{domain}' ist keine "
                          f"Domain (kein Schema, kein Pfad)")
        if domain in gesehen:
            fehler.append(f"trusted-sources.json: Domain '{domain}' doppelt "
                          f"(auch Eintrag {gesehen[domain]})")
        else:
            gesehen[domain] = i
        datum = q.get("aufgenommen")
        if datum is not None and not (isinstance(datum, str)
                                      and ISO_DATUM.match(str(datum))):
            fehler.append(f"trusted-sources.json: aufgenommen '{datum}' ist "
                          f"kein ISO-Datum")


def raw_ids():
    ids = set()
    for pfad in glob.glob(os.path.join(RAW, "*")):
        name = os.path.basename(pfad)
        ids.add(os.path.splitext(name)[0])
    return ids


def evidenz_zaehlen():
    """Wie oft ist jede Schreibform belegt? Zaehlwert ist die Fundstelle.

    Gezaehlt wird ueber alle raw-Dateien hinweg nach Form, nicht nach
    Record: Die Evidenzschicht weiss nichts von Kuration, und dieselbe Form
    kann in mehreren Erhebungen auftauchen. Die Zuordnung zu einem Record
    faellt erst in `statistik_fuer`.
    """
    je_form = {}
    je_form_hrsg = {}
    gesamt = 0
    for pfad in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        with open(pfad, encoding="utf-8") as f:
            daten = json.load(f)
        hrsg = daten.get("herausgeber")
        for eintrag in daten.get("eintraege") or []:
            form = eintrag.get("form")
            anzahl = len(eintrag.get("fundstellen") or [])
            gesamt += anzahl
            if form:
                je_form[form] = je_form.get(form, 0) + anzahl
                if hrsg:
                    je_form_hrsg.setdefault(form, set()).add(hrsg)
    return je_form, je_form_hrsg, gesamt


def statistik_fuer(record, je_form):
    """Belegzahlen der Formen eines Records — nur Formen mit Evidenz.

    Ein leeres Objekt heisst „keine Fundstelle", nicht „nicht erhoben":
    Der Bestand ist erst punktuell mit Evidenz unterlegt.
    """
    formen = [record["sigel"]] + [a["form"] for a in record.get("aliasse", [])]
    return {form: je_form[form] for form in sorted(set(formen))
            if je_form.get(form)}


def belegt_fuer(record, je_form_hrsg):
    """Herausgeber, in deren Publikationen eine Form des Records belegt ist."""
    formen = [record["sigel"]] + [a["form"] for a in record.get("aliasse", [])]
    hrsg = set()
    for form in formen:
        hrsg |= je_form_hrsg.get(form, set())
    return sorted(hrsg)


def validieren(records, bekannte_raw, gruppen):
    fehler, warnungen = [], []
    ids, sigel_map = {}, {}

    gruppen_ids = []
    for i, g in enumerate(gruppen):
        for feld in ("id", "titel", "aussage"):
            if not g.get(feld):
                fehler.append(f"groups.json: Gruppe {i} ohne '{feld}'")
        gid = g.get("id")
        if gid in gruppen_ids:
            fehler.append(f"groups.json: Gruppen-ID '{gid}' doppelt")
        elif gid:
            gruppen_ids.append(gid)
    belegt = {gid: 0 for gid in gruppen_ids}

    for datei, r in records:
        for feld in PFLICHTFELDER:
            if feld not in r:
                fehler.append(f"{datei}: Feld '{feld}' fehlt")
        if "id" not in r or "sigel" not in r:
            continue
        if r["id"] in ids:
            fehler.append(f"{datei}: id '{r['id']}' doppelt "
                          f"(auch in {ids[r['id']]})")
        else:
            ids[r["id"]] = datei
        if r["sigel"] in sigel_map:
            fehler.append(f"{datei}: sigel '{r['sigel']}' doppelt "
                          f"(auch in {sigel_map[r['sigel']]})")
        else:
            sigel_map[r["sigel"]] = datei
        if os.path.splitext(datei)[0] != r["id"]:
            fehler.append(f"{datei}: Dateiname passt nicht zu id '{r['id']}'")

        if r.get("sprache") not in SPRACHEN:
            fehler.append(f"{datei}: sprache '{r.get('sprache')}' unzulaessig "
                          f"(erlaubt: {', '.join(SPRACHEN)})")

        # Haertegrad: Pflichtfeld, geschlossene Werteliste, eigener Pruefstand
        haerte = r.get("haerte")
        if haerte not in HAERTE_STUFEN:
            fehler.append(f"{datei}: haerte '{haerte}' unzulaessig "
                          f"(erlaubt: {', '.join(HAERTE_STUFEN)})")
        geprueft_pruefen(datei, "haerte", r.get("haerte_geprueft"), fehler,
                         methoden=HAERTE_METHODEN, pflicht=True)

        if r.get("rang") not in RANG_WERTE:
            fehler.append(f"{datei}: rang '{r.get('rang')}' unzulaessig "
                          f"(1-7 oder null)")

        # Gliederung: jeder Record haengt an genau einer bekannten Gruppe
        gruppe = r.get("gruppe")
        if gruppe not in belegt:
            fehler.append(f"{datei}: gruppe '{gruppe}' ist in groups.json "
                          f"nicht definiert")
        else:
            belegt[gruppe] += 1

        ident = r.get("identitaet") or {}
        typ = ident.get("typ")
        if typ not in IDENT_TYPEN:
            fehler.append(f"{datei}: identitaet.typ '{typ}' unzulaessig")
        elif typ == "offen":
            warnungen.append(f"{r['id']}: identitaet offen "
                             f"(kein Identitaetsanker)")
        elif not ident.get("wert"):
            fehler.append(f"{datei}: identitaet.typ '{typ}' ohne wert")
        geprueft_pruefen(datei, "identitaet", ident.get("geprueft"), fehler)

        # Fassung ist typisiert: Freitext, Konsolidierung, Stichdatum getrennt
        fassung = r.get("fassung")
        if not isinstance(fassung, dict):
            fehler.append(f"{datei}: fassung ist kein Objekt "
                          f"(Schema v1 nicht migriert?)")
        else:
            unbekannt = set(fassung) - set(FASSUNGS_FELDER)
            if unbekannt:
                fehler.append(f"{datei}: fassung hat unbekannte Felder "
                              f"{sorted(unbekannt)}")
            for feld in FASSUNGS_FELDER:
                if feld not in fassung:
                    fehler.append(f"{datei}: fassung.{feld} fehlt")
            if not fassung.get("text"):
                fehler.append(f"{datei}: fassung.text ist leer")
            stand = fassung.get("stand")
            if stand is not None and not (isinstance(stand, str)
                                          and ISO_DATUM.match(stand)):
                fehler.append(f"{datei}: fassung.stand '{stand}' ist kein "
                              f"ISO-Datum")
            kons = fassung.get("konsolidierung")
            if kons is not None and not isinstance(kons, str):
                fehler.append(f"{datei}: fassung.konsolidierung ist kein Text")

        for i, link in enumerate(r.get("links") or []):
            if not link.get("label") or not link.get("url"):
                fehler.append(f"{datei}: Link {i} ohne label oder url")
            geprueft_pruefen(datei, f"links[{i}]", link.get("geprueft"), fehler)

    # Eine leere Gruppe ist eine Gliederung ohne Gegenstand
    for gid, anzahl in belegt.items():
        if anzahl == 0:
            fehler.append(f"groups.json: Gruppe '{gid}' ist leer")

    # Rechtsnachfolge muss auf existierende Records aufloesen
    for datei, r in records:
        for feld in ("ersetzt", "ersetzt_durch"):
            werte = r.get(feld)
            if not isinstance(werte, list):
                fehler.append(f"{datei}: {feld} ist keine Liste")
                continue
            for ziel in werte:
                if ziel == r.get("id"):
                    fehler.append(f"{datei}: {feld} verweist auf sich selbst")
                elif ziel not in ids:
                    fehler.append(f"{datei}: {feld} verweist auf unbekannte "
                                  f"Record-ID '{ziel}'")

    # Alias-Formen duerfen nicht mit dem Sigel eines anderen Records kollidieren
    for datei, r in records:
        for alias in r.get("aliasse", []):
            form = alias.get("form")
            if not form:
                fehler.append(f"{datei}: Alias ohne 'form'")
                continue
            besitzer = sigel_map.get(form)
            if besitzer and besitzer != datei:
                fehler.append(f"{datei}: Alias '{form}' kollidiert mit dem "
                              f"Sigel in {besitzer}")
            if form == r.get("sigel"):
                fehler.append(f"{datei}: Alias '{form}' ist das eigene Sigel")
            if alias.get("sprache") not in SPRACHEN:
                fehler.append(f"{datei}: Alias '{form}' hat sprache "
                              f"'{alias.get('sprache')}' (erlaubt: "
                              f"{', '.join(SPRACHEN)})")
            evidenz = alias.get("evidenz") or []
            if not evidenz:
                warnungen.append(f"{r.get('id')}: Alias '{form}' ohne Evidenz")
            for ev in evidenz:
                if ev not in bekannte_raw:
                    fehler.append(f"{datei}: Alias '{form}' verweist auf "
                                  f"unbekannte Evidenz '{ev}'")
    return fehler, warnungen


def mit_abgeleiteten_links(record):
    """Ausgabefassung eines Records: kuratierte Links plus abgeleiteter Link.

    Ein CELEX-Record mit konsolidierter Fassung bekommt den EUR-Lex-Link auf
    genau diese Fassung dazugerechnet. Das geschieht erst hier, in der
    Ausgabe — `curation/` bleibt Handpflege und traegt keinen generierten
    Link. Ohne `konsolidierung` entsteht keiner: Die Basis-CELEX-Seite zeigt
    die Ursprungsfassung, nicht die registrierte.
    """
    ident = record.get("identitaet") or {}
    kons = (record.get("fassung") or {}).get("konsolidierung")
    if ident.get("typ") != "celex" or not kons:
        return record

    url = ABGELEITET_URL.format(kons)
    vorhandene = {link.get("url") for link in record.get("links") or []}
    if url in vorhandene:
        return record

    kopie = dict(record)
    kopie["links"] = list(record.get("links") or []) + [{
        "label": ABGELEITET_LABEL,
        "url": url,
        "geprueft": dict(ABGELEITET_GEPRUEFT),
    }]
    return kopie


def md_zelle(text):
    return str(text).replace("|", "\\|")


def md_identitaet(ident):
    """Identitaetsanker als `typ:wert`; ohne Anker nur der Typ."""
    if ident["typ"] == "offen" or not ident.get("wert"):
        return ident["typ"]
    return f"{ident['typ']}:{ident['wert']}"


def md_links(links):
    """Links als Markdown-Links, Label als Linktext, mehrere mit ` · `."""
    teile = []
    for link in links:
        label = md_zelle(link["label"]).replace("[", "\\[").replace("]", "\\]")
        teile.append(f"[{label}]({link['url']})")
    return " · ".join(teile)


def md_zeile(r):
    aliasse = ", ".join(a["form"] for a in r.get("aliasse", [])) or "—"
    fassung = r["fassung"]["text"]
    rang = "—" if r.get("rang") is None else str(r["rang"])
    return (f"| {md_zelle(r['sigel'])} | {md_zelle(r['referenzform'])} | "
            f"{md_zelle(r['name'])} | "
            f"{rang} | {md_zelle(r['haerte'])} | "
            f"{md_zelle(md_identitaet(r['identitaet']))} | "
            f"{md_zelle(fassung)} | "
            f"{md_links(r.get('links', []))} | "
            f"{md_zelle(aliasse)} | "
            f"{md_zelle(', '.join(r.get('belegt_durch') or []) or '—')} |")


def md_schreiben(records, gruppen):
    zeilen = [
        "# Sigel-Register",
        "",
        f"Generiert von `tools/build.py` — Stand {STAND}, "
        f"Seed-Quelle: {QUELLE_SEED}. Nicht von Hand editieren; "
        "Änderungen gehören nach `curation/`.",
        "",
        KERNAUSSAGE,
    ]
    for g in gruppen:
        zeilen += [
            "",
            f"## {g['titel']}",
            "",
            g["aussage"],
            "",
            "| Sigel | Amtliche Referenz | Vollbezeichnung | Rang | Härte "
            "| Identität | Fassung | Quelle | Aliasse | Belegt durch |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        zeilen += [md_zeile(r) for r in records if r["gruppe"] == g["id"]]
    zeilen.append("")
    return "\n".join(zeilen)


# --- Statische Seite ------------------------------------------------------
# `docs/index.html` (englisch) und `docs/de.html` (deutsch) sind dieselbe
# Tabelle wie `dist/SIGEL.md`, nur lesbar ohne Markdown-Renderer: je eine
# Datei, kein Skript, kein externes Asset — was der Browser laedt, steht
# vollstaendig in dieser Datei; der Umschalter ist ein schlichter Link.
# Deterministisch wie jede andere Build-Ausgabe. Sprachabhaengig ist allein
# das Geruest — Titel, Kernaussage, Spaltenkoepfe, Gruppentexte, Fusszeile
# und die Anzeigelabels des Haertegrads; der Registerinhalt bleibt in beiden
# Fassungen identisch, in der Sprache seiner Quellen.

SEITEN = {
    "en": {
        "datei": "index.html",
        "lang": "en",
        "titel": "Source Siglum Registry",
        "kernaussage": (
            "The registry orders its sources by decreasing regulatory "
            "bindingness — from directly applicable EU law through European "
            "and national supervisory instruments to voluntary standards."),
        "sprachhinweis": (
            "Record content is given in the language of the sources it "
            "describes, which for this registry is largely German; the field "
            "names of the machine-readable data are German as well and are "
            "explained in the README."),
        "meta": ("As of {stand} — {anzahl} entries, {fundstellen} "
                 "attestations. Curated and growing; the registry makes no "
                 "promise of completeness."),
        "spalten": ("Siglum", "Official reference", "Full title", "Rank",
                    "Hardness", "Identity", "Version", "Source", "Aliases",
                    "Attested by"),
        "haerte": {"amtlich": "official",
                   "herausgeberueblich": "publisher usage",
                   "verkehrsueblich": "common usage",
                   "hausform": "house form"},
        "gruppe_titel": "titel_en",
        "gruppe_aussage": "aussage_en",
        "wechsel_ziel": "de.html",
        "wechsel_lang": "de",
        "wechsel_text": "Deutsch",
        "fuss_erzeugt": ("As of {stand}. Generated by <code>tools/build.py"
                         "</code> from <code>curation/</code> and "
                         "<code>raw/</code> — do not edit by hand."),
        "fuss_lizenz": ('Licensed <a href="{lizenz}">CC BY 4.0</a>, '
                        'attribution "gnosifex"; reuse, redistribution and '
                        'mirroring are welcome under that licence. The cited '
                        'legal texts and standards themselves are not covered '
                        'by it. Source code and data: '
                        '<a href="{repo}">{repo}</a>.'),
    },
    "de": {
        "datei": "de.html",
        "lang": "de",
        "titel": "Register der Quellensigel",
        "kernaussage": KERNAUSSAGE,
        "sprachhinweis": (
            "Die Inhalte der Records stehen in der Sprache der Quellen, die "
            "sie beschreiben — für dieses Register überwiegend Deutsch; die "
            "Feldnamen der maschinenlesbaren Daten sind ebenfalls deutsch und "
            "werden im README erläutert."),
        "meta": ("Stand {stand} — {anzahl} Einträge, {fundstellen} "
                 "Fundstellen. Kuratiert und wachsend; das Register erhebt "
                 "keinen Anspruch auf Vollständigkeit."),
        "spalten": ("Sigel", "Amtliche Referenz", "Vollbezeichnung", "Rang",
                    "Härte", "Identität", "Fassung", "Quelle", "Aliasse",
                    "Belegt durch"),
        "haerte": {"amtlich": "amtlich",
                   "herausgeberueblich": "herausgeberüblich",
                   "verkehrsueblich": "verkehrsüblich",
                   "hausform": "Hausform"},
        "gruppe_titel": "titel",
        "gruppe_aussage": "aussage",
        "wechsel_ziel": "index.html",
        "wechsel_lang": "en",
        "wechsel_text": "English",
        "fuss_erzeugt": ("Stand {stand}. Erzeugt von <code>tools/build.py"
                         "</code> aus <code>curation/</code> und "
                         "<code>raw/</code> — nicht von Hand editieren."),
        "fuss_lizenz": ('Lizenziert unter <a href="{lizenz}">CC BY 4.0</a>, '
                        'Namensnennung „gnosifex“; Weiterverwendung, '
                        'Weitergabe und Spiegelung sind unter dieser Lizenz '
                        'willkommen. Die zitierten Rechtstexte und Standards '
                        'selbst sind davon nicht erfasst. Quellcode und '
                        'Daten: <a href="{repo}">{repo}</a>.'),
    },
}

CSS = """\
:root { color-scheme: light dark;
  --grund: #ffffff; --text: #16191d; --leise: #5b6470;
  --linie: #d8dde3; --kopf: #f2f4f7; --link: #1a4fa0; }
@media (prefers-color-scheme: dark) { :root {
  --grund: #14171b; --text: #e6e9ed; --leise: #9aa4b1;
  --linie: #2c333c; --kopf: #1c2127; --link: #8ab4ff; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.25rem 4rem; background: var(--grund);
  color: var(--text); line-height: 1.55;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif; }
main { max-width: 76rem; margin: 0 auto; }
h1 { font-size: 1.9rem; margin: 0 0 .5rem; letter-spacing: -.01em; }
h2 { font-size: 1.25rem; margin: 2.75rem 0 .35rem;
  padding-top: 1.25rem; border-top: 1px solid var(--linie); }
p { margin: 0 0 1rem; max-width: 52rem; }
.kern { font-size: 1.05rem; }
.leise { color: var(--leise); font-size: .9rem; }
.wechsel { text-align: right; font-size: .9rem; margin: 0 0 .35rem;
  max-width: none; }
a { color: var(--link); }
.rahmen { overflow-x: auto; border: 1px solid var(--linie);
  border-radius: 6px; margin: 0 0 1rem; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; }
th, td { padding: .45rem .6rem; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--linie); white-space: nowrap; }
th { background: var(--kopf); font-weight: 600; position: sticky; top: 0; }
tr:last-child td { border-bottom: 0; }
td.weit { white-space: normal; min-width: 18rem; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .95em; }
footer { margin-top: 3rem; padding-top: 1.25rem;
  border-top: 1px solid var(--linie); color: var(--leise); font-size: .9rem; }
"""

# Spalten, deren Inhalt Fliesstext ist und deshalb umbrechen darf.
WEITE_SPALTEN = (2, 6, 8)


def h(text):
    """HTML-Escape — die Daten sind kuratiert, die Ausgabe bleibt dicht."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def html_links(links):
    if not links:
        return "—"
    return " · ".join(f'<a href="{h(l["url"])}">{h(l["label"])}</a>'
                      for l in links)


def html_zeile(r, seite):
    aliasse = ", ".join(a["form"] for a in r.get("aliasse", [])) or "—"
    zellen = [
        h(r["sigel"]), h(r["referenzform"]), h(r["name"]),
        "—" if r.get("rang") is None else str(r["rang"]),
        h(seite["haerte"][r["haerte"]]), h(md_identitaet(r["identitaet"])),
        h(r["fassung"]["text"]), html_links(r.get("links", [])),
        h(aliasse), h(", ".join(r.get("belegt_durch") or []) or "—"),
    ]
    tds = [f'<td{" class=\"weit\"" if i in WEITE_SPALTEN else ""}>{z}</td>'
           for i, z in enumerate(zellen)]
    return "      <tr>" + "".join(tds) + "</tr>"


def html_schreiben(records, gruppen, fundstellen_gesamt, seite):
    kopfzeile = "".join(f"<th>{h(s)}</th>" for s in seite["spalten"])
    meta = seite["meta"].format(stand=STAND, anzahl=len(records),
                                fundstellen=fundstellen_gesamt)
    teile = [
        "<!DOCTYPE html>",
        f'<html lang="{seite["lang"]}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">',
        f'<title>{h(seite["titel"])}</title>',
        f'<meta name="description" content="{h(seite["kernaussage"])}">',
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        "<main>",
        f'<p class="wechsel"><a href="{seite["wechsel_ziel"]}" '
        f'hreflang="{seite["wechsel_lang"]}">'
        f'{h(seite["wechsel_text"])}</a></p>',
        f'<h1>{h(seite["titel"])}</h1>',
        f'<p class="kern">{h(seite["kernaussage"])}</p>',
        f'<p class="leise">{h(meta)} {h(seite["sprachhinweis"])}</p>',
    ]
    for g in gruppen:
        teile += [
            f'<h2>{h(g[seite["gruppe_titel"]])}</h2>',
            f'<p>{h(g[seite["gruppe_aussage"]])}</p>',
            '<div class="rahmen">',
            "  <table>",
            f"    <thead><tr>{kopfzeile}</tr></thead>",
            "    <tbody>",
        ]
        teile += [html_zeile(r, seite)
                  for r in records if r["gruppe"] == g["id"]]
        teile += ["    </tbody>", "  </table>", "</div>"]
    teile += [
        "<footer>",
        f'<p>{seite["fuss_erzeugt"].format(stand=h(STAND))}</p>',
        f'<p>{seite["fuss_lizenz"].format(lizenz=LIZENZ_URL, repo=REPO_URL)}'
        f'</p>',
        "</footer>",
        "</main>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(teile)


def main():
    records = records_lesen()
    if not records:
        print("FEHLER: keine Records in curation/", file=sys.stderr)
        return 1

    gruppen = gruppen_lesen()
    fehler, warnungen = validieren(records, raw_ids(), gruppen)
    gruppen_pruefen(gruppen, fehler)
    pruefquellen_pruefen(pruefquellen_lesen(), fehler)
    for w in warnungen:
        print(f"WARNUNG: {w}")
    if fehler:
        for f in fehler:
            print(f"FEHLER: {f}", file=sys.stderr)
        return 1

    je_form, je_form_hrsg, fundstellen_gesamt = evidenz_zaehlen()
    sortiert = []
    for _, r in sorted(records, key=lambda t: t[1]["id"]):
        ausgabe_record = dict(mit_abgeleiteten_links(r))
        ausgabe_record["statistik"] = statistik_fuer(r, je_form)
        ausgabe_record["belegt_durch"] = belegt_fuer(r, je_form_hrsg)
        sortiert.append(ausgabe_record)
    belegte_records = sum(1 for r in sortiert if r["statistik"])
    abgeleitet = sum(1 for r in sortiert
                     for link in r["links"]
                     if link["label"] == ABGELEITET_LABEL)

    os.makedirs(DIST, exist_ok=True)
    ausgabe = {
        "meta": {
            "stand": STAND,
            "quelle_seed": QUELLE_SEED,
            "anzahl": len(sortiert),
            "fundstellen_gesamt": fundstellen_gesamt,
            "kernaussage": KERNAUSSAGE,
            "gruppen": gruppen,
        },
        "sigel": sortiert,
    }
    with open(os.path.join(DIST, "sigel.json"), "w", encoding="utf-8") as f:
        json.dump(ausgabe, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    with open(os.path.join(DIST, "SIGEL.md"), "w", encoding="utf-8") as f:
        f.write(md_schreiben(sortiert, gruppen))
    os.makedirs(DOCS, exist_ok=True)
    for seite in SEITEN.values():
        pfad = os.path.join(DOCS, seite["datei"])
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(html_schreiben(sortiert, gruppen, fundstellen_gesamt,
                                   seite))

    seiten = ", ".join(f"docs/{s['datei']}" for s in SEITEN.values())
    print(f"Build: {len(sortiert)} Records -> dist/sigel.json, dist/SIGEL.md, "
          f"{seiten} "
          f"({abgeleitet} abgeleitete Links, {belegte_records} Records mit "
          f"Evidenz aus {fundstellen_gesamt} Fundstellen, "
          f"{len(warnungen)} Warnungen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
