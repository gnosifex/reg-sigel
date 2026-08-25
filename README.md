# Sigel-Register

**Ein Register der Kurzformen, unter denen Regulatorik zitiert wird — und der
Belege, dass sie so tatsächlich geschrieben werden.** Wer „MaRisk“, „RTS RMF“
oder „EBA/GL/2019/02“ liest, soll nachschlagen können, welches Dokument
gemeint ist, in welcher Fassung und wie verbindlich — und woher die Kurzform
stammt. Jeder Eintrag löst auf ein zitierfähiges Dokument mit
Identitätsanker auf; jede Schreibform trägt, soweit erhoben, die Fundstellen,
an denen sie belegt ist.

Der fertige Bestand steht in [`dist/SIGEL.md`](dist/SIGEL.md) (Tabellen),
[`dist/sigel.json`](dist/sigel.json) (maschinenlesbar) und als statische
Seite unter [`docs/index.html`](docs/index.html).

## Gegenstand und Grenzen

**Das Register ist kuratiert und wachsend, nicht vollständig.** Es sammelt,
was im Umfeld der EU- und deutschen Finanzregulatorik und der angrenzenden
IT- und Informationssicherheits-Regulatorik zitiert wird: EU-Verordnungen und
-Richtlinien, delegierte und Durchführungsrechtsakte, europäische
Aufsichtsleitlinien, deutsche Gesetze und Aufsichtspraxis sowie die
Standards, die dort als Referenz herangezogen werden. Ein
Vollständigkeitsversprechen gibt es nicht und kann es nicht geben — der
Bestand wächst mit Meldungen und Kuration.

**Wie fest ein Eintrag sitzt, sagt der Eintrag selbst.** Das Register
behauptet nicht pauschal Verlässlichkeit, sondern legt sie je Eintrag offen:
`identitaet` nennt den Anker auf das Dokument, `haerte` die Bindung der
Kurzform an ihre Quelle, `geprueft` den Prüfstand jeder einzelnen Behauptung
und `statistik` die Zahl der Fundstellen, die `raw/` für jede Schreibform
führt. Ein Eintrag ohne Evidenz ist als solcher erkennbar.

Das Register beschreibt Rechtstexte und Normen, es enthält sie nicht.

## Vier Bausteine

- **`raw/`** — Evidenzschicht: verbatim festgehaltene Funde (Fundstelle,
  Abrufdatum, Methode), append-only. **Evidenz kommt ausschließlich aus
  Originalquellen** — Publikationen der Herausgeber, Regulatoren und
  Marktteilnehmer, nie aus Eigentexten des Registerbetreibers: Eigenzitate
  belegen keine Praxis (Zirkularität). **Wortgetreue lokale Spiegel zählen
  als ihre Originalquelle:** Der Betreiber hält einen Korpus gespiegelter
  Originalpublikationen mit Herkunfts-URL und Verbindlichkeitsrang im
  Frontmatter; durchsucht werden nur die Record-Bodys, die Fundstelle ist die
  Original-URL, `rang_quellen` hält den Rang der Quelldokumente fest.
  Eigentexte solcher Bestände (Antworten, Wiki, Analysen, Frontmatter,
  Sidecars) sind ausgeschlossen. Aliasse ohne externe Evidenz sind zulässig
  und tragen eine leere `evidenz`-Liste — der Build warnt, bis Discovery sie
  belegt. Jeder raw-Record nennt in `herausgeber` die publizierende Stelle
  (BaFin, EZB, BBK, EBA …); der Build aggregiert daraus je Register-Eintrag
  die Spalte **Belegt durch** und das JSON-Feld `belegt_durch` — sichtbar,
  bei welchen Häusern eine Form des Sigels verifiziert ist.
- **`kuration/`** — Entscheidungsschicht: ein Record je Quelle, von Hand
  gepflegt; hier fällt jede Entscheidung über Sigel, Identität und Aliasse.
- **`tools/build.py`** — deterministischer Build: validiert `kuration/` gegen
  `raw/` und schreibt sortiert nach `dist/` und `docs/`.
- **`tools/watch.py`** — Fassungsüberwachung: fragt für jeden Record mit
  CELEX-Anker den Cellar-Bestand ab und meldet, wo die registrierte
  Konsolidierung überholt ist. Liest nur; nachgezogen wird von Hand.
