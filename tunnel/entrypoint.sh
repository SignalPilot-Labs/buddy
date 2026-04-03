#!/bin/sh
set -e

# Wait for the dashboard to write the tunnel token
echo "[tunnel-auth] Waiting for tunnel token..."
while [ ! -f /tunnel/token.txt ] || [ ! -s /tunnel/token.txt ]; do
    sleep 1
done

export TUNNEL_TOKEN
TUNNEL_TOKEN=$(cat /tunnel/token.txt)
echo "[tunnel-auth] Token loaded, starting nginx"

envsubst '${TUNNEL_TOKEN}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
