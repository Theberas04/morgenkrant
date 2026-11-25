#!/usr/bin/env bash
# Richt De Morgenkrant in binnen de container. Wordt door create-morgenkrant-lxc.sh
# als /root/provision-morgenkrant.sh naar binnen gestuurd.
set -euo pipefail

APP=/opt/morgenkrant
POORT="${POORT:-8420}"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fout]\033[0m %s\n' "$*" >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive

log "Pakketten installeren"
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq --no-install-recommends \
  python3 python3-venv python3-pip ca-certificates curl \
  libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
  shared-mime-info fonts-dejavu-core >/dev/null || die "apt-get install is mislukt."

log "App uitpakken in $APP"
mkdir -p "$APP"
tar xzf /root/morgenkrant-app.tar.gz -C "$APP"
[ -f "$APP/app.py" ] || die "app.py ontbreekt na het uitpakken."

log "Python-omgeving bouwen"
python3 -m venv "$APP/.venv" || die "Kon geen venv maken (python3-venv ontbreekt?)."
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt" || die "pip install is mislukt."
"$APP/.venv/bin/python" -c "import flask, weasyprint, trafilatura" \
  || die "De app kan zijn pakketten niet importeren."

log "Diensten aanmaken"
cat > /etc/systemd/system/morgenkrant.service <<EOF
[Unit]
Description=De Morgenkrant - webpagina
After=network-online.target

[Service]
WorkingDirectory=$APP
Environment=PORT=$POORT
ExecStart=$APP/.venv/bin/python $APP/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/morgenkrant-build.service <<EOF
[Unit]
Description=De Morgenkrant - ochtendeditie bouwen
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$APP
ExecStart=$APP/.venv/bin/python $APP/build.py
TimeoutStartSec=1800
EOF

cat > /etc/systemd/system/morgenkrant-build.timer <<EOF
[Unit]
Description=De Morgenkrant - elke ochtend om 05:30

[Timer]
OnCalendar=*-*-* 05:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now morgenkrant.service >/dev/null
systemctl enable --now morgenkrant-build.timer >/dev/null

log "Eerste editie bouwen (kan twee minuten duren)"
if systemctl start morgenkrant-build.service; then
  systemctl is-active --quiet morgenkrant-build.service || true
else
  warn "De eerste editie bouwen ging mis. Log: journalctl -u morgenkrant-build.service -n 40"
fi

systemctl is-active --quiet morgenkrant.service \
  || die "De webdienst draait niet. Log: journalctl -u morgenkrant.service -n 40"

for i in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$POORT/gezondheid" 2>/dev/null; then break; fi
  sleep 2
  if [ "$i" -eq 30 ]; then warn "De gezondheidscontrole antwoordt nog niet; de dienst draait wel."; fi
done

EDITIE="$(curl -fsS "http://127.0.0.1:$POORT/gezondheid" 2>/dev/null || echo '{}')"
log "Klaar. Laatste editie: $EDITIE"
log "Timer: $(systemctl list-timers morgenkrant-build.timer --no-pager 2>/dev/null | sed -n 2p || echo 'onbekend')"