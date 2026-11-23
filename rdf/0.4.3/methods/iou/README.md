IOU is a set of middleware solutions in development for organizations comprising of a Operaton DMN server, a CPSV Editor, Linked Data Explorer, IOU API's, a Dashboard behind a Keycloack login and a CPRMV API. See https://iou-architectuur.open-regels.nl/nl/. 

**Supported Rule Set Formats:**

1. **Operaton server at operaton.open-regels.nl:**
 - Format: `DMN1.3_{deploymentid}R{resourceid}_{date}_{index}` (A date and index must be provided but are not used)
 - Example: `DMN1.3_e62cb254-0e74-11f1-a5e9-f68ed60940f5Re62cb255-0e74-11f1-a5e9-f68ed60940f5_2026-01-01_1, LiteralExpression_2021`
 - Fetches from: http://operaton.open-regels.nl/

2. **IOU Norms API at open-regels.nl:**
 - Format: `IOU-NORMS_{rulesetid}_{date}_{index}` (A date and index must be provided but are not used)
 - Example: `IOU-NORMS_BWBR0015703_2026-01-01_1`
 - Fetches from: http://operaton.open-regels.nl/
