#!/usr/bin/env bash
# Maakt de LXC voor De Morgenkrant en richt hem in.
# Wordt gestart door install.sh; los draaien kan ook:
#   bash /opt/morgenkrant-kit/deploy/proxmox/create-morgenkrant-lxc.sh
#   DROOG=1 ...  -> laat alleen zien wat er zou gebeuren
set -euo pipefail

KIT="${KIT_DIR:-/opt/morgenkrant-kit}"
CTID="${CTID:-}"
HOSTNAME_CT="${HOSTNAME_CT:-morgenkrant}"
CORES="${CORES:-2}"
MEM="${MEM:-1024}"
SWAP="${SWAP:-512}"
SCHIJF="${SCHIJF:-4}"
POORT="${POORT:-8420}"
BRIDGE="${BRIDGE:-vmbr0}"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fout]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Draai dit als root op de Proxmox-host."
command -v pct   >/dev/null || die "pct niet gevonden: dit is geen Proxmox VE-host."
command -v pveam >/dev/null || die "pveam niet gevonden."
[ -f "$KIT/app.py" ] || die "Kit niet gevonden in $KIT (zet KIT_DIR)."

ARCH="${ARCH:-$(dpkg --print-architecture)}"
DEBIAN_MAJOR="${DEBIAN_MAJOR:-13}"

log "Template zoeken voor $ARCH"
TEMPLATE="$(pveam available --section system 2>/dev/null | awk '{print $NF}' \
  | grep -E "^debian-${DEBIAN_MAJOR}-standard_.*_${ARCH}\.tar" | sort -V | tail -1 || true)"
if [ -z "$TEMPLATE" ]; then
  DEBIAN_MAJOR=12
  TEMPLATE="$(pveam available --section system 2>/dev/null | awk '{print $NF}' \
    | grep -E "^debian-${DEBIAN_MAJOR}-standard_.*_${ARCH}\.tar" | sort -V | tail -1 || true)"
fi
[ -n "$TEMPLATE" ] || die "Geen Debian-template voor $ARCH gevonden (pveam available --section system)."
case "$TEMPLATE" in *_${ARCH}.tar*) : ;; *) die "Template $TEMPLATE hoort niet bij $ARCH." ;; esac
log "Template: $TEMPLATE"

if ! pveam list local 2>/dev/null | grep -q "${TEMPLATE%%_*}"; then
  log "Template downloaden (kan een minuut duren)"
  pveam update >/dev/null 2>&1 || true
  pveam download local "$TEMPLATE" || die "Kon $TEMPLATE niet downloaden naar opslag 'local'."
fi
TEMPLATE_PAD="local:vztmpl/$TEMPLATE"

opslag_kandidaten() {
  pvesm status --content "$1" 2>/dev/null | awk 'NR>1 && $3=="active"{
      t=$2
      p = (t=="lvmthin" || t=="zfspool" || t=="btrfs") ? 1 : (t=="lvm" || t=="dir") ? 2 : 3
      printf "%d %019d %s\n", p, 999999999999999999-$6, $1
    }' | sort | awk '{print $3}'
}
opslag_pad() {
  local s="$1" t pad
  t="$(pvesm status 2>/dev/null | awk -v s="$s" 'NR>1 && $1==s{print $2}')"
  pad="$(awk -v s="$s" '$1 ~ /:$/ {naam=$2} naam==s && $1=="path" {print $2; exit}' \
    /etc/pve/storage.cfg 2>/dev/null || true)"
  [ -n "$pad" ] || case "$t" in nfs|cifs|glusterfs) pad="/mnt/pve/$s" ;; esac
  printf '%s' "$pad"
}
opslag_schrijfbaar() {
  local pad; pad="$(opslag_pad "$1")"; [ -n "$pad" ] || return 0
  [ -d "$pad" ] || return 1
  local proef="$pad/.schrijfproef.$$"
  touch "$proef" 2>/dev/null || return 1
  rm -f "$proef"
}

STORAGE="${STORAGE:-}"
if [ -z "$STORAGE" ]; then
  for s in $(opslag_kandidaten rootdir); do
    if opslag_schrijfbaar "$s"; then STORAGE="$s"; break; fi
    warn "Opslag '$s' is niet beschrijfbaar, ik probeer de volgende."
  done
