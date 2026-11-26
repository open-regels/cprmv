#!/usr/bin/env bash
# Moves acc.cprmv.open-regels.nl to the new VM. Run by the user:
#   bash cutover-dns.sh               the cutover
#   bash cutover-dns.sh --lower-ttl   only set the TTL to 300, a day ahead
#
# The cutover refuses unless the new VM reports state "running" on its own IP.
# It sets the A record to exactly that IP (other records in the set are
# removed) with TTL 300, and prints the old and the new values.
#
# Required environment (not kept in the repository, which is public):
#   SUBSCRIPTION         the Azure subscription id of the VM
#   DNS_RESOURCE_GROUP   the resource group of the DNS zone
# Optional environment (defaults below): RESOURCE_GROUP, PUBLIC_IP_NAME (the
# VM's public IP resource), DNS_SUBSCRIPTION (default: SUBSCRIPTION), DNS_ZONE,
# DNS_RECORD, TTL.
set -euo pipefail
export MSYS_NO_PATHCONV=1

SUBSCRIPTION=${SUBSCRIPTION:-}
RESOURCE_GROUP=${RESOURCE_GROUP:-rg-cprmv-acc}
PUBLIC_IP_NAME=${PUBLIC_IP_NAME:-pip-cprmv-acc}
DNS_SUBSCRIPTION=${DNS_SUBSCRIPTION:-$SUBSCRIPTION}
DNS_RESOURCE_GROUP=${DNS_RESOURCE_GROUP:-}
DNS_ZONE=${DNS_ZONE:-open-regels.nl}
DNS_RECORD=${DNS_RECORD:-acc.cprmv}
TTL=${TTL:-300}

die() {
  echo "cutover-dns.sh: $*" >&2
  exit 1
}

[ -n "$SUBSCRIPTION" ] || die "SUBSCRIPTION is required: the Azure subscription id"
[ -n "$DNS_RESOURCE_GROUP" ] || die "DNS_RESOURCE_GROUP is required: the resource group of the DNS zone"

mode=${1:-cutover}
case $mode in cutover | --lower-ttl) ;; *) die "usage: cutover-dns.sh [--lower-ttl]" ;; esac
command -v az >/dev/null 2>&1 || die "az is not installed"
command -v curl >/dev/null 2>&1 || die "curl is not installed"
command -v jq >/dev/null 2>&1 || die "jq is not installed"

dns() { az network dns record-set a "$@" --subscription "$DNS_SUBSCRIPTION" \
  --resource-group "$DNS_RESOURCE_GROUP" --zone-name "$DNS_ZONE" -n "$DNS_RECORD"; }

old=$(dns show --query "ARecords[].ipv4Address" --output tsv | tr '\n' ' ')
old_ttl=$(dns show --query ttl --output tsv)

if [ "$mode" = "--lower-ttl" ]; then
  dns update --set ttl="$TTL" --output none
  echo "$DNS_RECORD.$DNS_ZONE: TTL $old_ttl -> $TTL (records unchanged: $old)"
  exit 0
fi

new=$(az network public-ip show --subscription "$SUBSCRIPTION" --resource-group "$RESOURCE_GROUP" \
  --name "$PUBLIC_IP_NAME" --query ipAddress --output tsv)
[ -n "$new" ] || die "the public IP $PUBLIC_IP_NAME has no address"

status=$(curl -fsS --max-time 15 "http://$new/deploy-status.json") ||
  die "http://$new/deploy-status.json is not reachable; not moving DNS"
printf '%s' "$status" | jq -e '.state == "running"' >/dev/null ||
  die "the VM does not report state running; not moving DNS. It says: $status"

# Add the new address first so the record set is never empty, then drop the rest.
case " $old " in
  *" $new "*) echo "already present: $new" ;;
  *) dns add-record --ipv4-address "$new" --output none ;;
esac
for ip in $old; do
  [ "$ip" = "$new" ] || dns remove-record --ipv4-address "$ip" --output none
done
dns update --set ttl="$TTL" --output none

now=$(dns show --query "ARecords[].ipv4Address" --output tsv | tr '\n' ' ')
[ "$(printf '%s' "$now" | tr -d ' ')" = "$new" ] || die "the record set holds '$now', not exactly $new; check it in the portal"
echo "$DNS_RECORD.$DNS_ZONE"
echo "  old: $old (TTL $old_ttl)"
echo "  new: $now (TTL $TTL)"
echo "Caddy retries ACME with backoff from its startup, so the certificate should appear within a few minutes."
echo "If not, on the VM: sudo docker compose -p cprmv-acc -f /opt/cprmv/acc/current/compose.yml restart caddy"
