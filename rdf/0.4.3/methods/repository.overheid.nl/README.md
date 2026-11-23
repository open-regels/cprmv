# repository.overheid.nl

The repository.overheid.nl method is an official Dutch publication method (a web repository for official publications) for legal rulesets that are the output of the BWB and CVDR methods.

**Supported Rule Set Id formats:**

1. **BWB (Dutch Law Repository):**
- Format: `{BWB_ID}_{DATE}_{INDEX}` : retrieves the specific indicated version published on the given date with given index number
- Example: `BWBR0015703_2025-07-01_0` ([open with CPRMV API /rules endpoint](/rules/BWBR0015703_2025-07-01_0),[open with CPRMV API /raw endpoint](/raw/BWBR0015703_2025-07-01_0))
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
