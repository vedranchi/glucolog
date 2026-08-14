#!/usr/bin/env bash
# Keep the DuckDNS record pointed at this VM's current public IP.
# Only needed if the Oracle public IP is NOT reserved (ephemeral IPs can change).
#
# Usage:
#   DUCKDNS_DOMAIN=glucolog DUCKDNS_TOKEN=<your-token> ./deploy/duckdns.sh
#
# Cron (every 5 minutes):
#   */5 * * * * DUCKDNS_DOMAIN=glucolog DUCKDNS_TOKEN=xxxx /opt/glucolog/deploy/duckdns.sh >> /var/log/duckdns.log 2>&1
#
# (domains= takes the subdomain only, e.g. "glucolog" for glucolog.duckdns.org;
#  ip= left empty lets DuckDNS use the requesting IP.)
set -euo pipefail

DOMAIN="${DUCKDNS_DOMAIN:?set DUCKDNS_DOMAIN (subdomain only, e.g. glucolog)}"
TOKEN="${DUCKDNS_TOKEN:?set DUCKDNS_TOKEN}"

result=$(curl -fsS "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=")
echo "$(date -Is) duckdns: ${result}"
[ "${result}" = "OK" ]
