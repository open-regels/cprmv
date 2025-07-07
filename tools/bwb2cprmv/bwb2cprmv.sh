#!/bin/sh

BWBID=$1
if [[ "$BWBID" =~ ^BWBR[0-9]{7}$ ]] &> /dev/null; then
    echo "BWB id: $BWBID"
else
    echo "No valid BWB id given (expecting format: 'BWBRxxxxxxx')"
    exit 254
fi

PUBDATE=$2
if [[ "$PUBDATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && [[ "$PUBDATE" == $(date -r $(date -j -f "%Y-%m-%d" "$PUBDATE" "+%s") '+%Y-%m-%d') ]] &> /dev/null; then
    echo "publication date: $PUBDATE"
else
    echo "No valid publication date given (use format: YYYY-MM-DD)"
    exit 253
fi

INDEX="${3:-0}"
if [[ "$INDEX" =~ ^[0-9]{1}$ ]] &> /dev/null; then
    echo "index: $INDEX (default = 0)"
else
    echo "No valid BWB publication index given (expecting a single digit, default = 0)"
    exit 254
fi

XSLT="${4:-bwb-toestand2cprmv.xsl}"
echo "using XSL stylesheet: $XSLT"

BWBFILENAME="${BWBID}_${PUBDATE}_${INDEX}"

echo "fetching BWB publication from repository.officiele-overheidspublicaties.nl..."
curl "https://repository.officiele-overheidspublicaties.nl/bwb/${BWBID}/${PUBDATE}_0//xml/${BWBFILENAME}.xml" > "${BWBFILENAME}.xml"

echo "validating retrieved xml..."
xmllint --noout -schema toestand_2016-1.xsd "${BWBFILENAME}.xml"

echo "Converting ${BWBFILENAME}.xml to a cprmv representation (RDF/Turtle 1.2)"
xsltproc "${XSLT}" "${BWBFILENAME}.xml" > "${BWBFILENAME}.ttl"

echo "Output file: ${BWBFILENAME}.ttl"

echo "Converting ${BWBFILENAME}.ttl to an alternative cprmv representation (RDF/Turtle 1.2) for experimental rule method ExtractNormBedragUitBWBWet-experimenteel"
sed -e 's/cprmv:definition ".*€.\([0-9]\{0,3\}\).\{0,1\}\([0-9]\{1,3\},[0-9]\{1,2\}\).*"/cprmv:definition "\1\2"/g' -e 's/cprmvmethods:bwb/cprmvmethods:ExtractNormBedragUitBWBWet-experimenteel/g' "${BWBFILENAME}.ttl" > "${BWBFILENAME}.normbedrag.ttl"


exit 0
