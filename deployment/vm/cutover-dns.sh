#!/usr/bin/env bash
# Moves a tier's host name to its new VM: acc.cprmv.open-regels.nl for TIER=acc
# (the default), cprmv.open-regels.nl for TIER=stable. Run by the user:
#   TIER=<acc|stable> bash cutover-dns.sh               the cutover
#   TIER=<acc|stable> bash cutover-dns.sh --lower-ttl   only set the TTL to 300, a day ahead
#
# The cutover refuses unless the new VM reports state "running" on its own IP.
# It sets the A record to exactly that IP (other records in the set are
# removed) with TTL 300, and prints the old and the new values. For stable it
# then deletes the TLSA record set _443._tcp.<record> if there is one: it pins
# the old server's key, and Caddy's certificate key may change at renewal.
#
# Required environment (not kept in the repository, which is public):
#   SUBSCRIPTION         the Azure subscription id of the VM
#   DNS_RESOURCE_GROUP   the resource group of the DNS zone
# Optional environment (defaults below): TIER, RESOURCE_GROUP, PUBLIC_IP_NAME
# (the VM's public IP resource), DNS_SUBSCRIPTION (default: SUBSCRIPTION),
# DNS_ZONE, DNS_RECORD, TTL.
set -euo pipefail
export MSYS_NO_PATHCONV=1

die() {
  echo "cutover-dns.sh: $*" >&2
  exit 1
}

TIER=${TIER:-acc}
case $TIER in
  acc) default_record=acc.cprmv ;;
  stable) default_record=cprmv ;;
  *) die "TIER must be acc or stable, not '$TIER'" ;;
esac

SUBSCRIPTION=${SUBSCRIPTION:-}
RESOURCE_GROUP=${RESOURCE_GROUP:-rg-cprmv-$TIER}
PUBLIC_IP_NAME=${PUBLIC_IP_NAME:-pip-cprmv-$TIER}
DNS_SUBSCRIPTION=${DNS_SUBSCRIPTION:-$SUBSCRIPTION}
DNS_RESOURCE_GROUP=${DNS_RESOURCE_GROUP:-}
DNS_ZONE=${DNS_ZONE:-open-regels.nl}
DNS_RECORD=${DNS_RECORD:-$default_record}
TTL=${TTL:-300}

[ -n "$SUBSCRIPTION" ] || die "SUBSCRIPTION is required: the Azure subscription id"
[ -n "$DNS_RESOURCE_GROUP" ] || die "DNS_RESOURCE_GROUP is required: the resource group of the DNS zone"

mode=${1:-cutover}
case $mode in cutover | --lower-ttl) ;; *) die "usage: TIER=<acc|stable> cutover-dns.sh [--lower-ttl]" ;; esac
command -v az >/dev/null 2>&1 || die "az is not installed"
command -v curl >/dev/null 2>&1 || die "curl is not installed"
command -v jq >/dev/null 2>&1 || die "jq is not installed"

# az prints CRLF line ends on some Windows terminals; a captured value must not carry the CR.
strip_cr() { tr -d '\r'; }

dns() { az network dns record-set a "$@" --subscription "$DNS_SUBSCRIPTION" \
  --resource-group "$DNS_RESOURCE_GROUP" --zone-name "$DNS_ZONE" -n "$DNS_RECORD"; }

old=$(dns show --query "ARecords[].ipv4Address" --output tsv | strip_cr | tr '\n' ' ')
old_ttl=$(dns show --query TTL --output tsv | strip_cr)

if [ "$mode" = "--lower-ttl" ]; then
  dns update --set ttl="$TTL" --output none
  echo "$DNS_RECORD.$DNS_ZONE: TTL $old_ttl -> $TTL (records unchanged: $old)"
  exit 0
fi

new=$(az network public-ip show --subscription "$SUBSCRIPTION" --resource-group "$RESOURCE_GROUP" \
  --name "$PUBLIC_IP_NAME" --query ipAddress --output tsv | strip_cr)
[ -n "$new" ] || die "the public IP $PUBLIC_IP_NAME has no address"

status=$(curl -fsS --max-time 15 "http://$new/deploy-status.json") ||
  die "http://$new/deploy-status.json is not reachable; not moving DNS"
printf '%s' "$status" | jq -e --arg t "$TIER" '.state == "running" and .tier == $t' >/dev/null ||
  die "the VM at $new does not report tier $TIER running; not moving DNS. It says: $status"

# Add the new address first so the record set is never empty, then drop the rest.
case " $old " in
  *" $new "*) echo "already present: $new" ;;
  *) dns add-record --ipv4-address "$new" --output none ;;
esac
for ip in $old; do
  [ "$ip" = "$new" ] || dns remove-record --ipv4-address "$ip" --output none
done
dns update --set ttl="$TTL" --output none

now=$(dns show --query "ARecords[].ipv4Address" --output tsv | strip_cr | tr '\n' ' ')
[ "$(printf '%s' "$now" | tr -d ' ')" = "$new" ] || die "the record set holds '$now', not exactly $new; check it in the portal"
echo "$DNS_RECORD.$DNS_ZONE"
echo "  old: $old (TTL $old_ttl)"
echo "  new: $now (TTL $TTL)"

# The stable host had a TLSA record (3 1 1) pinning the old server's key. It is
# removed only now, once the A record holds exactly the new VM.
if [ "$TIER" = stable ]; then
  tlsa=_443._tcp.$DNS_RECORD
  tlsa_az() { az network dns record-set tlsa "$@" --subscription "$DNS_SUBSCRIPTION" \
    --resource-group "$DNS_RESOURCE_GROUP" --zone-name "$DNS_ZONE" -n "$tlsa"; }
  # az exits 3 when the record set does not exist; any other failure is not
  # proof of absence. pipefail carries az's exit code through strip_cr.
  tlsa_err=$(mktemp)
  set +e
  tlsa_old=$(tlsa_az show --query "TLSARecords" --output json 2>"$tlsa_err" | strip_cr)
  rc=$?
  set -e
  err=$(strip_cr <"$tlsa_err")
  rm -f "$tlsa_err"
  case $rc in
    0)
      tlsa_az delete --yes --output none ||
        die "the A record moved to $new; deleting $tlsa.$DNS_ZONE failed; delete it by hand"
      echo "deleted: TLSA record set $tlsa.$DNS_ZONE (it held: $(printf '%s' "$tlsa_old" | jq -c .))"
      ;;
    3) echo "no TLSA record set $tlsa.$DNS_ZONE; nothing to delete" ;;
    *) die "could not read $tlsa.$DNS_ZONE: $err; the A record has already moved to $new; delete the TLSA set by hand" ;;
  esac
fi

echo "Caddy retries ACME with backoff from its startup, so the certificate should appear within a few minutes."
echo "If not, on the VM: sudo docker compose -p cprmv-$TIER -f /opt/cprmv/$TIER/current/compose.yml restart caddy"
