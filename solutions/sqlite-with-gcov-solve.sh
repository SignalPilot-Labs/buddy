#!/bin/bash
set -e

apt-get update && apt-get install -y build-essential gcc make tcl

mkdir -p /app/sqlite
cd /app/sqlite

# Extract the vendored source
tar xzf /app/vendor/sqlite-fossil-release.tar.gz --strip-components=1 || tar xzf /app/vendor/sqlite-fossil-release.tar.gz

# If there's a configure script, use it
if [ -f configure ]; then
    CFLAGS="--coverage" ./configure --prefix=/usr/local
    make -j$(nproc)
    make install
elif [ -f Makefile ]; then
    make CFLAGS="--coverage" -j$(nproc)
else
    # Amalgamation build
    gcc --coverage -o sqlite3 shell.c sqlite3.c -lpthread -ldl -lm
    cp sqlite3 /usr/local/bin/
fi

# Verify
which sqlite3
sqlite3 :memory: "SELECT sqlite_version();"
echo "SQLite built with gcov instrumentation!"
ls -la /app/sqlite/*.gcno 2>/dev/null || find /app/sqlite -name "*.gcno" | head -5
