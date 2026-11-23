<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:dmn="http://www.omg.org/spec/DMN/20151101/dmn.xsd" xmlns:feel="http://www.omg.org/spec/FEEL/20140401" xmlns:triso="http://www.trisotech.com/2015/triso/modeling" xmlns:trisofeed="http://trisotech.com/feed" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0">
  <xsl:output method="text" indent="no" omit-xml-declaration="yes"/>
  <xsl:param name="cprmvid" select="'root'"/>
  <xsl:param name="puburl" select="''"/>

  <xsl:template match="text()"/>

  <xsl:template match="/dmn:definitions" priority="2">
    <xsl:text xml:space="preserve">@base &lt;https://cprmv.open-regels.nl/0.4.3/methods/dso/&gt; .
@prefix cpsv: &lt;http://purl.org/vocab/cpsv#&gt; .
@prefix cprmv: &lt;https://standaarden.open-regels.nl/standards/cprmv/0.4.3#&gt; .
@prefix cprmvmethods: &lt;https://cprmv.open-regels.nl/0.4.3/methods/&gt; .
@prefix prov: &lt;http://www.w3.org/ns/prov#&gt; .
@prefix xsd: &lt;http://www.w3.org/2001/XMLSchema#&gt; .
@prefix overheid: &lt;http://standaarden.overheid.nl/owms/terms/&gt; .
@prefix tooibwb: &lt;https://identifier.overheid.nl/tooi/thes/bwb&gt; .
&lt;</xsl:text><xsl:value-of select="$cprmvid"/><xsl:text xml:space="preserve">&gt; a cprmv:DecisionModel;
    prov:wasDerivedFrom &lt;</xsl:text><xsl:value-of select="$puburl"/><xsl:text xml:space="preserve">&gt;;
    cprmv:id "</xsl:text><xsl:value-of select="$cprmvid"/><xsl:text xml:space="preserve">"@nl;
    # TODO cprmv:validFrom "YYYY-MM-DD"^^xsd:date is required by RuleSetShape; wire a reliable date from the DMN source.
    cprmv:validFrom "</xsl:text>2026-01-01<xsl:text xml:space="preserve">"^^xsd:date;
    cprmv:hasMethod cprmvmethods:sttr;
    cprmv:hasPart (</xsl:text><xsl:apply-templates select="./*"/><xsl:text xml:space="preserve">).
</xsl:text>
  </xsl:template>

  <xsl:template match="*" priority="1"><xsl:text xml:space="preserve">[
        a cprmv:Rule;
        cprmv:id "</xsl:text><xsl:value-of select="@id"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:choose><xsl:when test="./*[@id]"><xsl:text xml:space="preserve">;
        cprmv:hasPart (</xsl:text><xsl:apply-templates select="./*"/><xsl:text xml:space="preserve">)</xsl:text></xsl:when><xsl:otherwise><xsl:text xml:space="preserve">;
        cprmv:definition "</xsl:text><xsl:call-template name="verbatim"><xsl:with-param name="quote" select="*"/></xsl:call-template><xsl:text xml:space="preserve">";</xsl:text></xsl:otherwise></xsl:choose><xsl:text xml:space="preserve">
    ]</xsl:text>
  </xsl:template>

  <xsl:template name="verbatim">
      <xsl:param name="quote"/>
      <xsl:call-template name="encode-string"><xsl:with-param name="s" select="$quote"/></xsl:call-template>
  </xsl:template>

  <xsl:template name="encode-string">
          <xsl:param name="s" select="''"/>
          <xsl:param name="encoded" select="''"/>
          <xsl:choose>
            <xsl:when test="$s = ''">
                <xsl:call-template name="verbatim2"><xsl:with-param name="quote" select="$encoded"/></xsl:call-template>
            </xsl:when>
            <xsl:when test="contains($s, '&quot;')">
              <xsl:call-template name="encode-string">
                <xsl:with-param name="s" select="substring-after($s,'&quot;')"/>
                <xsl:with-param name="encoded"
                                select="concat($encoded,substring-before($s,'&quot;'),'')"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:otherwise>
                <xsl:call-template name="verbatim2"><xsl:with-param name="quote" select="concat($encoded, $s)"/></xsl:call-template>
            </xsl:otherwise>
          </xsl:choose>
      </xsl:template>

  <xsl:template name="verbatim2">
      <xsl:param name="quote"/>
      <xsl:call-template name="encode-string2"><xsl:with-param name="s" select="$quote"/></xsl:call-template>
  </xsl:template>

  <xsl:template name="encode-string2">
          <xsl:param name="s" select="''"/>
          <xsl:param name="encoded" select="''"/>
          <xsl:choose>
            <xsl:when test="$s = ''">
              <xsl:value-of select="$encoded"/>
            </xsl:when>
            <xsl:when test="contains($s, '&#xa;')">
              <xsl:call-template name="encode-string">
                <xsl:with-param name="s" select="substring-after($s,'&#xa;')"/>
                <xsl:with-param name="encoded"
                                select="concat($encoded,substring-before($s,'&#xa;'),'')"/>
              </xsl:call-template>
            </xsl:when>
            <xsl:otherwise>
              <xsl:value-of select="concat($encoded, $s)"/>
            </xsl:otherwise>
          </xsl:choose>
      </xsl:template>

</xsl:stylesheet>
