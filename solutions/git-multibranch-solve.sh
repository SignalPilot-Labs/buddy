#!/bin/bash
set -e

# Create git user and set password for SSH password authentication
useradd -m git || true
echo "git:password" | chpasswd

# Set up SSH directory for git user
mkdir -p /home/git/.ssh
chmod 700 /home/git/.ssh
touch /home/git/.ssh/authorized_keys
chmod 600 /home/git/.ssh/authorized_keys
chown -R git:git /home/git/.ssh

# Allow password authentication in SSH config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
# Ensure UsePAM is enabled so password auth works
sed -i 's/^#\?UsePAM.*/UsePAM yes/' /etc/ssh/sshd_config

# Create web deploy directories and grant git user ownership
mkdir -p /var/www/html /var/www/dev
chown -R git:git /var/www/html /var/www/dev

# Initialize bare Git repository at the expected SSH path
mkdir -p /git/project
cd /git/project
git init --bare
chown -R git:git /git

# Write post-receive hook to deploy main and dev branches
cat > /git/project/hooks/post-receive << 'HOOK'
#!/bin/bash
set -e
while read oldrev newrev ref; do
    branch=$(basename "$ref")
    TMP_DIR=$(mktemp -d)
    GIT_WORK_TREE="$TMP_DIR" git checkout -f "$branch"
    if [ "$branch" = "main" ]; then
        cp "$TMP_DIR/index.html" /var/www/html/index.html
    elif [ "$branch" = "dev" ]; then
        cp "$TMP_DIR/index.html" /var/www/dev/index.html
    fi
    rm -rf "$TMP_DIR"
done
HOOK

chmod +x /git/project/hooks/post-receive
chown git:git /git/project/hooks/post-receive

# Generate self-signed SSL certificate if not already present
mkdir -p /etc/ssl/certs /etc/ssl/private
if [ ! -f /etc/ssl/certs/nginx-selfsigned.crt ]; then
    openssl req -x509 -nodes -days 365 \
        -subj "/CN=localhost" \
        -newkey rsa:2048 \
        -keyout /etc/ssl/private/nginx-selfsigned.key \
        -out /etc/ssl/certs/nginx-selfsigned.crt
fi

# Write Nginx config for HTTPS with main and dev branch paths
# /dev location uses root /var/www so that /dev/index.html maps to /var/www/dev/index.html
cat > /etc/nginx/sites-available/default << 'NGINX'
server {
    listen 8443 ssl;
    server_name localhost;

    ssl_certificate /etc/ssl/certs/nginx-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/nginx-selfsigned.key;

    location / {
        root /var/www/html;
        index index.html;
    }

    location /dev {
        root /var/www;
        index index.html;
    }
}
NGINX

# Enable the site (symlink if not already present)
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Remove default nginx site that may conflict
rm -f /etc/nginx/sites-enabled/default.conf 2>/dev/null || true

# Test nginx configuration
nginx -t

# Start SSH daemon
mkdir -p /run/sshd
/usr/sbin/sshd

# Start Nginx
nginx

echo "Setup complete: SSH git server and Nginx HTTPS reverse proxy are running."
