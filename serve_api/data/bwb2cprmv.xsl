<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="text" indent="yes"/>
  <xsl:param name="cprmvid" select="''"/>
  
  <xsl:template match="text()"/>
  
  <xsl:template match="/toestand">
    <xsl:text xml:space="preserve">@base &lt;http://example.com/&gt; .
@prefix cpsv: &lt;http://purl.org/vocab/cpsv#&gt; .
@prefix cprmv: &lt;https://cprmv.open-regels.nl/0.3.0/&gt; .
@prefix cprmvmethods: &lt;https://cprmv.open-regels.nl/0.3.0/methods/&gt; .
@prefix overheid: &lt;http://standaarden.overheid.nl/owms/terms/&gt; .
@prefix tooibwb: &lt;https://identifier.overheid.nl/tooi/thes/bwb&gt; .
&lt;http://opencatalogi.open-regels.nl/</xsl:text><xsl:value-of select="concat(./@bwb-id,'-',./@inwerkingtreding)"/><xsl:text xml:space="preserve">&gt; a cprmv:RuleSet;
    cprmv:extends &lt;https://identifier.overheid.nl/tooi/id/bwb/</xsl:text><xsl:value-of select="./@bwb-id"/><xsl:text xml:space="preserve">&gt;;
    cprmv:id "</xsl:text><xsl:value-of select="concat(./@bwb-id,'_',./@inwerkingtreding, '_', substring(./@bwb-ng-vast-deel, string-length(./@bwb-ng-vast-deel)))"/><xsl:text xml:space="preserve">"@nl;
    cprmv:method cprmvmethods:bwb;
    cprmv:output-of [
        a cpsv:PublicService;
        cprmv:id &lt;https://identifier.overheid.nl/tooi/id/upl/bwb/</xsl:text><xsl:value-of select="./@bwb-id"/><xsl:text xml:space="preserve">&gt;;
        cprmv:providedBy [ overheid:authority "Sociale Zaken en Werkgelegenheid" ];
        cpsv:produces &lt;http://opencatalogi.open-regels.nl/</xsl:text><xsl:value-of select="concat(./@bwb-id,'-',./@inwerkingtreding)"/><xsl:text xml:space="preserve">&gt;
    ];
    tooibwb:id "</xsl:text><xsl:value-of select="./@bwb-id"/><xsl:text xml:space="preserve">";
    tooibwb:inwerkingtreding "</xsl:text><xsl:value-of select="./@inwerkingtreding"/><xsl:text xml:space="preserve">";
    cprmv:contains (</xsl:text><xsl:apply-templates select="./wetgeving/wet-besluit/wettekst/*|./wetgeving/regeling/regeling-tekst/*"/><xsl:text xml:space="preserve">).
</xsl:text>
  </xsl:template>

  <xsl:template match="hoofdstuk"><xsl:text xml:space="preserve">[
        a cprmv:Rule;
        cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
        cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"</xsl:text></xsl:if><xsl:if test="paragraaf|artikel"><xsl:text xml:space="preserve">;
        cprmv:contains (</xsl:text><xsl:apply-templates select="paragraaf|artikel"/><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
    ]</xsl:text>
  </xsl:template>
  
  <xsl:template match="paragraaf"><xsl:text xml:space="preserve">[
            a cprmv:Rule;
            cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
            cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./artikel"><xsl:text xml:space="preserve">;
            cprmv:contains (</xsl:text><xsl:apply-templates select="artikel"><xsl:with-param name="indent" select="true()"/></xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
        ]</xsl:text>
  </xsl:template>
  
<xsl:template match="artikel">
    <xsl:param name="indent" select="false"/>
    <xsl:text xml:space="preserve">[
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./lid|./lijst/li"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="lid|lijst/li">
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
        </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">     </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
</xsl:template>

  <xsl:template match="lid"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "lid </xsl:text><xsl:value-of select="./lidnr"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./lijst/li"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="lijst/li">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="lijst/li"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "onderdeel </xsl:text><xsl:value-of select="./li.nr"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:text xml:space="preserve">
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
</xsl:stylesheet>
