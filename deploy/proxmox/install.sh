#!/usr/bin/env bash
# De Morgenkrant op een Proxmox-host: haalt de kit op en start het maakscript.
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/Theberas04/morgenkrant/main/deploy/proxmox/install.sh)"
#
# Opties (env):
#   FETCH_ONLY=1     alleen de kit ophalen en controleren, niets aanmaken
#   KIT_DIR=<pad>    waar de kit komt te staan (standaard /opt/morgenkrant-kit)
#   CTID=<id>        vaste container-id in plaats van de eerst vrije
#   CORES=2 MEM=1024 SCHIJF=4
set -euo pipefail

REPO="${REPO:-Theberas04/morgenkrant}"
BRANCH="${BRANCH:-main}"
KIT="${KIT_DIR:-/opt/morgenkrant-kit}"
TARBALL=""

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fout]\033[0m %s\n' "$*" >&2; exit 1; }
trap 'rm -f "${TARBALL:-}"' EXIT

log "Kit ophalen van github.com/$REPO ($BRANCH)"
if [ -e "$KIT" ]; then
  [ -f "$KIT/deploy/proxmox/create-morgenkrant-lxc.sh" ] \
    || die "$KIT bestaat al en is niet de kit van De Morgenkrant. Kies een ander KIT_DIR."
  rm -rf "$KIT"
fi
mkdir -p "$KIT"
TARBALL="$(mktemp -t morgenkrant-kit.XXXXXXXX.tar.gz)"
curl -fsSL --retry 3 "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" -o "$TARBALL" \
  || die "Kon de kit niet ophalen van github.com/$REPO."
tar xzf "$TARBALL" -C "$KIT" --strip-components=1

for f in krant/config.py krant/fetch.py krant/render.py app.py build.py requirements.txt \
         templates/web.html templates/print.html templates/_macros.html \
         deploy/proxmox/create-morgenkrant-lxc.sh deploy/proxmox/provision-morgenkrant.sh; do
  [ -f "$KIT/$f" ] || die "De kit is onvolledig: $f ontbreekt."
done
log "Kit staat in $KIT en is compleet"

if [ "${FETCH_ONLY:-0}" = "1" ]; then
  log "FETCH_ONLY=1: niets aangemaakt, ik stop hier."
  exit 0
fi

[ "$(id -u)" -eq 0 ] || die "Draai dit als root op de Proxmox-host."
command -v pct   >/dev/null || die "pct niet gevonden: dit is geen Proxmox VE-host."
command -v pveam >/dev/null || die "pveam niet gevonden: dit is geen Proxmox VE-host."

exec bash "$KIT/deploy/proxmox/create-morgenkrant-lxc.sh"