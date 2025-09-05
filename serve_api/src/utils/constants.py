from rdflib import Namespace
from typing import Union
from fastapi import Path, Query


RULE_ID_PATH_DESCRIPTION = """
The Rule ID Path consisting of the Rule Set ID followed by a comma-separated path of rule identifiers.
        
**Format:** `{RuleSetId}, {RuleId1}, {RuleId2}, ...`
        
**Examples:**
- `BWBR0015703_2025-07-01_0, Artikel 20, onderdeel a.`
- `CVDR712517_1, Hoofdstuk 2, Artikel 5`
- `CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2, Article 1`
        
**Supported Rule Set Formats:**
        
1. **BWB (Dutch Law Repository):**
- Format: `{BWB_ID}_{DATE}_{INDEX}`
- Example: `BWBR0015703_2025-07-01_0`
- Fetches from: https://repository.officiele-overheidspublicaties.nl/bwb/
        
2. **CVDR (Dutch Municipal Regulations):**
- Format: `{CVDR_ID}_{INDEX}`
- Example: `CVDR712517_1`
- Fetches from: https://repository.officiele-overheidspublicaties.nl/cvdr/
        
3. **EU CELLAR (European Publications):**
 - Format: `CFMX4{CELLAR_ID}_{ITEM_ID}`
 - Example: `CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2`
 - Fetches from: http://publications.europa.eu/resource/cellar/
        
**Rule Path Navigation:**
        
 - Rule identifiers are matched **case-sensitively** but **all non alphanumeric characters (including whitespace) are ignored**
 - Uses **depth-first search** for the first matching rule
 - Intermediate rule IDs can be omitted for convenience
 - Path `"Artikel 20, onderdeel a)"` finds the same result as `"Artikel 20,lid1, onderdeel a."`
 - To target specific nested rules, include all intermediate identifiers
        
 **URL Encoding Note:** Remember to URL-encode special characters in the path when making requests.
 """

CPRMV = Namespace("https://cprmv.open-regels.nl/0.3.0/")
CPRMVSERVE = Namespace("https://cprmv.open-regels.nl/0.3.0/serve-api/")
CPRMVMETHODS = Namespace("https://cprmv.open-regels.nl/0.3.0/methods/")

RULE_ID_PATH: str = Path(
    min_length=10,
    max_length=500,
    description=RULE_ID_PATH_DESCRIPTION,
    example="BWBR0015703_2025-07-01_0, Artikel 20, onderdeel a.",
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
    description="Pattern for extracting specific values from rule definitions using parse syntax (e.g., '{situatie:param_value}: € {norm:param_value}')",
    example="{situatie:param_value}: € {norm:param_value}",
)
