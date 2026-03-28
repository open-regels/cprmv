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
        
**Supported Rule Set Formats:**
        
1. **BWB (Dutch Law Repository):**
- Format: `{BWB_ID}_{DATE}_{INDEX}` : retrieves the specific indicated version published on the given date with given index number
- Example: `BWBR0015703_2025-07-01_0`
- Format: `{BWB_ID}_{DATE}_latest` : Retrieves the version valid on the date specified
- Example: `BWBR0015703_2025-07-02_latest`
- Format: `{BWB_ID}` : Retrieves the version valid on the current day
- Example: `BWBR0015703`
- Fetches from: https://repository.officiele-overheidspublicaties.nl/bwb/
        
2. **CVDR (Dutch Municipal Regulations):**
- Format: `{CVDR_ID}_{INDEX}` : retrieves the specific indicated with the given index number
- Example: `CVDR712517_1`
- Format: `{CVDR_ID}_{DATE}_latest` : Retrieves the version valid on the date specified
- Example: `CVDR712517_2025-07-02_latest`
- Format: `{CVDR_ID}` : Retrieves the version valid on the current day
- Example: `CVDR712517`
- Fetches from: https://repository.officiele-overheidspublicaties.nl/cvdr/
        
3. **EU CELLAR (European Publications):**
 - Format: `CFMX4{CELLAR_ID}_{ITEM_ID}`
 - Example: `CFMX483e4752e-f2e5-11e8-9982-01aa75ed71a1.0017.02_DOC_2`
 - Fetches from: http://publications.europa.eu/resource/cellar/
 
Note that for CMFX4 finding the version on a specific date is not supported yet.
        
**Rule Path Navigation:**
        
 - Rule identifiers are matched **case-sensitively** but **all non alphanumeric characters (including whitespace) are ignored**
 - Uses **depth-first search** for the first matching rule
 - Intermediate rule IDs can be omitted for convenience
 - Path `"Artikel 20, onderdeel a)"` finds the same result as `"Artikel 20,lid1, onderdeel a."`
 - To target specific nested rules, include all intermediate identifiers
        
 **URL Encoding Note:** Remember to URL-encode special characters in the path when making requests.
 """

CPRMV = Namespace("https://standaarden.open-regels.nl/standards/cprmv/0.4.0/#")
CPRMVSERVE = Namespace("https://cprmv.open-regels.nl/0.4.0/serve-api/")
CPRMVMETHODS = Namespace("https://cprmv.open-regels.nl/0.4.0/methods/")

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
