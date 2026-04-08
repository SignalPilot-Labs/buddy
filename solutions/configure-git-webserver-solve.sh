#!/bin/bash
set -e

DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git nginx openssh-server

# Create git user with home directory and password
adduser --disabled-password --gecos 'Git' --shell /bin/bash --home /home/git git 2>/dev/null || true
echo "git:password" | chpasswd

# Set up SSH
mkdir -p /home/git/.ssh
touch /home/git/.ssh/authorized_keys
chmod 700 /home/git/.ssh
chmod 600 /home/git/.ssh/authorized_keys
chown -R git:git /home/git/.ssh

# Create bare git repo as git user
mkdir -p /git/server
chown -R git:git /git
su - git -c "git init --bare /git/server"

# Create webroot
mkdir -p /var/www/html
chown -R git:git /var/www/html

# Create post-receive hook
cat > /git/server/hooks/post-receive << 'EOF'
#!/bin/bash
GIT_WORK_TREE=/var/www/html git checkout -f
EOF
chmod +x /git/server/hooks/post-receive
chown git:git /git/server/hooks/post-receive

# Configure nginx on port 8080
cat > /etc/nginx/conf.d/git-site.conf << 'EOF'
server {
    listen 8080;
    server_name localhost;
    root /var/www/html;
    location / {
        try_files $uri $uri/ =404;
    }
}
EOF
rm -f /etc/nginx/sites-enabled/default

# Start services
service ssh start
service nginx start

echo "Setup complete!"
