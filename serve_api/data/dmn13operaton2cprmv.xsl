<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:dmn="https://www.omg.org/spec/DMN/20191111/MODEL/" xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/" xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/" xmlns:modeler="http://camunda.org/schema/modeler/1.0" xmlns:camunda="http://camunda.org/schema/1.0/dmn" version="1.0">
  <xsl:output method="text" indent="no" omit-xml-declaration="yes"/>
  <xsl:param name="cprmvid" select="'root'"/>
  
  <xsl:template match="text()"/>
  
  <xsl:template match="/dmn:definitions" priority="2">
    <xsl:text xml:space="preserve">@base &lt;http://operaton.open-regels.nl/&gt; .
@prefix cprmv: &lt;https://standaarden.open-regels.nl/standards/cprmv/0.4.0/#&gt; .
@prefix cprmvmethods: &lt;https://cprmv.open-regels.nl/0.4.0/methods/&gt; .
&lt;</xsl:text><xsl:value-of select="$cprmvid"/><xsl:text xml:space="preserve">&gt; a cprmv:RuleSet;
    cprmv:id "</xsl:text><xsl:value-of select="$cprmvid"/><xsl:text xml:space="preserve">"@nl;
    cprmv:method cprmvmethods:dmn13;
    cprmv:contains (</xsl:text><xsl:apply-templates select="./*"/><xsl:text xml:space="preserve">).
</xsl:text>
  </xsl:template>

  <xsl:template match="*" priority="1"><xsl:text xml:space="preserve">[
        a cprmv:Rule;
        cprmv:id "</xsl:text><xsl:value-of select="@id"/><xsl:text xml:space="preserve">"@nl</xsl:text><xsl:choose><xsl:when test="./*[@id]"><xsl:text xml:space="preserve">;
        cprmv:contains (</xsl:text><xsl:apply-templates select="./*"/><xsl:text xml:space="preserve">)</xsl:text></xsl:when><xsl:otherwise><xsl:text xml:space="preserve">;
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
