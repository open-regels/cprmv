<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cvdr="http://standaarden.overheid.nl/cvdr/terms/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:overheidrg="http://standaarden.overheid.nl/cvdr/meta/"
    xmlns:overheid="http://standaarden.overheid.nl/owms/terms/" version="1.0">
  <xsl:output method="text" indent="yes"/>
  <xsl:param name="cprmvid" select="''"/>
  
  <xsl:template match="text()"/>
  
  <xsl:template match="/cvdr:cvdr">
    <xsl:text xml:space="preserve">@base &lt;http://example.com/&gt; .
@prefix cpsv: &lt;http://purl.org/vocab/cpsv#&gt; .
@prefix cprmv: &lt;https://standaarden.open-regels.nl/standards/cprmv/0.4.0/#&gt; .
@prefix cprmvmethods: &lt;https://cprmv.open-regels.nl/0.4.0/methods/&gt; .
@prefix overheid: &lt;http://standaarden.overheid.nl/owms/terms/&gt; .
@prefix tooicvdr: &lt;https://identifier.overheid.nl/tooi/thes/cvdr&gt; .
&lt;http://opencatalogi.open-regels.nl/</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:identifier"/><xsl:text xml:space="preserve">&gt; a cprmv:RuleSet;
    cprmv:isBasedOn &lt;https://identifier.overheid.nl/tooi/id/cvdr/</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:identifier"/><xsl:text xml:space="preserve">&gt;;
    cprmv:id "</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:identifier"/><xsl:text xml:space="preserve">"@nl;
    cprmv:hasMethod cprmvmethods:cvdr;
    cprmv:output-of [
        a cpsv:PublicService;
        cprmv:id &lt;https://identifier.overheid.nl/tooi/id/upl/cvdr/</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:identifier"/><xsl:text xml:space="preserve">&gt;;
        cprmv:providedBy [ overheid:authority [ </xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:creator/@scheme"/><xsl:text xml:space="preserve"> "</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:creator"/><xsl:text xml:space="preserve">" ]];
        cpsv:produces &lt;http://opencatalogi.open-regels.nl/</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:identifier"/><xsl:text xml:space="preserve">&gt;
    ];
    tooicvdr:id "</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:identifier"/><xsl:text xml:space="preserve">";
    tooicvdr:title "</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:owmskern/dcterms:title"/><xsl:text xml:space="preserve">";
    tooicvdr:inwerkingtreding "</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:cvdripm/overheidrg:inwerkingtredingDatum"/><xsl:text xml:space="preserve">";
    tooicvdr:terugwerkendekrachtDatum "</xsl:text><xsl:value-of select="./cvdr:meta/cvdr:cvdripm/overheidrg:terugwerkendekrachtDatum"/><xsl:text xml:space="preserve">";
    cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="./cvdr:body/cvdr:regeling/cvdr:regeling-tekst/*"/><xsl:text xml:space="preserve">).
</xsl:text>
  </xsl:template>

  <xsl:template match="cvdr:hoofdstuk"><xsl:text xml:space="preserve">[
        a cprmv:Rule;
        cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./cvdr:al"><xsl:text xml:space="preserve">;
        cprmv:definition "</xsl:text><xsl:value-of select="translate(./cvdr:al, '&#xA;', '')"/><xsl:text xml:space="preserve">"</xsl:text></xsl:if><xsl:if test="cvdr:paragraaf|cvdr:artikel"><xsl:text xml:space="preserve">;
        cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="cvdr:paragraaf|cvdr:artikel"/><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
    ]</xsl:text>
  </xsl:template>
  
  <xsl:template match="cvdr:paragraaf"><xsl:text xml:space="preserve">[
            a cprmv:Rule;
            cprmv:id "</xsl:text><xsl:value-of select="@label"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./cvdr:al"><xsl:text xml:space="preserve">;
            cprmv:definition "</xsl:text><xsl:value-of select="translate(./cvdr:al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./cvdr:artikel"><xsl:text xml:space="preserve">;
            cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="cvdr:artikel">
                <xsl:with-param name="indent" select="true()"/>
            </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
        ]</xsl:text>
  </xsl:template>
  
  <xsl:template match="cvdr:artikel"><xsl:param name="indent" select="false"/><xsl:text xml:space="preserve">[
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "</xsl:text><xsl:value-of select="concat(cvdr:kop/cvdr:label, ' ', cvdr:kop/cvdr:nr)"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./cvdr:al"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./cvdr:al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./cvdr:lid|./cvdr:lijst/cvdr:li"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="cvdr:lid|cvdr:lijst/cvdr:li">
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
        </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">     </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="cvdr:lid"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "lid </xsl:text><xsl:value-of select="./cvdr:lidnr"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./cvdr:al"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./cvdr:al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./cvdr:lijst/cvdr:li"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="cvdr:lijst/cvdr:li">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="cvdr:lijst/cvdr:li"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "onderdeel </xsl:text><xsl:value-of select="@nr"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./cvdr:al"><xsl:text xml:space="preserve">;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./cvdr:al, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:text xml:space="preserve">
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
</xsl:stylesheet>
