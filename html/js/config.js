let respecConfig = {
  // Config parameters
  useLogo: true,
  useLabel: true,
  license: "CC0",
  specStatus: "fpwd",
  specType: "ST",
  pubDomain: "ronl",

  // shortName = Repository name
  shortName: "cprmv",
  publishDate: "2025-06-27",
  publishVersion: "0.3.0",

  previousPublishVersion: "0.2.0",
  previousPublishDate: "2025-03-27",
  previousMaturity: "fpwd",
  title: "CPRMV",
  subtitle:
    "Core Public Rule Management Vocabulary (CPRMV), extending the Interoperable Europe standards towards a standard for Public Rule Management",

  // Content
  content: { ch01: "informative", ch02: "informative" },
  editors: [
    {
      name: "Steven Gort",
      mailto: "steven.gort@ictu.nl",
      company: "ICTU",
      companyURL: "http://www.ictu.nl",
    },
    {
      name: "Bas Kaptijn",
      mailto: "bas.kaptijn@ictu.nl",
      company: "ICTU",
      companyURL: "http://www.ictu.nl",
    },
  ],
  authors: [
    {
      name: "Steven Gort",
      url: "https://www.ictu.nl",
    },
    {
      name: "Bas Kaptijn",
      url: "https://www.ictu.nl",
    },
    {
      name: "Andre van Brussel",
      url: "https://www.ictu.nl",
    }
  ],
  // Note that github and gitlab urls are compatible (except for the pulls), however respec prevents gitlab url's to be set
  github: "https://github.com/standards/cprmv/",

  // Create PDF and link to file in header (optional):
  alternateFormats: [
    {
      label: "pdf",
      uri: "https://www.open-regels.nl/cprmv/0.3.0/snapshot.pdf",
    },
  ],
};
