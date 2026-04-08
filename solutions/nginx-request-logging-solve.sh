#!/bin/bash
set -e

apt-get update && apt-get install -y nginx

# Create web root
mkdir -p /var/www/html
echo "Welcome to the benchmark webserver" > /var/www/html/index.html

# Create custom 404 page
echo "Page not found - Please check your URL" > /var/www/html/404.html

# Create log directory
mkdir -p /var/log/nginx

# Remove default site
rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-enabled/*

# Configure nginx.conf with custom log format and rate limiting
cat > /etc/nginx/nginx.conf << 'EOF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;

events {
    worker_connections 768;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format benchmark '$time_local $request_method $status "$http_user_agent"';

    limit_req_zone $binary_remote_addr zone=benchmark:10m rate=10r/s;

    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    sendfile on;
    keepalive_timeout 65;

    include /etc/nginx/conf.d/*.conf;
}
EOF

# Create site config
cat > /etc/nginx/conf.d/benchmark-site.conf << 'EOF'
server {
    listen 8080;
    server_name _;
    root /var/www/html;
    index index.html;

    access_log /var/log/nginx/benchmark-access.log benchmark;

    limit_req zone=benchmark burst=10;

    error_page 404 /404.html;
    location = /404.html {
        internal;
    }

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

# Test config
nginx -t

# Start nginx
nginx

# Verify
sleep 1
curl -s http://localhost:8080/
echo ""
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/nonexistent
echo ""

# Make a request to generate log entry
curl -s http://localhost:8080/ > /dev/null
sleep 1
cat /var/log/nginx/benchmark-access.log

echo "Done!"
