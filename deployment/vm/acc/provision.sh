#!/usr/bin/env bash
# Provisions the CPRMV acceptance VM with the az CLI. Run by the user:
#   SUBSCRIPTION=<subscription id> ADMIN_SSH_SOURCE=<address> bash provision.sh
# Idempotent: each resource is created only if it is missing.
#
# Required environment:
#   ADMIN_SSH_SOURCE   the one address (or CIDR) allowed to reach SSH. Never
#                      written to a file; the repository is public.
#   SUBSCRIPTION       the Azure subscription id. Not written to a file either.
# Optional environment (defaults below):
#   LOCATION, RESOURCE_GROUP, VM_NAME, VM_SIZE, VM_IMAGE,
#   ADMIN_USER, ADMIN_SSH_PUBLIC_KEY (path), VNET_NAME, SUBNET_NAME, NSG_NAME,
#   PUBLIC_IP_NAME, REPO_ROOT (the checkout; default: this script's repository,
#   so a copy of the script elsewhere needs REPO_ROOT set).
# Other use:
#   bash provision.sh --render <file>   write the rendered cloud-init and stop;
#                                       needs neither Azure nor the variables above.
set -euo pipefail
export MSYS_NO_PATHCONV=1 # Git Bash must not rewrite arguments that look like paths

SUBSCRIPTION=${SUBSCRIPTION:-}
LOCATION=${LOCATION:-westeurope}
RESOURCE_GROUP=${RESOURCE_GROUP:-rg-cprmv-acc}
VM_NAME=${VM_NAME:-vm-cprmv-acc}
VM_SIZE=${VM_SIZE:-Standard_B2ms}
VM_IMAGE=${VM_IMAGE:-Canonical:ubuntu-24_04-lts:server:latest} # Ubuntu 24.04 LTS, x86-64
ADMIN_USER=${ADMIN_USER:-cprmvadmin}
ADMIN_SSH_PUBLIC_KEY=${ADMIN_SSH_PUBLIC_KEY:-$HOME/.ssh/id_ed25519.pub}
VNET_NAME=${VNET_NAME:-vnet-cprmv-acc}
SUBNET_NAME=${SUBNET_NAME:-snet-cprmv-acc}
NSG_NAME=${NSG_NAME:-nsg-cprmv-acc}
PUBLIC_IP_NAME=${PUBLIC_IP_NAME:-pip-cprmv-acc}

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=${REPO_ROOT:-$(cd "$here/../../.." && pwd)}
template=$REPO_ROOT/deployment/vm/acc/cloud-init.yaml
reconciler_dir=$REPO_ROOT/deployment/vm/reconciler

die() {
  echo "provision.sh: $*" >&2
  exit 1
}

b64() { base64 <"$1" | tr -d '\n'; }

# az prints CRLF line ends on some Windows terminals; a captured value must not carry the CR.
strip_cr() { tr -d '\r'; }

# render <out>: the cloud-init template with the three files inserted.
render() {
  local f out=$1 tpl
  for f in "$template" "$reconciler_dir/reconcile.sh" \
    "$reconciler_dir/cprmv-reconcile@.service" "$reconciler_dir/cprmv-reconcile@.timer"; do
    [ -f "$f" ] || die "missing $f (set REPO_ROOT to the checkout)"
  done
  tpl=$(cat "$template")
  tpl=${tpl//@@RECONCILE_SH_B64@@/$(b64 "$reconciler_dir/reconcile.sh")}
  tpl=${tpl//@@RECONCILE_SERVICE_B64@@/$(b64 "$reconciler_dir/cprmv-reconcile@.service")}
  tpl=${tpl//@@RECONCILE_TIMER_B64@@/$(b64 "$reconciler_dir/cprmv-reconcile@.timer")}
  case $tpl in *@@RECONCILE_*) die "a placeholder is left in the rendered cloud-init" ;; esac
  printf '%s\n' "$tpl" >"$out"
  # Azure accepts 64 KB of custom data, measured after its own base64.
  [ "$(wc -c <"$out")" -lt 45000 ] || die "rendered cloud-init is too large for custom data"
}

if [ "${1:-}" = "--render" ]; then
  [ -n "${2:-}" ] || die "usage: provision.sh --render <file>"
  render "$2"
  echo "rendered cloud-init written to $2"
  exit 0
fi

[ -n "$SUBSCRIPTION" ] || die "SUBSCRIPTION is required: the Azure subscription id (not kept in the repository)"
[ -n "${ADMIN_SSH_SOURCE:-}" ] || die "ADMIN_SSH_SOURCE is required: the one address allowed to reach SSH"
[ -f "$ADMIN_SSH_PUBLIC_KEY" ] || die "no SSH public key at $ADMIN_SSH_PUBLIC_KEY (set ADMIN_SSH_PUBLIC_KEY)"
command -v az >/dev/null 2>&1 || die "az is not installed"

# The key value (not the path) goes to az: without the CR of a CRLF key file, and
# never echoed, as its comment is usually an e-mail address. az needs the type
# named for Ed25519.
ssh_key=$(tr -d '\r' <"$ADMIN_SSH_PUBLIC_KEY" | head -n 1)
case ${ssh_key%% *} in
  ssh-ed25519) ssh_key_type=(--ssh-key-type Ed25519) ;;
  ssh-rsa) ssh_key_type=() ;;
  *) die "the key in $ADMIN_SSH_PUBLIC_KEY is neither ssh-ed25519 nor ssh-rsa" ;;
