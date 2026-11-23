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
  publishDate: "2026-11-06",
  publishVersion: "0.4.4",

  previousPublishVersion: "0.4.3",
  previousPublishDate: "2026-11-23",
  previousMaturity: "fpwd",
  title: "CPRMV",
  subtitle:
    "Core Public Rule Management Vocabulary (CPRMV), extending the Interoperable Europe standards towards a standard for Public Rule Management",

  // Content
  content: { ch01: "informative", ch02: "informative", ch03: "conformance", methods: "conformance", modules: "conformance", api: "conformance"},
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
      name: "Bas Kaptijn",
      url: "https://www.ictu.nl",
    },
    {
      name: "Marco Brattinga",
      url: "https://www.soprasteria.com",
    },
    {
      name: "Steven Gort",
      url: "https://www.ictu.nl",
    },
    {
      name: "Andre van Brussel",
      url: "https://www.ictu.nl",
    },
  ],
  // Note that github and gitlab urls are compatible (except for the pulls), however respec prevents gitlab url's to be set
  github: "https://github.com/standards/cprmv/",

  // Create PDF and link to file in header (optional):
  alternateFormats: [
    {
      label: "pdf",
      uri: "./cprmv.pdf",
    },
  ],
};
