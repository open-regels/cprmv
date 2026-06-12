# CPRMV 0.4.1 SHACL compliance fix

This note documents why the CPRMV Rules Serve API output did not validate against
its own 0.4.1 SHACL shapes (`rdf/0.4.1/cprmv.shacl.ttl`) and what was changed to make
it conformant. It is the SHACL counterpart of `SSL_FIX.md`.

## Symptom

A CPRMV `RuleSet` served by the API (e.g. `GET /rules/BWBR0015703, Artikel 20, onderdeel a.?format=turtle`)
did not conform to `cprmv.shacl.ttl`. In practice the shapes appeared to "pass" only
because **no nodes were even targeted** — see the root cause below.

## Root cause

### 1. Namespace had a stray `/` before `#`

The ontology and shapes declare the vocabulary namespace as:

```
https://standaarden.open-regels.nl/standards/cprmv/0.4.1#
```

but the Python constant and every XSLT declared it with an extra slash:

```
https://standaarden.open-regels.nl/standards/cprmv/0.4.1/#      ← wrong
```

`…/0.4.1/#RuleSet` is a **different IRI** than `…/0.4.1#RuleSet`. The Python constant
and the XSLT output were wrong *in lockstep*, so the API ran fine, but every emitted
node landed in the wrong namespace and was invisible to the shapes' `sh:targetClass`.
Validation therefore matched nothing instead of validating the rules.

### 2. Structural gaps versus the shapes

Even with the namespace corrected, the output violated `RuleSetShape`:

| Issue | Shape expectation | Was emitted |
|-------|-------------------|-------------|
| `cprmv:output-of` | property is `cprmv:isOutputOf` (`sh:class cpsv:PublicService`) | `cprmv:output-of` (not in the vocabulary) |
| missing `cprmv:validFrom` | required (`minCount 1`, `xsd:date`) | not emitted (date only in `tooibwb:inwerkingtreding`) |
| `cprmv:isBasedOn <publication-url>` | `isBasedOn` range is `cprmv:RuleSet` | pointed at the raw source-publication URL (not a RuleSet) |
| `cprmv:hasMethod <…/methods/bwb>` | value must be a typed `cprmv:RuleMethod` carrying `cprmv:id` | method only defined in a separate graph; not present in the served description, and typed only as a subtype (e.g. `AnalysisMethod`) — the validator does no `rdfs:subClassOf` reasoning |

## Fixes

All changes are confined to the served pipeline (`serve_api/`), with the canonical
`rdf/0.4.1/` and `serve_api/respec/0.4.1/rdf/` copies kept in sync.

1. **Namespace** — removed the stray `/` in `…/cprmv/0.4.1/#` → `…/cprmv/0.4.1#`, atomically
   across `src/utils/constants.py` (the `CPRMV` navigation constant), the four served
   transforms (`data/{bwb,cvdr,dmn13operaton,fmx4cellar}2cprmv.xsl`), and `data/cprmvmethods.ttl`
   (plus the `rdf/0.4.1/` and `respec/0.4.1/rdf/` copies). The constant and the XSLT output
   must match, since `serve.py` navigates the parsed graph with `CPRMV.*`.

2. **`output-of` → `isOutputOf`** in the transforms (the value was already a typed
   `[ a cpsv:PublicService ]`).

3. **Added `cprmv:validFrom "…"^^xsd:date`** to each `RuleSet` — BWB from `@inwerkingtreding`,
   CVDR from `overheidrg:inwerkingtredingDatum`.

4. **`cprmv:isBasedOn <publication-url>` → `prov:wasDerivedFrom <publication-url>`** — the
   source publication is not a derived `cprmv:RuleSet`, and the ontology already declares
   `cprmv:isBasedOn rdfs:subPropertyOf prov:wasDerivedFrom`. `cprmv:isBasedOn` is reserved
   for genuine RuleSet-to-RuleSet lineage.

5. **`hasMethod` typing** — `serve.py` (`get_rules`) now folds the referenced method's
   `rdf:type cprmv:RuleMethod` and `cprmv:id` into the non-JSON (Turtle/N3/XML) output, so the
   served description is self-contained and satisfies both the `hasMethod` class check and
   `RuleMethodShape`. (`cprmv:comment` is intentionally omitted — it is language-tagged and
   `RuleMethodShape` constrains `comment` to `xsd:string`.) The `dmn13` transform is also
   retyped `RuleSet` → `DecisionModel` and its `cprmv:method` corrected to `cprmv:hasMethod`.

## Verification

- **SHACL**: transforming the committed sample `tools/bwb2cprmv/BWBR0015703_2025-07-01_0.xml`
  through the fixed `bwb2cprmv.xsl` (mirroring `serve.py`'s method injection) and validating
  with pySHACL against `rdf/0.4.1/cprmv.shacl.ttl` reports **0 violations**.
- **Unit tests**: `pytest test` — the namespace-sensitive `detect_*` assertions pass; the
  `test_get_rules` expectation was updated to the corrected namespace/structure.
- **Live**: `GET /rules/BWBR0015703, Artikel 20, onderdeel a.?format=turtle` returns a
  `RuleSet` with the `…/0.4.1#` namespace, `validFrom`^^xsd:date, `isOutputOf`,
  `prov:wasDerivedFrom`, an RDF-list `hasPart`, and `<…/methods/bwb> a cprmv:RuleMethod ; cprmv:id "bwb"@nl`.

## Known follow-ups (out of scope here)

- **FMX4 (EU CELLAR)** `validFrom`: no reliable source date is wired into
  `fmx4cellar2cprmv.xsl` yet; a `# TODO` marks where to add it. Until then a CELLAR `RuleSet`
  still misses the required `validFrom`.
- **Legacy dev/sample transforms** (`tools/bwb2cprmv/bwb-toestand2cprmv.xsl` — still on the
  `0.3.0` namespace — and `example/wetten.nl.xml2cprmv.xsl`) are not used by the served
  pipeline and were left untouched.
- The custom `cprmv-json` format keeps `hasMethod` as a bare URL (no inline `RuleMethod`
  typing); the typing is only added to the RDF serializations that SHACL validates.
