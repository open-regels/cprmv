from rdflib import Namespace
from typing import Union
from fastapi import Path, Query


RULE_ID_PATH_DESCRIPTION = """
The Rule ID Path consisting of the Rule Set ID followed by a comma-separated path of rule identifiers.

**Format:** `{RuleSetId}, {RuleId1}, {RuleId2}, ...`

**Examples:**
- `BWBR0015703_2025-07-01_0, Artikel 20, onderdeel a.`
- `CVDR677883, Artikel 5`
- `CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2, Artikel 1`
- `DMN1.3_e62cb254-0e74-11f1-a5e9-f68ed60940f5Re62cb255-0e74-11f1-a5e9-f68ed60940f5_2026-01-01_1, LiteralExpression_2021` (A date and index must be provided but are not used)
- `IOU-NORMS_BWBR0015703_2026-01-01_1` (a date and index must be provided but are not used)
- `ROO_2026-01-01_1` (Whole list of organisations. Note that this is a very heavy request which takes time to load. Pagination support will be added lateron. A date and index must be provided but are not used.)
- `ROOURIhttps%3A%2F%2Fidentifier.overheid.nl%2Ftooi%2Fid%2Fgemeente%2Fgm1926_2026-01-01_1` (use the URL encoded TOOI URI after the ROOURI prefix. A date and index must be provided but are not used)
- `ROO.organisatiecode=gm1926_2026-01-01_1` (retrieve a organisation by a known key and value. For instance organisatiecode as key. A date and index must be provided but are not used.)
- `DSO_14_2026-01-01_1` (NOTE: the methods in the dso module require Authorization by setting a x-api-key header. See the dso module documentation.)

**Rule Path Navigation:**

 - Rule identifiers are matched **case-sensitively** but **all non alphanumeric characters (including whitespace) are ignored**
 - Uses **depth-first search** for the first matching rule
 - Intermediate rule IDs can be omitted for convenience
 - Path `"Artikel 20, onderdeel a)"` finds the same result as `"Artikel 20,lid1, onderdeel a."`
 - To target specific nested rules, include all intermediate identifiers

 **URL Encoding Note:** Remember to URL-encode special characters in the path when making requests.
 """

CPRMV = Namespace("https://standaarden.open-regels.nl/standards/cprmv/0.4.3#")
CPSV = Namespace("http://purl.org/vocab/cpsv#")
CPRMVSERVE = Namespace("https://cprmv.open-regels.nl/0.4.3/serve-api/")
CPRMVMETHODS = Namespace("https://cprmv.open-regels.nl/0.4.3/methods/")
COREAPI = Namespace("https://cprmv.open-regels.nl/0.4.3/methods/core-api#")

RULE_ID_PATH: str = Path(
    min_length=10,
    max_length=500,
    description=RULE_ID_PATH_DESCRIPTION,
    examples=["BWBR0015703_2025-07-01_0, Artikel 20, onderdeel a."],
)
PATH_DELIMITER: str = Query(
    default=",",
    description="Delimiter used to separate rule identifiers in the path",
)
FORMAT: str = Query(
    default="cprmv-json",
    description="Output format for the rule data (cprmv-json, json-ld, xml, turtle, ttl, n3, turtle2)",
)
LANGUAGE: Union[str, None] = Query(
    default=None,
    description="Language for the output (currently only 'nl' is supported)",
)
UNFORMAT: str = Query(
    default="",
    description="If specified will imply format=cprmv-json. Pattern for extracting specific values from rule definitions using parse syntax (e.g., '{situatie:param_value}: € {norm:param_value}')",
    examples=["{situatie:param_value}: € {norm:param_value}"],
)

# returns a version of the given uri that ignores a (CPRMV) version indication within the namespace
def anyVersionOf(ns):
    splitted = ns.split('#')
    if len(splitted) > 1:
        return splitted[1]
    return ns
