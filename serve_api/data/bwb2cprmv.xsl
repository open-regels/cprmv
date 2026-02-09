<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="text" indent="yes"/>
  <xsl:param name="cprmvid" select="''"/>
  
  <xsl:template match="text()"/>
  
  <xsl:template match="/toestand">
    <xsl:text xml:space="preserve">@base &lt;http://example.com/&gt; .
@prefix cpsv: &lt;http://purl.org/vocab/cpsv#&gt; .
@prefix cprmv: &lt;https://standaarden.open-regels.nl/standards/cprmv/0.4.0/#&gt; .
@prefix cprmvmethods: &lt;https://cprmv.open-regels.nl/0.4.0/methods/&gt; .
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
        cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"</xsl:text></xsl:if><xsl:if test="afdeling|paragraaf|artikel"><xsl:text xml:space="preserve">;
        cprmv:contains (</xsl:text><xsl:apply-templates select="afdeling|paragraaf|artikel"/><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
    ]</xsl:text>
  </xsl:template>
  
  <xsl:template match="afdeling"><xsl:text xml:space="preserve">[
            a cprmv:Rule;
            cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./kop/titel"><xsl:text xml:space="preserve">;
            cprmv:definition "</xsl:text><xsl:value-of select="translate(./kop/titel, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./artikel"><xsl:text xml:space="preserve">;
            cprmv:contains (</xsl:text><xsl:apply-templates select="artikel"><xsl:with-param name="indent" select="true()"/></xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
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
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./lid|./lijst/li|table"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="lid|lijst/li|table">
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
        </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">     </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
</xsl:template>

  <xsl:template match="lid"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "lid </xsl:text><xsl:value-of select="./lidnr"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./lijst/li|table"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="lijst/li|table">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="lijst/li"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "onderdeel </xsl:text><xsl:value-of select="./li.nr"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./lijst/li|table"><xsl:text xml:space="preserve">;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="lijst/li|table">
                        <xsl:with-param name="indent" select="$indent"/>
                    </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="table"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "table </xsl:text><xsl:value-of select="position()"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./title, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="tgroup/tbody/row"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="tgroup/tbody/row">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="row"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "row </xsl:text><xsl:value-of select="position()"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="entry"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:contains (</xsl:text><xsl:apply-templates select="entry">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="entry"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "column </xsl:text><xsl:value-of select="position()"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./al"><xsl:text xml:space="preserve">;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:apply-templates select="al"></xsl:apply-templates><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:text xml:space="preserve">
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="al"><xsl:value-of select="translate(., '&#xA;', '')"/></xsl:template>
  
</xsl:stylesheet>
