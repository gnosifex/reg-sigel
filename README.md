# reg-sigel — Register of Regulatory Source Sigla

**A curated register of the short forms under which financial regulation is cited — and of the evidence that they are really written that way.** For every siglum the register records the short form itself, the official reference form, an identity anchor that survives amendment, the version the entry currently pledges, a rank of bindingness, and aliases backed by evidence. Anyone who reads "MaRisk", "RTS RMF" or "EBA/GL/2019/02" can look up which document is meant, in which version, how binding it is, and where the short form comes from.

The scope is the source vocabulary of EU, UK and US financial regulation and the adjacent IT and information-security regulation — EU regulations and directives, delegated and implementing acts, European supervisory guidelines, national law and supervisory practice, and the standards cited alongside them.

The built register lives in [`dist/SIGEL.md`](dist/SIGEL.md) (tables), [`dist/sigel.json`](dist/sigel.json) (machine-readable) and as a static page in two languages — [`docs/index.html`](docs/index.html) (English) and [`docs/de.html`](docs/de.html) (German).

Browse the registry in your browser: **https://gnosifex.github.io/reg-sigel/** (English) · **https://gnosifex.github.io/reg-sigel/de.html** (Deutsch)

The data comes from a non-public regulatory corpus. This is its third public spin-off, alongside [esa-qa-mirror](https://github.com/gnosifex/esa-qa-mirror) — a Markdown mirror of the supervisory Q&As — and [dora-graph](https://github.com/gnosifex/dora-graph) — an animated map of the DORA regulation and its surrounding documents.

## AI agents are a core audience, and that is why the format looks like this

The register is written for two readers at once: a person looking up a citation, and a machine resolving one. Everything about the format follows from the second reader.

- **The build is deterministic.** `tools/build.py` reads `curation/` and `raw/` and writes byte-identical output for identical input, with no network access. CI proves it by building twice and comparing.
- **The machine-readable artifact is stable.** `dist/sigel.json` carries a `meta` block and a `sigel` array of records, sorted by `id`, with a fixed field set. It is committed, so any change to it is visible in the diff.
- **Every claim carries its own verification status.** A link, an identity anchor and a hardness grade each carry `geprueft` — date and method, or `null`. An agent can therefore tell a fetched-and-confirmed link from a constructed one instead of trusting the whole file uniformly.
- **Identity and version are separate fields**, so an agent can resolve a siglum to a document that stays the same across amendments, and separately to the version this register currently pledges.
- **Aliases are enumerated and evidenced**, so a string found in the wild can be matched back to one record rather than guessed at.

For machines, fetch the raw JSON directly: `https://raw.githubusercontent.com/gnosifex/reg-sigel/main/dist/sigel.json`

```sh
curl -s https://raw.githubusercontent.com/gnosifex/reg-sigel/main/dist/sigel.json | jq '.sigel[] | select(.sigel == "DORA")'
```

## The field names are German; this is what they mean

Field names are data, not prose — they are never translated, in either direction. The word *Sigel* itself (cf. Latin *siglum*, plural *sigla*) means a registered short form used to cite a source; it is the object this register is about.

| Field | Meaning |
|---|---|
| `id` | kebab-case slug derived from the siglum; also the file name |
| `sigel` | the canonical short form (it lives mostly in rank 3–7 texts) |
| `sprache` | language of the canonical form (`de` or `en`) |
| `referenzform` | official reference form — how legal acts cite the source (regulation number, guideline ID) |
| `name` | full title of the document |
| `haerte` | hardness: how firmly the short form is bound to its source (four grades, below) |
| `haerte_geprueft` | `{datum, methode}` for the hardness grade; `methode` is always `einschaetzung` (curated judgement) |
| `gruppe` | group ID from `curation/groups.json` |
| `rang` | rank of bindingness, 1–7 or `null` |
| `identitaet` | `{typ, wert, geprueft}` — anchor on the document, **not** on the version |
| `fassung` | `{stand, konsolidierung, text}` — the version this entry pledges |
| `links` | list of `{label, url, geprueft}` |
| `aliasse` | list of `{form, sprache, evidenz}` — every secondary spelling with its evidence |
| `ersetzt` / `ersetzt_durch` | legal succession: "replaces" / "replaced by", as lists of record IDs |
| `status` | maturity of the record (e.g. `pilot-seed`, `auto-intake`) |
| `statistik` | output only: per spelling, the number of attestations `raw/` holds for it |
| `belegt_durch` | output only: the publishers in whose publications a form of this siglum is attested |

Nested and neighbouring names: `geprueft` = verification status (`datum` date, `methode` method) · `fassung.stand` = as-of date, `fassung.konsolidierung` = consolidated CELEX ID, `fassung.text` = the version statement in the source's own wording · `aliasse[].form` = the spelling, `aliasse[].evidenz` = list of raw record IDs · `herausgeber` = publisher · `quelle` = source · `abgerufen` = retrieved on · `fundstellen` = attestations (the URLs where a form occurs) · `kontext` = surrounding text of a find · `rang_quellen` = ranks of the source documents behind a find · `titel` / `aussage` = a group's title and its load-bearing statement · `domain`, `typ`, `aufgenommen`, `freigabe` = the four descriptive fields of a trusted source.

Closed value vocabularies: `haerte` ∈ `amtlich` (official), `herausgeberueblich` (publisher's own usage), `verkehrsueblich` (established practice), `hausform` (house convention) · `geprueft.methode` ∈ `web-abruf` (fetched), `konstruiert` (constructed), `seed-doksigel` (from the maintainer's curated seed), `spiegel-provenienz` (from mirror provenance), plus `abgeleitet-aus-fassung` (derived from the version) on generated links and `einschaetzung` (judgement) on hardness · `identitaet.typ` ∈ `celex`, `jurabk`, `doc_ref`, `version`, `offen` (open) · watch findings are `veraltet` (outdated) or `unpruefbar` (not checkable).

## The register is curated and growing, not complete

It collects what is actually cited in and around EU and German financial regulation and the adjacent IT and information-security regulation, and its trusted-source base extends to UK and US supervisors. There is no promise of completeness and there cannot be one — the stock grows through reports and curation.

**How firmly an entry sits is stated by the entry itself.** The register does not claim reliability wholesale; it discloses it per entry: `identitaet` names the anchor on the document, `haerte` the binding of the short form to its source, `geprueft` the verification status of each individual claim, and `statistik` the number of attestations `raw/` holds for each spelling. An entry without evidence is recognisable as such.

The register describes legal texts and standards; it does not contain them.

## Four building blocks

- **`raw/`** — the evidence layer: verbatim finds (attestation, retrieval date, method), append-only. **Evidence comes only from original sources** — publications of issuers, regulators and market participants, never from the register operator's own texts: self-citation proves no practice (circularity). **Verbatim local mirrors count as their original source:** the operator keeps a corpus of mirrored original publications carrying origin URL and bindingness rank in the front matter; only record bodies are searched, the attestation is the original URL, and `rang_quellen` records the rank of the source documents. Own texts within such holdings (answers, wiki, analyses, front matter, sidecars) are excluded. Aliases without external evidence are permitted and carry an empty `evidenz` list — the build warns until discovery attests them. Every raw record names the publishing body in `herausgeber` (BaFin, ECB, Bundesbank, EBA, …); the build aggregates this per register entry into the **Belegt durch** column and the `belegt_durch` JSON field.
- **`curation/`** — the decision layer: one record per source, maintained by hand; every decision about siglum, identity and aliases is taken here.
- **`tools/build.py`** — the deterministic build: validates `curation/` against `raw/` and writes sorted output to `dist/` and `docs/`.
- **`tools/watch.py`** — version surveillance: queries the Cellar holdings for every record with a CELEX anchor and reports where the registered consolidation is out of date. Read-only; updates are made by hand.
- **`tools/intake.py`** — ingest of reported sigla: checks a report against its source (`--vorpruefung`) and creates records from it (`--uebernehmen`). See [Reporting and automatic ingest](#reporting-and-automatic-ingest).

The data format is JSON; the schema is YAML-capable, and a switch would change only the serializer.

## Record schema

The mandatory fields are listed in the glossary above. What follows are the rules that the field list alone does not carry.

### Every spelling carries its language

`sprache` stands on the record for the canonical form and on every alias for the secondary form; permitted values are `de` and `en`. German and English short forms of the same source stay distinguishable without having to guess the language from the form — the German DSGVO is GDPR in English, and both forms attest the same document. Where a form is identical in both languages (`DORA`, `CRD IV`) there is nothing to distinguish: it appears once, in the language of its record.

### Identity and version are separate

`identitaet` names the document across its lifetime, `fassung` the state the entry refers to today. For EU law that means `identitaet.wert` carries the **base CELEX** (sector 3, `32013L0036`), while the consolidated CELEX (`02013L0036-20260711`) sits in `fassung.konsolidierung`. The anchor therefore survives a new consolidation — only the version has to be updated.

`fassung.text` is the version statement in the source's own wording; `fassung.stand` is the as-of date in ISO form, but **only where the text states it unambiguously** (patterns "Stand …", "vom …", "Fassung …"). A bare date without a keyword stays `null` — it could be the date of adoption, application or repeal.

### Five anchor types, none of them open

| `typ` | Value | Population |
|---|---|---|
| `celex` | base CELEX, sector 3 | EU legal acts and generation labels |
| `jurabk` | juris abbreviation (`ao_1977`, `hgb`, `kredwg`, `zag_2018`) | German statutes |
| `doc_ref` | the publisher's document reference (`EBA/GL/2019/02`) | guidelines and acts without a CELEX anchor |
| `version` | version label (`v8.1`, `C5:2026`, `V3.1a`) | standards without a document number |
| `offen` | `null` | currently none |

`version` is the weakest anchor: it identifies the version, not the document, and moves with every release. Publishers that issue no document reference (CVSS, EPSS, CIS Controls, PCI DSS, BSI C5, SDM, ENISA TIG) permit nothing better.

### Hardness says how firmly the short form sits

`haerte` distinguishes four grades: **`amtlich`** — formally assigned by the legislator or publisher (juris abbreviation, document reference, standard number); **`herausgeberueblich`** — not assigned, but used by the publisher itself in its own publications; **`verkehrsueblich`** — broad practice without official assignment; **`hausform`** — a convention of this register alone. The grading is **curated judgement until discovery evidence measures it** — which is why `haerte_geprueft` carries the method `einschaetzung` and not `web-abruf`.

**A house form is never canonical while an externally attested form exists.** Where an official or publisher-used form is carried by the source — BaFin, for instance, runs an abbreviation legend in its DORA publications with "RTS RMF", "RTS TPPol", "RTS CCI", "RTS CTIR", "ITS RoI" and "ITS TIR" — that form is the siglum; divergent in-house conventions run as aliases.

### Consolidated EU versions get their link computed

A record with `identitaet.typ: celex` and a set `fassung.konsolidierung` receives the EUR-Lex link to exactly that version **only in the output** (`methode: abgeleitet-aus-fassung`, without a check date — it is computed, not fetched); a curated link with the same URL suppresses it. `curation/` is untouched by this. Without `konsolidierung` no link is generated: the base CELEX page shows the original version, not the registered one.

### Every claim carries its verification status

`geprueft` sits on every link **and** on every identity anchor, as `{datum, methode}` or `null` (unverified). Four methods:

- **`web-abruf`** — target opened and confirmed.
- **`konstruiert`** — built mechanically from an identifier, never fetched; plausible but unproven.
- **`seed-doksigel`** — taken from the operator's curated seed (as of 2026-08-24), with the source's verification status.
- **`spiegel-provenienz`** — URL taken from the provenance front matter of a verbatim local mirror, where it was verified against the document at retrieval time; attested by the mirror, not by a fetch of our own.

The point of the field is exactly this difference: a constructed EUR-Lex link looks like a verified one and is not.

### The usage statistic counts attestations, not documents

Every output record carries `statistik` — per spelling, the number of attestations `raw/` holds for it (canonical siglum and each alias form). Counting runs across all evidence files by form; an empty object means "no attestation", not "not surveyed". `meta.fundstellen_gesamt` gives the total number of attestations in the holdings. Like the derived links, the field arises only in the output — `curation/` stays hand-maintained — and it deliberately does not appear in `SIGEL.md`: evidence density says something about how far this register has surveyed a source, nothing about the source itself.

### The rank carries the hierarchy of bindingness

`rang` carries the level of bindingness: **1** binding law of one's own legal order (EU regulations, directives, national statutes) · **2** delegated and implementing acts · **3** guidelines and consulted circulars (MaRisk, BAIT) · **4–7** Q&As, preparatory material, supervisory communications, rolling web communication (currently unpopulated) · **`null`** ("—") standards and practices without legal binding. The numbers are identical to those of the corpus rank model from which the mirror evidence comes, and to the public [dora-graph](https://github.com/gnosifex/dora-graph) — register and graph are interoperable. Rank and grouping intersect deliberately: `gruppe` orders by publisher and mechanism of effect, `rang` by binding force — rank 1 sits in three groups.

## Grouping follows descending bindingness

`curation/groups.json` holds the groups as an ordered list, each with a title and a load-bearing statement; the order there is the order of the output and follows decreasing regulatory bindingness — from EU regulations through delegated acts, directives, European and national supervisory requirements, down to voluntary standards. Every record names its group in `gruppe`; the build rejects unknown groups and empty groups. A one-member group is permitted if it carries a mechanism of effect of its own (`eu-richtlinien`).

## Triage: only citable documents get in

A register entry is created only for what resolves to a **citable document with an identity anchor**. Pure subject-matter abbreviations (SBOM, ICT, ISMS) denote no source and are never admitted.

**Generation labels are entries in their own right.** Whoever writes `CRD V` or `CRR III` means a particular version of the base act, not the act as it stands today — the label is therefore a siglum itself and gets its own record. It carries the **base CELEX of the act** as identity (`CRD IV`–`CRD VI` → `32013L0036`, `CRR II`/`CRR III` → `32013R0575`), names in `fassung.text` the amending act that constitutes the generation, and links it. `fassung.konsolidierung` stays empty: a generation spans several consolidated versions, and no single one of them *is* the generation. The generations of a family are chained through `ersetzt`/`ersetzt_durch`; the stem records `CRD` and `CRR` stand alongside as act entries at today's state and do not chain. Spelling variants (`CRDIV`, `CRD 4`) are aliases of the respective generation record as soon as discovery attests them.

**Every report names its source.** Whoever reports a new entry names the original attestation as a URL; a report without a source is not admitted. Checking against exactly that source is the act of admission, and it produces the new entry's first raw evidence record at the same time.

## Reporting and automatic ingest

**Reported by issue, checked by the Action, admitted by a daily routine, merged only on green CI — with no human in the loop.** The admission rule of this register is a source rule, and a source rule is machine-executable: if the reported short form occurs verbatim in the named original attestation and that attestation is a released trusted source, the entry is attested; if either is missing, it is not.

```sh
gh issue create --repo gnosifex/reg-sigel --template siglum-report.yml
```

### Two fields are the entire attack surface

The report form asks for **short form** (at most 25 characters) and **source URL** (at most 200 characters), and nothing else. All foreign text that ever enters processing is thereby capped at **225 validated characters**; everything else — official reference form, full title, identity anchor, publisher, group, rank — comes from the verified source, from `curation/trusted-sources.json`, or from curation. Exceeding the limits is a rejection naming field, actual length and limit.

### Four stages, each with its own responsibility

**Stage 1 — the report.** The issue form `.github/ISSUE_TEMPLATE/siglum-report.yml` asks for the two mandatory fields.

**Stage 2 — pre-check by the Action.** `.github/workflows/intake.yml` runs on every opened or edited issue labelled `sigel-meldung` and calls `tools/intake.py --vorpruefung`. That check is deterministic (mandatory fields, lengths, siglum and URL syntax, collision against `curation/`), fetches the source — HTML directly, PDF through `pdftotext` — and searches for the short form verbatim. The result is the **artifact**: a bot comment carrying the marker `<!-- intake-artefakt v1 -->`, the check report and the outcome as JSON, together with the context lines the Action itself cut from the fetched source text. The Action **writes nothing** to the repository and needs no push rights.

It decides three ways:

- **passed** → label `vorgeprueft-ok`, issue stays open;
- **formally deficient, short form not attested in the source, or source not on the trusted-source list** → label `abgelehnt` and close;
- **collision with an existing record** → label `wartet-maintainer`.

**Attestation and released domain are jointly the condition.** A source outside the trusted list is rejected, with a pointer to the trusted-source process; the `wartet-maintainer` label applies only when an existing record would be affected.

**Stage 3 — admission by the daily routine.** A scheduled Claude Code agent works through all open `vorgeprueft-ok` issues following `tools/routine-intake.md`. It reads **only the artifact** — the most recent comment carrying the marker whose author is `github-actions[bot]` — never the issue title, body, or third-party comments. The reason is the provenance of the text: the raw text is attacker-controlled, the artifact is syntax-checked, length-limited and verified against the source.

The routine supplies what requires judgement: triage (is this a source siglum at all?), determination of reference form, full title and identity anchor from the source, and a reasoned assignment of group and rank. It then calls `python tools/intake.py --uebernehmen --artefakt …` with exactly those inputs. The script creates the curation record (`status: auto-intake`, `haerte: verkehrsueblich` as a judgement) and the raw evidence record from its own fetch, then calls `build.py` — **only on exit 0 is anything committed**, the build being the last gate. Where the identity anchor cannot be established with confidence, nothing is guessed: `wartet-maintainer`.

**Stage 4 — merge only on green CI.** The routine works on a branch `intake/<date>`, opens a pull request and enables auto-merge. It never commits to `main` and never merges itself. Merging happens only once `intake-guard` and `build` are green.

### The guard turns the guardrail into a condition

`tools/intake_guard.py` checks the diff against the base on every pull request and lets exactly three things through:

- new files under `curation/` (except `groups.json` and `trusted-sources.json`) and under `raw/`,
- **field-wise pure additions** to existing curation records: new alias entries and new evidence IDs in existing aliases, with no other field changed,
- the freshly built state of `dist/` and `docs/`.

Everything else — `tools/`, `.github/`, `README.md`, `groups.json`, `trusted-sources.json`, changes to existing fields, renames, deletions — ends the run with exit 1 and a list of findings.

That is the difference between a promise and a condition: an instruction text is a request, and a sufficiently clever piece of foreign text could subvert it. The guard does not ask what was meant, it asks what is in the diff. Checkable locally:

```sh
python3 tools/intake_guard.py --selbsttest
python3 tools/intake_guard.py --basis origin/main
```

### Seven guardrails carry the automation

- **Source mandatory.** No attestation, no admission — and the attestation is fetched, not believed.
- **Minimal attack surface.** 225 validated characters of reporter input; everything else comes from verified sources or from curation.
- **The artifact instead of the raw text.** The routine never processes what a stranger wrote, only what the Action checked out of it.
- **Additive-only, twice over.** The script compares the changed file field by field against the original and aborts if anything moved outside `aliasse`; the guard checks the same thing again on the diff.
- **The trusted-source list.** Only attestations on curated domains count as evidence (see below).
- **`status: auto-intake` and the rate brake.** Automatically created records are recognisable by their status; more than ten `auto-intake` commits on the same day, and admission switches to `wartet-maintainer`.
- **The issue is the audit trail.** Report, artifact, decision and commit subject sit in one place and are publicly readable.

The chain is checkable locally with the fixtures under `tools/tests/` — one for the load-bearing case, three for the rejection grounds:

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

`--dry-run` makes `--uebernehmen` work on a copy of the repository in a temporary directory and leaves the holdings untouched.

### The trusted-source list is the only stage with a human in the loop

`curation/trusted-sources.json` holds the domains whose publications the ingest accepts as evidence — per entry `domain`, `herausgeber` (publisher), `typ` (`eu-behoerde`, `eu-amtsveroeffentlichung`, `nationale-aufsicht`, `notenbank`, `us-aufsicht`, `gesetzesportal`, `normungsorganisation`), `aufgenommen` (added on) and `freigabe` (release). It is configuration like `groups.json`, not a record; the build validates mandatory fields and uniqueness of domains along with everything else. Subdomains are covered by their domain.

The current holdings are a **maintainer seed** (`freigabe: maintainer-seed`) spanning the EU authorities and official EU publication services, the national supervisors and central banks of the EU member states, the United Kingdom and the US banking supervisors, plus the relevant standards bodies. **The domains are not individually verified** — the seed is a setting, not a check finding; corrections run through the same trusted-source process as extensions.

**Only the maintainer extends or corrects the list.** Proposals are made by issue (`.github/ISSUE_TEMPLATE/trusted-source-proposal.yml`, label `pruefquelle-vorschlag`); the Action marks such issues `wartet-maintainer` and does nothing else. **The daily routine does not touch them** — not even to pre-check or comment. They are worked only in a maintainer session, which answers two questions with evidence: is the domain the official presence of the claimed publisher, and does that publisher issue regulation or standards? The reason for the separation is one line long: whoever controls the trusted sources controls the register — the object level is automated, the trust level is not.

## Open modelling questions

**Legal succession so far reaches only inside the CRD and CRR families.** `ersetzt` and `ersetzt_durch` chain the generation records; all other records leave the fields empty. The superseding and superseded documents named in their version texts — MaRisk RS 06/2024, EBA/GL/2026/06 — are not records themselves: a version is admitted only if it carries an established siglum of its own, and that does not hold for predecessor circulars.

**The banking directives before CRD IV are missing.** `CRD I`–`CRD III` denote versions of the predecessor base acts 2006/48/EC and 2006/49/EC, not of Directive 2013/36/EU; they therefore need identity anchors of their own and are deliberately not yet created. Whoever adds them attaches them to `crd-iv` through `ersetzt_durch`.

**`version` as an anchor remains a makeshift** — see above; a switch to a real document anchor is possible only if a publisher issues one.

**Version surveillance reaches only part of the holdings.** `watch` covers the records with a CELEX anchor; for `doc_ref`, `jurabk` and `version` there is no comparable version list, and they stay under manual control.

## Checking versions

```sh
python3 tools/watch.py [--json <path>]
```

`watch` queries the consolidated versions of the base act for every record with `identitaet.typ: celex` and compares the most recent one with `fassung.konsolidierung`. It **never writes** to `curation/` or `dist/`: a finding is an instruction to the hand-maintained layer. Exit 1 as soon as a record is `veraltet` (outdated); `unpruefbar` (not checkable) stays a warning.

**Two routes, in this order.** The default is a SPARQL query to `https://publications.europa.eu/webapi/rdf/sparql`, which returns all CELEX identifiers for the consolidation prefix (`32013L0036` → `02013L0036-`) — responses in the kilobyte range. If it fails, `watch` fetches the notice XML of the base act (`Accept: application/xml;notice=branch`, some 1–3 MB) and extracts the identifiers by regex. The notice route additionally needs `Accept-Language: deu`; without that header the Cellar answers HTTP 400. The website route to EUR-Lex remains blocked for automated fetching.

**Limits.** Queries run sequentially, at most one request per second, with an honest user agent. `watch` checks whether *a more recent consolidation exists* — not whether it is materially relevant; the decision to update a record stays curatorial. If a record carries no consolidation but the Cellar does, it counts as `veraltet`. If the registered version is absent from the Cellar list, it counts as `unpruefbar` — that is a data finding, not a network error.

## Building

```sh
python3 tools/build.py    # repeatable; exit 1 on validation errors
```

The build checks uniqueness of `id` and `sigel`, the language of every spelling, freedom from collision between alias forms and foreign sigla, the resolvability of every `evidenz` reference into `raw/`, the structure of `fassung` and of every `geprueft` block, the hardness grade against its value list, the group assignment against `groups.json`, and the resolvability of `ersetzt`/`ersetzt_durch` onto existing record IDs. It also checks `trusted-sources.json` for complete entries and unique, well-formed domains — `groups.json` and `trusted-sources.json` are configuration of the curation layer and are never read as records. `identitaet.typ: offen` is a warning, not an error. No network access; research changes only `curation/`. `dist/` and `docs/` are committed so that diffs show the effect of a curation change.

Alongside these lie the migration scripts (`migrate_v2.py`, `migrate_haerte.py`, `migrate_gruppen.py`, `seed_aus_sigeltabelle.py`). They stay in the repository because each is the executable description of one schema change, and they run as no-ops on migrated holdings. None of them re-seeds — the curation state is hand-edited.

### The static page is the same table without a renderer, in two languages

`docs/index.html` (English) and `docs/de.html` (German) are produced in the same run: each a single file, no script, no external asset — title, core statement, then per group a heading, a statement and a table with clickable source links, plus date and licence in the footer. A plain link at the top right switches between the two, which is why no JavaScript is needed. Language-dependent is the frame only — title, core statement, column heads, group titles and statements, footer, and the display labels of the hardness grade; the data cells are identical in both versions and stay in the language of their sources, as does the schema. Both come from the same build: `curation/groups.json` carries each group in both languages, and the build refuses a group that is missing one. What the browser loads is fully contained in the one file; the tables scroll horizontally inside their own frame instead of breaking the page. To view them locally:

```sh
python3 -m http.server --directory docs 8000
```

## CI keeps the committed output honest

`.github/workflows/build.yml` runs on `push` and `pull_request`, builds, verifies with `git diff --exit-code dist/` that the committed output matches curation, and proves determinism with a second run plus a byte comparison. `.github/workflows/intake-guard.yml` runs on pull requests and enforces the ingest guardrails. `watch` does **not** run in CI: it needs network access to the Cellar, and a third-party service has no business in the success path of the build.

## Licence — reuse and mirroring are welcome

The register is published under **CC BY 4.0** with attribution to **"gnosifex"**. Licence text at [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/legalcode); terms and scope in [LICENSE](LICENSE).

**Reuse, redistribution and mirroring into other repositories are explicitly welcome and covered by the licence.** You may copy and redistribute the material in any medium or format, and remix, transform and build upon it, including commercially — provided you give attribution: name the author ("gnosifex"), link the licence, and indicate whether changes were made. Suggested attribution: `Quellen-Sigel-Register, gnosifex, CC BY 4.0, https://creativecommons.org/licenses/by/4.0/`

The cited legal texts and standards themselves are not covered by this licence — the register describes them, it does not contain them. For those, the terms of their respective publishers apply.
