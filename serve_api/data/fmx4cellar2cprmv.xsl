<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cvdr="http://standaarden.overheid.nl/cvdr/terms/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:overheidrg="http://standaarden.overheid.nl/cvdr/meta/"
    xmlns:overheid="http://standaarden.overheid.nl/owms/terms/" version="1.0">
  <xsl:output method="text" encoding="UTF-8" indent="yes"/>
  <xsl:param name="cprmvid" select="''"/>
  <xsl:param name="puburl" select="''"/>
  
  <xsl:template match="text()"/>
  
  <xsl:template match="/ACT|/CONS.ACT"><xsl:text xml:space="preserve">@base &lt;http://example.com/&gt; .
@prefix cpsv: &lt;http://purl.org/vocab/cpsv#&gt; .
@prefix cprmv: &lt;https://standaarden.open-regels.nl/standards/cprmv/0.4.1/#&gt; .
@prefix cprmvmethods: &lt;https://cprmv.open-regels.nl/0.4.1/methods/&gt; .
&lt;http://publications.europa.eu/resource/celex/</xsl:text><xsl:value-of select="$cprmvid"/><xsl:text xml:space="preserve">&gt; a cprmv:RuleSet;
    cprmv:isBasedOn &lt;</xsl:text><xsl:value-of select="$puburl"/><xsl:text xml:space="preserve">&gt;;
    cprmv:id "</xsl:text><xsl:value-of select="$cprmvid"/><xsl:text xml:space="preserve">"@nl;
    cprmv:id "3</xsl:text><xsl:value-of select="BIB.INSTANCE/DOCUMENT.REF/YEAR"/><xsl:text xml:space="preserve">R</xsl:text><xsl:value-of select="BIB.INSTANCE/NO.DOC/NO.CURRENT"/><xsl:text xml:space="preserve">.NLD.fmx4.</xsl:text><xsl:value-of select="BIB.INSTANCE/DOCUMENT.REF/@FILE"/><xsl:text xml:space="preserve">"@nl;
    cprmv:hasMethod cprmvmethods:cellarfmx4;
    cprmv:output-of [
        a cpsv:PublicService;
        cprmv:id "some cpsv:PublicService instance ";
        cprmv:providedBy "EU";
        cpsv:produces &lt;http://publications.europa.eu/resource/celex/3</xsl:text><xsl:value-of select="BIB.INSTANCE/DOCUMENT.REF/YEAR"/><xsl:text xml:space="preserve">R</xsl:text><xsl:value-of select="BIB.INSTANCE/NO.DOC/NO.CURRENT"/><xsl:text xml:space="preserve">.NLD.fmx4.</xsl:text><xsl:value-of select="BIB.INSTANCE/DOCUMENT.REF/@FILE"/><xsl:text xml:space="preserve">&gt;
    ];
    cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="./ENACTING.TERMS/DIVISION|./CONS.DOC/ENACTING.TERMS/DIVISION"/><xsl:text xml:space="preserve">).
</xsl:text>
  </xsl:template>

  <xsl:template match="DIVISION"><xsl:text xml:space="preserve">[
        a cprmv:Rule;
        cprmv:id "</xsl:text><xsl:value-of select="./TITLE/TI/P"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./STI/P/HT"><xsl:text xml:space="preserve">;
        cprmv:definition "</xsl:text><xsl:value-of select="translate(./STI/P/HT, '&#xA;', '')"/><xsl:text xml:space="preserve">"</xsl:text></xsl:if><xsl:if test="DIVISION|ARTICLE"><xsl:text xml:space="preserve">;
        cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="DIVISION|ARTICLE"/><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
    ]</xsl:text>
  </xsl:template>
  
  <xsl:template match="ARTICLE"><xsl:param name="indent" select="false"/><xsl:text xml:space="preserve">[
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "</xsl:text><xsl:value-of select="TI.ART"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./STI.ART"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./STI.ART, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./PARAG|./LIST/ITEM"><xsl:text xml:space="preserve">;
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="PARAG|LIST/ITEM">
                <xsl:with-param name="indent" select="$indent"/>
            </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
        </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">     </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="PARAG"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "lid </xsl:text><xsl:value-of select="./NO.PARAG"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./ALINEA"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./ALINEA, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:if test="./ALINEA/LIST/ITEM"><xsl:text xml:space="preserve">;
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:hasPart
 (</xsl:text><xsl:apply-templates select="ALINEA/LIST/ITEM">
                    <xsl:with-param name="indent" select="$indent"/>
                </xsl:apply-templates><xsl:text xml:space="preserve">)</xsl:text></xsl:if><xsl:text xml:space="preserve">
            </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
  <xsl:template match="ITEM"><xsl:param name="indent"/><xsl:text xml:space="preserve">[
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">a cprmv:Rule;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:id "onderdeel </xsl:text><xsl:value-of select="./NP/NO.P"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:if test="./NP/TXT"><xsl:text xml:space="preserve">;
                    </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">cprmv:definition "</xsl:text><xsl:value-of select="translate(./NP/TXT, '&#xA;', '')"/><xsl:text xml:space="preserve">"@nl</xsl:text></xsl:if><xsl:text xml:space="preserve">
                </xsl:text><xsl:if test="$indent=true()"><xsl:text xml:space="preserve">    </xsl:text></xsl:if><xsl:text xml:space="preserve">]</xsl:text>
  </xsl:template>
  
</xsl:stylesheet>