fi
[ -n "$STORAGE" ] || die "Geen beschrijfbare opslag voor de schijf. Bekijk 'pvesm status --content rootdir' (NFS heeft vaak no_root_squash nodig)."
log "Schijf op '$STORAGE'"

if [ -z "$CTID" ]; then
  CTID="$(pvesh get /cluster/nextid 2>/dev/null || true)"
  [ -n "$CTID" ] || die "Kon geen vrij container-id vinden."
fi
[ -z "$(pct status "$CTID" 2>/dev/null || true)" ] || die "Container $CTID bestaat al. Kies CTID=<ander id>."

if [ "${DROOG:-0}" = "1" ]; then
  log "DROOG=1: ik zou container $CTID ($HOSTNAME_CT, ${CORES} cores, ${MEM} MB, ${SCHIJF} GB op $STORAGE) aanmaken en inrichten."
  exit 0
fi

log "Container $CTID aanmaken"
pct create "$CTID" "$TEMPLATE_PAD" \
  --hostname "$HOSTNAME_CT" \
  --cores "$CORES" --memory "$MEM" --swap "$SWAP" \
  --rootfs "$STORAGE:$SCHIJF" \
  --net0 "name=eth0,bridge=$BRIDGE,ip=dhcp" \
  --features nesting=1 \
  --unprivileged 1 \
  --onboot 1 \
  --description "De Morgenkrant - dagelijkse Nederlandstalige krant (webpagina + PDF)" >/dev/null

if ! pct start "$CTID"; then
  warn "Container $CTID startte niet. Dit is de volledige uitleg van de laatste poging:"
  pct start "$CTID" --debug 2>&1 | tail -25 | sed 's/^/    /' || true
  die "De container is aangemaakt maar draait niet. Diagnose:
  CTID=$CTID bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Theberas04/morgenkrant/main/deploy/proxmox/check-morgenkrant.sh)\"
Weggooien kan met: pct destroy $CTID"
fi

log "Wachten tot de container op het netwerk is"
IP=""
for i in $(seq 1 45); do
  IP="$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}' || true)"
  [ -n "$IP" ] && break
  sleep 2
  if [ "$i" -eq 45 ]; then warn "Geen IP-adres gevonden na 90 seconden."; fi
done
[ -n "$IP" ] || die "Container $CTID heeft geen IP gekregen (DHCP op $BRIDGE)."
log "Container bereikbaar op $IP"

log "App en inrichtscript naar de container sturen"
TARBAL_APP="$(mktemp -t morgenkrant-app.XXXXXXXX.tar.gz)"
trap 'rm -f "${TARBAL_APP:-}"' EXIT
tar czf "$TARBAL_APP" -C "$KIT" krant templates fonts build.py app.py reclean.py \
  requirements.txt README.md 2>/dev/null \
  || die "Kon de app-bestanden niet inpakken (staat de kit compleet in $KIT?)."
pct push "$CTID" "$TARBAL_APP" /root/morgenkrant-app.tar.gz
pct push "$CTID" "$KIT/deploy/proxmox/provision-morgenkrant.sh" /root/provision-morgenkrant.sh

log "Inrichten in de container (dit duurt een paar minuten)"
if ! pct exec "$CTID" -- bash /root/provision-morgenkrant.sh; then
  die "Het inrichten is mislukt. Bekijk de regels hierboven.
Opnieuw proberen: pct exec $CTID -- bash /root/provision-morgenkrant.sh
Log van de app: pct exec $CTID -- journalctl -u morgenkrant.service -n 40"
fi

cat <<EOF

────────────────────────────────────────────────────────────
 De Morgenkrant draait in container $CTID ($HOSTNAME_CT)

   Webpagina : http://$IP:$POORT
   PDF       : http://$IP:$POORT/pdf/<datum>/a4.pdf
               http://$IP:$POORT/pdf/<datum>/mobiel.pdf

 Elke ochtend om 05:30 bouwt een timer de nieuwe editie.
 Nu meteen een editie bouwen:
   pct exec $CTID -- systemctl start morgenkrant-build.service

 Controle later (op deze host):
   bash -c "\$(curl -fsSL https://raw.githubusercontent.com/Theberas04/morgenkrant/main/deploy/proxmox/check-morgenkrant.sh)"

 Krantennaam, bronnen en rubrieken aanpassen:
   pct exec $CTID -- nano /opt/morgenkrant/krant/config.py
   pct exec $CTID -- systemctl restart morgenkrant
────────────────────────────────────────────────────────────
EOF