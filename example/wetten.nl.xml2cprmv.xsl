<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="text" indent="no"/>
  
  <xsl:template match="text()"/>
  
  <xsl:template match="/toestand">
    <xsl:text>VERSION "1.2"
BASE :&lt;http://example.com/&gt;
PREFIX cpsv: &lt;http://purl.org/vocab/cpsv#&gt;
PREFIX cprmv: &lt;https://cprmv.open-regels.nl/0.3.0/&gt;
PREFIX cprmvmethods: &lt;https://cprmv.open-regels.nl/0.3.0/methods/&gt;
PREFIX overheid: &lt;http://standaarden.overheid.nl/owms/terms/&gt;
PREFIX tooibwb: &lt;https://identifier.overheid.nl/tooi/thes/bwb&gt;
&lt;http://opencatalogi.open-regels.nl/</xsl:text><xsl:value-of select="concat(./@bwb-id,'-',./@inwerkingtreding)"/><xsl:text>&gt; a cprmv:RuleSet;
    cprmv:extends &lt;https://identifier.overheid.nl/tooi/id/bwb/</xsl:text><xsl:value-of select="./@bwb-id"/><xsl:text>&gt;;
    cprmv:id "</xsl:text><xsl:value-of select="concat(./@bwb-id,'-',./@inwerkingtreding)"/><xsl:text>";
    cprmv:method cprmvmethods:bwb;
    cprmv:output-of [
        a cpsv:PublicService;
        cprmv:id &lt;https://identifier.overheid.nl/tooi/id/upl/bwb/</xsl:text><xsl:value-of select="./@bwb-id"/><xsl:text>&gt;
        cprmv:providedBy [ overheid:authority "Sociale Zaken en Werkgelegenheid" ];
        cpsv:produces &lt;http://opencatalogi.open-regels.nl/</xsl:text><xsl:value-of select="concat(./@bwb-id,'-',./@inwerkingtreding)"/><xsl:text>&gt;
    ];
    tooibwb:id </xsl:text><xsl:value-of select="./@bwb-id"/><xsl:text>";
    tooibwb:inwerkingtreding "</xsl:text><xsl:value-of select="./@inwerkingtreding"/><xsl:text>";
    cprmv:contains (</xsl:text><xsl:apply-templates select="./wetgeving/wet-besluit/wettekst/hoofdstuk"/><xsl:text>).
</xsl:text>
  </xsl:template>

  <xsl:template match="hoofdstuk"><xsl:text>[
        a cprmv:Rule;
        cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:if test="./al"><xsl:text>"@nl;
        cprmv:definition "</xsl:text><xsl:value-of select="./al"/><xsl:text>"</xsl:text></xsl:if><xsl:if test="paragraaf|artikel"><xsl:text>;
        cprmv:contains (</xsl:text><xsl:apply-templates select="paragraaf|artikel"/><xsl:text>)</xsl:text></xsl:if><xsl:text>
    ]</xsl:text>
  </xsl:template>
  
  <xsl:template match="paragraaf"><xsl:text>[
            a cprmv:Rule;
            cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:if test="./al"><xsl:text>"@nl;
            cprmv:definition "</xsl:text><xsl:value-of select="./al"/><xsl:text>"@nl</xsl:text></xsl:if><xsl:if test="./artikel"><xsl:text>;
            cprmv:contains (</xsl:text><xsl:apply-templates select="artikel">
                <xsl:with-param name="indent" select="true()"/>
            </xsl:apply-templates><xsl:text>)</xsl:text></xsl:if><xsl:text>
        </xsl:text>
  </xsl:template>
  
  <xsl:template match="artikel"><xsl:param name="indent" select="false"/><xsl:text>[
            </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>a cprmv:Rule;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:if test="./al"><xsl:text>"@nl;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:definition "</xsl:text><xsl:value-of select="./al"/><xsl:text>"@nl</xsl:text></xsl:if><xsl:if test="./lid"><xsl:text>;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:contains (</xsl:text><xsl:apply-templates select="lid">
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:apply-templates><xsl:text>)</xsl:text></xsl:if><xsl:text>
        </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>]</xsl:text>
  </xsl:template>
  
  <xsl:template match="lid"><xsl:param name="indent"/><xsl:text>[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:id "lid </xsl:text><xsl:value-of select="./lidnr"/><xsl:if test="./al"><xsl:text>"@nl;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:definition "</xsl:text><xsl:value-of select="./al"/><xsl:text>"@nl</xsl:text></xsl:if><xsl:if test="./lijst/li"><xsl:text>;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:contains (</xsl:text><xsl:apply-templates select="lijst/li">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text>)</xsl:text></xsl:if><xsl:text>
            </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>]</xsl:text>
  </xsl:template>
  
  <xsl:template match="lijst/li"><xsl:param name="indent"/><xsl:text>[
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>a cprmv:Rule;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:id "onderdeel </xsl:text><xsl:value-of select="./li.nr"/><xsl:if test="./al"><xsl:text>"@nl;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>cprmv:definition "</xsl:text><xsl:value-of select="./al"/><xsl:text>"@nl</xsl:text></xsl:if><xsl:text>
                </xsl:text><xsl:if test="$indent=true()"><xsl:text>&#160;&#160;&#160;&#160;</xsl:text></xsl:if><xsl:text>]</xsl:text>
  </xsl:template>
  
</xsl:stylesheet>