esac

userdata=$(mktemp)
trap 'rm -f "$userdata"' EXIT
render "$userdata"
# az is a native Windows program and, with path conversion off, cannot find a
# POSIX path such as /tmp/tmp.X: it would take the string itself as custom data.
userdata_arg=$userdata
if command -v cygpath >/dev/null 2>&1; then
  userdata_arg=$(cygpath -m "$userdata")
  case $userdata_arg in /*) die "could not turn $userdata into a Windows path for az" ;; esac
fi

# Every call names the subscription; the user's default is left alone.
azs() { az "$@" --subscription "$SUBSCRIPTION"; }

if azs group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "exists: resource group $RESOURCE_GROUP"
else
  echo "creating: resource group $RESOURCE_GROUP"
  azs group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
fi

if azs network nsg show --resource-group "$RESOURCE_GROUP" --name "$NSG_NAME" >/dev/null 2>&1; then
  echo "exists: network security group $NSG_NAME"
else
  echo "creating: network security group $NSG_NAME"
  azs network nsg create --resource-group "$RESOURCE_GROUP" --name "$NSG_NAME" \
    --location "$LOCATION" --output none
fi

# nsg_rule <name> <priority> <port> <source>: create the rule, or correct its
# source when it exists with another one.
nsg_rule() {
  local name=$1 priority=$2 port=$3 source=$4 current
  if current=$(azs network nsg rule show --resource-group "$RESOURCE_GROUP" \
    --nsg-name "$NSG_NAME" --name "$name" --query sourceAddressPrefix --output tsv 2>/dev/null | strip_cr); then
    if [ "$current" = "$source" ]; then
      echo "exists: NSG rule $name"
    else
      echo "updating: NSG rule $name (the source differed)"
      azs network nsg rule update --resource-group "$RESOURCE_GROUP" --nsg-name "$NSG_NAME" \
        --name "$name" --source-address-prefixes "$source" --output none
    fi
  else
    echo "creating: NSG rule $name"
    azs network nsg rule create --resource-group "$RESOURCE_GROUP" --nsg-name "$NSG_NAME" \
      --name "$name" --priority "$priority" --direction Inbound --access Allow \
      --protocol Tcp --source-address-prefixes "$source" --source-port-ranges '*' \
      --destination-address-prefixes '*' --destination-port-ranges "$port" --output none
  fi
}
nsg_rule allow-http 100 80 '*'
nsg_rule allow-https 110 443 '*'
nsg_rule allow-ssh-admin 120 22 "$ADMIN_SSH_SOURCE"

if azs network vnet show --resource-group "$RESOURCE_GROUP" --name "$VNET_NAME" >/dev/null 2>&1; then
  echo "exists: virtual network $VNET_NAME"
else
  echo "creating: virtual network $VNET_NAME"
  azs network vnet create --resource-group "$RESOURCE_GROUP" --name "$VNET_NAME" \
    --location "$LOCATION" --address-prefixes 10.20.0.0/24 \
    --subnet-name "$SUBNET_NAME" --subnet-prefixes 10.20.0.0/27 --output none
fi

if azs network public-ip show --resource-group "$RESOURCE_GROUP" --name "$PUBLIC_IP_NAME" >/dev/null 2>&1; then
  echo "exists: public IP $PUBLIC_IP_NAME"
else
  echo "creating: public IP $PUBLIC_IP_NAME (Standard, static)"
  azs network public-ip create --resource-group "$RESOURCE_GROUP" --name "$PUBLIC_IP_NAME" \
    --location "$LOCATION" --sku Standard --allocation-method Static --version IPv4 --output none
fi

# The VM carries the hash of the cloud-init it was created with, to tell a later
# run whether the rendered cloud-init has changed since.
want=$(sha256sum <"$userdata" | cut -d' ' -f1)
if have=$(azs vm show --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" \
  --query 'tags."cloudinit-sha256"' --output tsv 2>/dev/null | strip_cr); then
  echo "exists: VM $VM_NAME"
  if [ "$have" != "$want" ]; then
    echo "cloud-init changed since this VM was created; delete the VM to apply it (cloud-init runs on first boot only)"
  fi
else
  echo "creating: VM $VM_NAME ($VM_SIZE, $VM_IMAGE)"
  azs vm create --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --location "$LOCATION" \
    --size "$VM_SIZE" --image "$VM_IMAGE" \
    --admin-username "$ADMIN_USER" --authentication-type ssh \
    --ssh-key-values "$ssh_key" ${ssh_key_type[@]+"${ssh_key_type[@]}"} \
    --custom-data "$userdata_arg" --tags "cloudinit-sha256=$want" \
    --nsg "$NSG_NAME" --vnet-name "$VNET_NAME" --subnet "$SUBNET_NAME" \
    --public-ip-address "$PUBLIC_IP_NAME" --output none
fi

ip=$(azs network public-ip show --resource-group "$RESOURCE_GROUP" --name "$PUBLIC_IP_NAME" \
  --query ipAddress --output tsv | strip_cr)
echo
echo "Public IP: $ip"
echo "cloud-init needs a few minutes, then the first reconciler run deploys the head of acc."
echo "Check:"
echo "  http://$ip/health"
echo "  http://$ip/deploy-status.json"
