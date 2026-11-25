#!/usr/bin/env bash
# Controle van De Morgenkrant op de Proxmox-host.
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/Theberas04/morgenkrant/main/deploy/proxmox/check-morgenkrant.sh)"
# Of met CTID=<id> als de container een andere naam heeft.
set -uo pipefail

CTID="${CTID:-}"
POORT="${POORT:-8420}"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { printf 'Draai dit als root op de Proxmox-host.\n' >&2; exit 1; }
command -v pct >/dev/null || { printf 'pct niet gevonden: dit is geen Proxmox-host.\n' >&2; exit 1; }

if [ -z "$CTID" ]; then
  CTID="$(pct list | awk '$3=="morgenkrant"{print $1; exit}')"
fi
[ -n "$CTID" ] || { warn "Geen container met hostnaam 'morgenkrant' gevonden (pct list)."; exit 1; }

log "Container $CTID"
pct status "$CTID"

log "Diensten"
pct exec "$CTID" -- systemctl is-active morgenkrant.service || warn "webdienst niet actief"
pct exec "$CTID" -- systemctl list-timers morgenkrant-build.timer --no-pager || true

IP="$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')"
log "Adres: http://$IP:$POORT"

if command -v curl >/dev/null; then
  if curl -fsS --max-time 8 "http://$IP:$POORT/gezondheid"; then
    echo
  else
    warn "De pagina antwoordt niet op http://$IP:$POORT/gezondheid"
  fi
  DAILY="$(date +%F)"
  CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$IP:$POORT/pdf/$DAILY/a4.pdf")"
  log "PDF van vandaag: HTTP $CODE"
fi

log "Laatste build-log"
pct exec "$CTID" -- journalctl -u morgenkrant-build.service -n 8 --no-pager 2>/dev/null || true

cat <<EOF

Handig:
  pct exec $CTID -- systemctl start morgenkrant-build.service     # nu een editie bouwen
  pct exec $CTID -- nano /opt/morgenkrant/krant/config.py         # naam, bronnen, rubrieken
  pct exec $CTID -- systemctl restart morgenkrant
EOF