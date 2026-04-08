#!/bin/bash
set -e

apt-get update
apt-get install -y build-essential dpkg-dev libncurses-dev

# Enable source repositories
echo 'deb-src http://deb.debian.org/debian stable main' >> /etc/apt/sources.list.d/deb-src.list 2>/dev/null || true
sed -i 's/^# deb-src/deb-src/' /etc/apt/sources.list 2>/dev/null || true
sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/*.sources 2>/dev/null || true
apt-get update

# Get pMARS source
cd /app
apt-get source pmars

# Build curses (headless) version - no X11
cd /app/pmars-*/src

# Remove X11 graphics flag and link against ncurses instead of X11
sed -i 's/-DXWINGRAPHX//g' Makefile
sed -i 's/^LIB *=.*/LIB = -lncurses/' Makefile

make clean 2>/dev/null || true
make

# Install
install -m 0755 pmars /usr/local/bin/pmars

echo "=== Installed pmars ==="
which pmars
ldd /usr/local/bin/pmars
echo "Done!"