- **`tools/intake.py`** — Ingest gemeldeter Sigel: prüft eine Meldung gegen
  ihre Quelle (`--vorpruefung`) und erzeugt daraus Records
  (`--uebernehmen`). Siehe [Meldung und automatischer
  Ingest](#meldung-und-automatischer-ingest).

Datenformat ist JSON; das Schema ist YAML-fähig, ein Wechsel änderte nur den
Serializer.

## Record-Schema

| Feld | Bedeutung |
|---|---|
| `id` | kebab-case-Slug aus dem Sigel; zugleich Dateiname |
| `sigel` | kanonische Kurzform (lebt vor allem in Rang-3–7-Texten) |
| `sprache` | Sprache der kanonischen Form (`de` oder `en`) |
| `referenzform` | amtliche Referenzform — wie Rechtsakte die Quelle zitieren (Verordnungsnummer, GL-ID); rankt identisch mit dem Sigel, denn der Rang gehört zur Zielquelle, nicht zur Schreibform |
| `name` | Vollbezeichnung |
| `haerte` | Bindung der Kurzform an ihre Quelle (vier Stufen, siehe unten) |
| `haerte_geprueft` | `{datum, methode}` — Methode ist immer `einschaetzung` |
| `gruppe` | Gruppen-ID aus `kuration/gruppen.json` |
| `identitaet` | `{typ, wert, geprueft}` — Anker auf das Dokument, **nicht auf die Fassung** |
| `fassung` | `{stand, konsolidierung, text}` |
| `links` | Liste `{label, url, geprueft}` |
| `aliasse` | Liste `{form, sprache, evidenz: [raw-ids]}` — jede Nebenform belegt |
| `ersetzt` / `ersetzt_durch` | Rechtsnachfolge als Listen von Record-IDs |
| `status` | Reifegrad des Records |

### Jede Schreibform trägt ihre Sprache

`sprache` steht am Record für die kanonische Form und an jedem Alias für die
Nebenform; zulässig sind `de` und `en`. So bleiben deutsche und englische
Kurzform derselben Quelle unterscheidbar, ohne dass die Sprache aus der Form
geraten werden müsste — die DSGVO heißt englisch `GDPR`, und beide Formen
belegen dasselbe Dokument. Wo eine Form in beiden Sprachen gleich lautet
(`DORA`, `CRD IV`), gibt es nichts zu unterscheiden: Sie steht einmal, in der
Sprache ihres Records.

### Identität und Fassung sind getrennt

`identitaet` benennt das Dokument über seine Lebenszeit hinweg, `fassung`
den Stand, auf den sich der Eintrag heute bezieht. Bei EU-Recht heißt das:
`identitaet.wert` trägt die **Basis-CELEX** (Sektor 3, `32013L0036`), die
konsolidierte CELEX (`02013L0036-20260711`) steht in
`fassung.konsolidierung`. So bleibt der Anker stabil, wenn eine neue
Konsolidierung erscheint — nachzuziehen ist dann allein die Fassung.

`fassung.text` ist die Fassungsangabe im Wortlaut der Quelle;
`fassung.stand` das Stichdatum in ISO, aber **nur wo es aus dem Text
eindeutig hervorgeht** (Muster `Stand …`, `vom …`, `Fassung …`). Ein
nacktes Datum ohne Schlüsselwort bleibt `null` — es könnte Erlass-,
Anwendungs- oder Aufhebungsdatum sein.

### Fünf Ankertypen, keiner davon offen

| `typ` | Wert | Bestand |
|---|---|---|
| `celex` | Basis-CELEX, Sektor 3 | EU-Rechtsakte und Fassungsgenerationen |
| `jurabk` | juris-Abkürzung (`ao_1977`, `hgb`, `kredwg`, `zag_2018`) | deutsche Gesetze |
| `doc_ref` | Dokumentkennzeichen des Herausgebers (`EBA/GL/2019/02`) | Leitlinien und Rechtsakte ohne CELEX-Anker |
| `version` | Versionslabel (`v8.1`, `C5:2026`, `V3.1a`) | Standards ohne Dokumentnummer |
| `offen` | `null` | derzeit keiner |

`version` ist der schwächste Anker: Er identifiziert die Fassung, nicht das
Dokument, und wandert bei jedem Release mit. Herausgeber ohne
Dokumentkennzeichen (CVSS, EPSS, CIS Controls, PCI DSS, BSI C5, SDM,
ENISA TIG) lassen keinen besseren zu.

### Der Härtegrad sagt, wie fest die Kurzform sitzt

`haerte` unterscheidet vier Stufen: **`amtlich`** — vom Normgeber oder
Herausgeber förmlich vergeben (juris-Abkürzung, Dokumentkennzeichen,
Normnummer); **`herausgeberueblich`** — nicht vergeben, aber vom Herausgeber
selbst in seinen Publikationen geführt; **`verkehrsueblich`** — breite Praxis
ohne amtliche Vergabe; **`hausform`** — Konvention allein dieses Registers.
Die Einstufung ist **kuratierte Einschätzung, bis Discovery-Evidenz sie
misst** — deshalb trägt `haerte_geprueft` die Methode `einschaetzung` und
nicht `web-abruf`.

**Kanonisch ist nie eine Hausform, wenn eine extern belegte Form existiert:**
Trägt eine amtliche oder herausgeberübliche Form die Quelle — die BaFin etwa
führt in ihren DORA-Publikationen eine Abkürzungslegende mit „RTS RMF“,
„RTS TPPol“, „RTS CCI“, „RTS CTIR“, „ITS RoI“ und „ITS TIR“ —, dann ist sie
das Sigel; abweichende Eigenkonventionen laufen als Aliasse.

### Konsolidierte EU-Fassungen bekommen ihren Link gerechnet

Ein Record mit `identitaet.typ: celex` und gesetzter `fassung.konsolidierung`
erhält **erst in der Ausgabe** den EUR-Lex-Link auf genau diese Fassung
(`methode: abgeleitet-aus-fassung`, ohne Prüfdatum — er ist gerechnet, nicht
abgerufen); URL-gleiche kuratierte Links unterdrücken ihn. `kuration/` bleibt
davon unberührt. Ohne `konsolidierung` entsteht keiner: Die
Basis-CELEX-Seite zeigt die Ursprungsfassung, nicht die registrierte.

### Jede Behauptung trägt ihren Prüfstand

`geprueft` steht an jedem Link **und** an jedem Identitätsanker, als
`{datum, methode}` oder `null` (ungeprüft). Vier Methoden:

- **`web-abruf`** — Ziel geöffnet und bestätigt.
- **`konstruiert`** — mechanisch aus einer Kennung gebaut, nie abgerufen;
  plausibel, aber unbelegt.
- **`seed-doksigel`** — aus dem kuratierten Seed des Betreibers übernommen
  (Stand 2026-08-24), Prüfstand der Quelle.
- **`spiegel-provenienz`** — URL aus dem Provenienz-Frontmatter eines
  wortgetreuen lokalen Spiegels übernommen, wo sie beim Abruf gegen das
  Dokument verifiziert wurde; belegt durch den Spiegel, nicht durch einen
  eigenen Abruf.

Der Unterschied ist der Zweck des Felds: Ein konstruierter EUR-Lex-Link
sieht wie ein geprüfter aus, ist aber keiner.

### Die Nutzungsstatistik zählt Fundstellen, nicht Dokumente

Jeder Record der Ausgabe trägt `statistik` — je Schreibform die Zahl der
Fundstellen, die `raw/` dafür führt (kanonisches Sigel und jede
Alias-Form). Gezählt wird über alle Evidenzdateien hinweg nach Form; ein
leeres Objekt heißt „keine Fundstelle“, nicht „nicht erhoben“. `meta`
nennt mit `fundstellen_gesamt` die Gesamtzahl der Belege im Bestand. Das
Feld entsteht wie die abgeleiteten Links erst in der Ausgabe — `kuration/`
bleibt Handpflege — und erscheint bewusst nicht in `SIGEL.md`: Die
Belegdichte sagt etwas über den Erschließungsstand des Registers, nichts
über die Quelle.

### Der Rang trägt die Verbindlichkeits-Hierarchie

`rang` trägt die Verbindlichkeitsstufe: **1** bindendes Recht der eigenen
Rechtsordnung (EU-Verordnungen, Richtlinien, nationale Gesetze) · **2**
delegierte und Durchführungsrechtsakte · **3** Leitlinien und konsultierte
Rundschreiben (MaRisk, BAIT) · **4–7** Q&As, vorbereitendes Material,
aufsichtliche Mitteilungen, rollende Webkommunikation (im Bestand derzeit
unbesetzt) · **null** („—“) Standards und Praktiken ohne Rechtsbindung. Die
Zahlen sind identisch mit denen des Korpus-Rangmodells, dem die
Spiegel-Evidenz entstammt, und mit dem öffentlichen
[dora-graph](https://github.com/gnosifex/dora-graph) — Register und Graph
sind damit interoperabel. Rang und Gliederung schneiden sich bewusst:
`gruppe` ordnet nach Herausgeber und Wirkmechanismus, `rang` nach
Bindungswirkung — Rang 1 liegt in drei Gruppen.

## Gliederung nach absteigender Verbindlichkeit

`kuration/gruppen.json` führt die Gruppen als geordnete Liste, jede mit
Titel und einer tragenden Aussage; die Reihenfolge dort ist die Reihenfolge
der Ausgabe und folgt der abnehmenden regulatorischen Verbindlichkeit — von
EU-Verordnungen über delegierte Rechtsakte, Richtlinien, europäische und
nationale Aufsichtsvorgaben bis zu freiwilligen Standards. Jeder Record
nennt seine Gruppe in `gruppe`; der Build lehnt unbekannte Gruppen und leere
Gruppen ab. Eine Ein-Mann-Gruppe ist zulässig, wenn sie einen eigenen
Wirkmechanismus trägt (`eu-richtlinien`).

## Triage-Grundsatz

Registereintrag wird nur, was auf ein **zitierfähiges Dokument mit
Identitätsanker** auflöst. Reine Fachbegriffs-Abkürzungen (SBOM, IKT, ISMS)
bezeichnen keine Quelle und werden nie aufgenommen.

**Generationslabels sind eigene Einträge.** Wer `CRD V` oder `CRR III`
schreibt, meint eine bestimmte Fassung des Basisakts, nicht den Akt in
seinem heutigen Stand — das Label ist also selbst ein Sigel und bekommt
einen eigenen Record. Er trägt die **Basis-CELEX des Akts** als Identität
(`CRD IV`–`CRD VI` → `32013L0036`, `CRR II`/`CRR III` → `32013R0575`),
nennt in `fassung.text` den Änderungsrechtsakt, der die Generation
begründet, und verlinkt ihn. `fassung.konsolidierung` bleibt dabei leer:
Eine Generation gilt über mehrere konsolidierte Fassungen hinweg, keine
einzelne davon *ist* die Generation. Die Generationen einer Familie sind über
`ersetzt`/`ersetzt_durch` verkettet; die Stamm-Records `CRD` und `CRR`
bleiben als Akt-Einträge auf dem heutigen Stand daneben stehen und
verketten nicht. Schreibvarianten (`CRDIV`, `CRD 4`) sind Aliasse des
jeweiligen Generations-Records, sobald Discovery sie belegt.

**Jede Sigel-Meldung nennt ihre Quelle.** Wer einen neuen Eintrag meldet,
nennt die Originalfundstelle als URL; eine Meldung ohne Quelle wird nicht
aufgenommen. Die Prüfung gegen genau diese Quelle ist der Aufnahme-Handgriff
und erzeugt zugleich den ersten raw-Evidenz-Record des neuen Eintrags.

## Meldung und automatischer Ingest

**Gemeldet wird per Issue, geprüft von der Action, aufgenommen von einer
täglichen Routine, gemergt nur bei grüner CI — ohne Human-in-the-loop.** Die
Aufnahme-Regel des Registers ist eine Quellen-Regel, und eine Quellen-Regel
ist maschinell vollziehbar: Kommt die gemeldete Kurzform in der genannten
Originalfundstelle wörtlich vor und ist diese Fundstelle eine freigegebene
Prüfquelle, ist der Eintrag belegt; fehlt eines von beidem, ist er es nicht.

```sh
gh issue create --repo gnosifex/reg-sigel --template sigel-meldung.yml
```

### Zwei Felder sind die ganze Angriffsfläche

Das Meldeformular fragt **Kurzform** (höchstens 25 Zeichen) und
**Quelle-URL** (höchstens 200 Zeichen) ab, sonst nichts. Damit ist der
gesamte Fremdtext, der je in die Verarbeitung gelangt, auf **225 geprüfte
Zeichen** begrenzt; alles Weitere — amtliche Referenzform, Vollbezeichnung,
Identitätsanker, Herausgeber, Gruppe, Rang — stammt aus der verifizierten
Quelle, aus `kuration/pruefquellen.json` oder aus der Kuration. Eine
Überschreitung der Längen ist eine Ablehnung mit Nennung von Feld, Ist-Länge
und Limit, kein Rückfragen.

### Vier Stufen, jede mit eigener Zuständigkeit

**Stufe 1 — Meldung.** Das Issue-Formular
`.github/ISSUE_TEMPLATE/sigel-meldung.yml` fragt die beiden Pflichtfelder ab.

**Stufe 2 — Vorprüfung durch die Action.**
`.github/workflows/intake.yml` läuft bei jedem geöffneten oder bearbeiteten
Issue mit Label `sigel-meldung` und ruft `tools/intake.py --vorpruefung`.
Die prüft deterministisch (Pflichtfelder, Längen, Sigel- und URL-Syntax,
Kollision gegen `kuration/`), ruft die Quelle ab — HTML direkt, PDF über
`pdftotext` — und sucht die Kurzform wortgenau. Ergebnis ist das
**Artefakt**: ein Bot-Kommentar mit dem Marker `<!-- intake-artefakt v1 -->`,
dem Prüfbericht und dem Prüfergebnis als JSON, samt den Kontextzeilen, die
die Action selbst aus dem abgerufenen Quelltext geschnitten hat. Die Action
**schreibt nichts** ins Repo und braucht kein Push-Recht.

Sie entscheidet dreierlei:

- **bestanden** → Label `vorgeprueft-ok`, Issue bleibt offen;
- **formal mangelhaft, Kurzform in der Quelle nicht belegt, oder Quelle nicht
  auf der Prüfquellen-Liste** → Label `abgelehnt` und Close;
- **Kollision mit einem bestehenden Record** → Label `wartet-maintainer`.

**Beleg und freigegebene Domain sind zusammen die Bedingung.** Eine fremde
Domain ist kein Wartefall, sondern eine Ablehnung mit Verweis auf den
Prüfquellen-Prozess; `wartet-maintainer` bleibt damit dem einen Fall
vorbehalten, in dem Bestehendes berührt würde.

**Stufe 3 — Aufnahme durch die tägliche Routine.** Ein geplanter
Claude-Code-Agent arbeitet nach `tools/routine-intake.md` alle offenen
`vorgeprueft-ok`-Issues ab. Er liest dabei **ausschließlich das Artefakt** —
den jüngsten Kommentar mit dem Marker, dessen Autor `github-actions[bot]`
ist —, niemals Issue-Titel, -Body oder Kommentare Dritter. Der Grund ist die
Herkunft der Texte: Der Rohtext ist angreifergesteuert, das Artefakt ist
syntaxgeprüft, längenbegrenzt und an der Quelle verifiziert.

Die Routine leistet, was Urteilskraft verlangt: Triage (ist das überhaupt ein
Quellen-Sigel?), Ermittlung von Referenzform, Vollbezeichnung und
Identitätsanker aus der Quelle, begründete Zuordnung von Gruppe und Rang.
Dann ruft sie `python tools/intake.py --uebernehmen --artefakt …` mit genau
diesen Zuarbeiten. Das Skript erzeugt den kuration-Record
(`status: auto-intake`, `haerte: verkehrsueblich` als Einschätzung) und den
raw-Evidenz-Record aus dem eigenen Abruf und ruft `build.py` — **nur bei
Exit 0 wird committet**, der Build ist das letzte Gate. Lässt sich der
Identitätsanker nicht sicher ermitteln, wird nicht geraten:
`wartet-maintainer`.

**Stufe 4 — Merge nur bei grüner CI.** Die Routine arbeitet auf einem Branch
`intake/<datum>`, eröffnet einen Pull Request und aktiviert Auto-Merge. Sie
committet nie auf `main` und mergt nie selbst. Zusammengeführt wird erst,
wenn `intake-guard` und `build` grün sind.

### Der Guard macht die Leitplanke zur Bedingung

`tools/intake_guard.py` prüft auf jedem Pull Request den Diff gegen die Basis
und lässt genau dreierlei durch:

- neue Dateien unter `kuration/` (außer `gruppen.json` und
  `pruefquellen.json`) und unter `raw/`,
- **feldweise reine Ergänzungen** an bestehenden kuration-Records: neue
  Alias-Einträge und neue Evidenz-IDs in bestehenden Aliassen, sonst kein
  Feld geändert,
- den neu gebauten Stand von `dist/` und `docs/`.

Alles andere — `tools/`, `.github/`, `README.md`, `gruppen.json`,
`pruefquellen.json`, Änderungen an bestehenden Feldern, Umbenennungen,
Löschungen — beendet den Lauf mit Exit 1 und einer Befundliste.

Das ist der Unterschied zwischen einer Zusage und einer Bedingung: Ein
Auftragstext ist eine Bitte, die ein hinreichend geschickt formulierter
Fremdtext untergraben könnte. Der Guard fragt nicht, was gemeint war, sondern
was im Diff steht. Lokal prüfbar:

```sh
python3 tools/intake_guard.py --selbsttest
python3 tools/intake_guard.py --basis origin/main
```

### Sieben Schutzgeländer tragen die Automatik

- **Quelle-Pflicht.** Keine Fundstelle, keine Aufnahme — und die Fundstelle
  wird abgerufen, nicht geglaubt.
- **Minimale Angriffsfläche.** 225 geprüfte Zeichen Melder-Input; alles
  Weitere stammt aus verifizierten Quellen oder aus der Kuration.
- **Das Artefakt statt des Rohtexts.** Die Routine verarbeitet nie, was ein
  Fremder geschrieben hat, sondern nur, was die Action daraus geprüft hat.
- **Additiv-only, doppelt.** Das Skript vergleicht die geänderte Datei
  feldweise gegen das Original und bricht ab, wenn sich außerhalb von
  `aliasse` etwas gerührt hat; der Guard prüft dasselbe noch einmal am Diff.
- **Prüfquellen-Liste.** Nur Fundstellen der kuratierten Domains gelten als
  Beleg (siehe nächster Abschnitt).
- **`status: auto-intake` und die Ratenbremse.** Automatisch entstandene
  Records sind an ihrem Status erkennbar; mehr als zehn
  `auto-intake`-Commits am selben Tag, und die Aufnahme schaltet auf
  `wartet-maintainer`.
- **Das Issue ist der Audit-Trail.** Meldung, Artefakt, Entscheidung und
  Commit-Betreff stehen an einem Ort und sind öffentlich nachlesbar.

Lokal prüfbar ist die Kette mit den Fixtures unter `tools/tests/` — einer für
den tragenden Fall, drei für die Ablehnungsgründe:

```sh
ISSUE_NUMBER=1 python3 tools/intake.py --vorpruefung \
    --body-datei tools/tests/meldung-valide.md
ISSUE_NUMBER=1 python3 tools/intake.py --vorpruefung \
    --body-datei tools/tests/meldung-ohne-quelle.md
ISSUE_NUMBER=1 python3 tools/intake.py --vorpruefung \
    --body-datei tools/tests/meldung-zu-lang.md
ISSUE_NUMBER=1 python3 tools/intake.py --vorpruefung \
    --body-datei tools/tests/meldung-fremde-domain.md
```

`--dry-run` lässt `--uebernehmen` auf einer Kopie des Repos im
Temp-Verzeichnis arbeiten und den Bestand unberührt.

### Die Prüfquellen-Liste ist die einzige Stufe mit Human-in-the-loop

`kuration/pruefquellen.json` führt die Domains, deren Publikationen der
Ingest als Beleg akzeptiert — je Eintrag `domain`, `herausgeber`, `typ`
(`eu-behoerde`, `eu-amtsveroeffentlichung`, `nationale-aufsicht`,
`notenbank`, `us-aufsicht`, `gesetzesportal`, `normungsorganisation`),
`aufgenommen` und `freigabe`. Sie ist Konfiguration wie `gruppen.json`, kein
Record; der Build validiert Pflichtfelder und Eindeutigkeit der Domains mit.
Subdomains gelten mit der Domain als erfasst.

Der Bestand ist eine **Vorbelegung des Maintainers**
(`freigabe: maintainer-seed`) über die EU-Behörden und
-Amtsveröffentlichungen, die nationalen Aufsichten und Notenbanken der
EU-Mitgliedstaaten, das Vereinigte Königreich und die US-Bankenaufsicht sowie
die einschlägigen Normungsorganisationen. **Die Domains sind dabei nicht
einzeln verifiziert** — der Seed ist eine Setzung, kein Prüfbefund;
Korrekturen laufen über denselben Prüfquellen-Prozess wie Erweiterungen.

**Erweitert und korrigiert wird die Liste nur vom Maintainer.**
Vorgeschlagen wird per Issue
(`.github/ISSUE_TEMPLATE/pruefquelle-vorschlag.yml`, Label
`pruefquelle-vorschlag`); die Action kennzeichnet solche Issues mit
`wartet-maintainer` und tut sonst nichts. **Die tägliche Routine rührt sie
nicht an** — auch nicht vorprüfend oder kommentierend. Abgearbeitet werden
sie ausschließlich in einer Maintainer-Session, die zwei Fragen belegt
beantwortet: Ist die Domain die offizielle Präsenz des behaupteten
Herausgebers, und publiziert dieser Regulatorik oder Standards? Der Grund für
die Trennung ist einzeilig: Wer die Prüfquellen kontrolliert, kontrolliert
das Register — die Objektebene ist automatisiert, die Vertrauensebene nicht.

## Offene Modellierungsfragen

**Rechtsnachfolge greift bislang nur innerhalb der CRD-/CRR-Familien.**
`ersetzt` und `ersetzt_durch` verketten die Generationen-Records; alle
übrigen Records führen die Felder leer. Die abgelösten und ablösenden
Dokumente, die deren Fassungstexte nennen — MaRisk RS 06/2024,
EBA/GL/2026/06 —, sind selbst keine Records: Aufgenommen wird eine Fassung
nur, wenn sie ein eigenes verkehrsübliches Sigel trägt, und das gilt für
Rundschreiben-Vorgänger nicht.

**Die Bankenrichtlinien vor CRD IV fehlen.** `CRD I`–`CRD III` bezeichnen
Fassungen der Vorgänger-Basisakte 2006/48/EG und 2006/49/EG, nicht der
Richtlinie 2013/36/EU; sie brauchen deshalb eigene Identitätsanker und
sind bewusst noch nicht angelegt. Wer sie ergänzt, hängt sie über
`ersetzt_durch` an `crd-iv`.

**`version` als Anker bleibt ein Behelf** — siehe oben; ein Wechsel auf
einen echten Dokumentanker ist nur möglich, wenn ein Herausgeber einen
vergibt.

**Fassungsüberwachung erreicht nur einen Teil des Bestands.** `watch` deckt
die Records mit CELEX-Anker ab; für `doc_ref`, `jurabk` und `version` gibt es
keine vergleichbare Fassungsliste, sie bleiben Handkontrolle.

## Fassungen prüfen

```sh
python3 tools/watch.py [--json <pfad>]
```

`watch` fragt für jeden Record mit `identitaet.typ: celex` die
konsolidierten Fassungen des Basisakts ab und vergleicht die jüngste mit
`fassung.konsolidierung`. Es **schreibt nie** nach `kuration/` oder
`dist/`: Ein Befund ist ein Auftrag an die Handpflege. Exit 1, sobald ein
Record `veraltet` ist; `unpruefbar` bleibt Warnung.

**Zwei Wege, in dieser Reihenfolge.** Standard ist eine SPARQL-Abfrage an
`https://publications.europa.eu/webapi/rdf/sparql`, die zum
Konsolidierungspräfix (`32013L0036` → `02013L0036-`) alle CELEX-Kennungen
liefert — Antworten im Kilobyte-Bereich. Fällt sie aus, holt `watch` das
Notice-XML des Basisakts (`Accept: application/xml;notice=branch`, rund
1–3 MB) und zieht die Kennungen per Regex. Der Notice-Weg braucht
zusätzlich `Accept-Language: deu`; ohne den Kopf antwortet das Cellar mit
HTTP 400. Der Website-Weg zu EUR-Lex bleibt per Web-Abruf gesperrt.

**Grenzen.** Abgefragt wird sequenziell, höchstens ein Request je Sekunde,
mit ehrlichem User-Agent. `watch` prüft, ob eine *jüngere Konsolidierung
existiert* — nicht, ob sie inhaltlich einschlägig ist; die Entscheidung,
ob ein Record nachgezogen wird, bleibt kuratorisch. Führt ein Record keine
Konsolidierung, das Cellar aber schon, gilt er als `veraltet`. Steht die
registrierte Fassung nicht in der Cellar-Liste, gilt er als `unpruefbar` —
das ist ein Datenbefund und kein Netzfehler.

## Bauen

```sh
python3 tools/build.py    # wiederholbar; Exit 1 bei Validierungsfehlern
```

Der Build prüft Eindeutigkeit von `id` und `sigel`, die Sprache jeder
Schreibform, Kollisionsfreiheit der Alias-Formen gegen fremde Sigel, die
Auflösbarkeit jeder `evidenz`-Referenz nach `raw/`, die Struktur von
`fassung` und jedem `geprueft`-Block, den Härtegrad gegen die Werteliste, die
Gruppenzuordnung gegen `gruppen.json` sowie die Auflösbarkeit von
`ersetzt`/`ersetzt_durch` auf existierende Record-IDs. Dazu prüft er
`pruefquellen.json` auf vollständige Einträge und eindeutige, wohlgeformte
Domains — `gruppen.json` und `pruefquellen.json` sind Konfiguration der
Kurationsschicht und werden nie als Record gelesen. `identitaet.typ: offen`
ist eine Warnung, kein Fehler. Kein Netzzugriff; Recherche ändert nur
`kuration/`. `dist/` und `docs/` sind committet, damit Diffs die Wirkung
einer Kurations-Änderung zeigen.

Daneben liegen die Migrationsskripte (`migrate_v2.py`, `migrate_haerte.py`,
`migrate_gruppen.py`, `seed_aus_sigeltabelle.py`). Sie bleiben im Repo, weil sie
die ausführbare Beschreibung je einer Schemaänderung sind, und laufen auf
migrierten Beständen als No-op. Keines seedet neu — die Kurationsstände sind
handbearbeitet.

### Die statische Seite ist dieselbe Tabelle, ohne Renderer

`docs/index.html` entsteht im selben Lauf: eine einzelne Datei, kein Skript,
kein externes Asset — Titel, Kernaussage, je Gruppe Überschrift, Aussage und
Tabelle mit klickbaren Quelle-Links, dazu Stand und Lizenz in der Fußzeile.
Was der Browser lädt, steht vollständig in dieser Datei; die Tabellen
scrollen waagerecht in ihrem eigenen Rahmen, statt die Seite zu sprengen.
Lokal ansehen:

```sh
python3 -m http.server --directory docs 8000
```

## CI hält den committeten Ausgabestand ehrlich

`.github/workflows/build.yml` läuft bei `push` und `pull_request`, baut,
prüft mit `git diff --exit-code dist/`, dass der committete Ausgabestand der
Kuration entspricht, und beweist mit einem zweiten Lauf plus Byte-Vergleich
den Determinismus. `.github/workflows/intake-guard.yml` läuft auf Pull
Requests und setzt die Ingest-Leitplanken durch. `watch` läuft **nicht** in
CI: Er braucht Netz zum Cellar, und ein fremder Dienst gehörte sonst in den
Erfolgspfad des Builds.

## Lizenz

CC BY 4.0 — Namensnennung „gnosifex“, Lizenztext unter
[creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/legalcode.de),
Bedingungen und Geltungsbereich in [LICENSE](LICENSE). Die zitierten
Rechtstexte und Normen selbst sind davon nicht erfasst — das Register
beschreibt sie, es enthält sie nicht.
