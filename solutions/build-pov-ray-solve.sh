#!/bin/bash
set -e

# Install build dependencies
apt-get update -qq
apt-get install -y -qq build-essential wget

# Create target directory
mkdir -p /app/povray-2.2
cd /app/povray-2.2

# Download POVSRC.TAR.Z (Unix compressed tar with correct MD5 hashes)
echo "Downloading POV-Ray 2.2 source..."
wget -q "https://www.povray.org/ftp/pub/povray/Old-Versions/Official-2.2/POVSRC.TAR.Z" -O /tmp/POVSRC.TAR.Z

# Extract source to /app/povray-2.2
uncompress -c /tmp/POVSRC.TAR.Z | tar -x -C /app/povray-2.2

# Download POVDOC.TAR.Z (documentation and include files)
echo "Downloading POV-Ray 2.2 documentation and includes..."
wget -q "https://www.povray.org/ftp/pub/povray/Old-Versions/Official-2.2/POVDOC.TAR.Z" -O /tmp/POVDOC.TAR.Z

# Extract docs to /app/povray-2.2 (extracts into povdoc/ subdirectory)
uncompress -c /tmp/POVDOC.TAR.Z | tar -x -C /app/povray-2.2

# Verify key files exist
echo "Verifying source files..."
for f in file_id.diz knownbug.doc povlegal.doc whatsnew.doc \
          povdoc/include/colors.inc povdoc/include/shapes.inc; do
    if [ ! -f "/app/povray-2.2/$f" ]; then
        echo "ERROR: Missing required file: /app/povray-2.2/$f"
        exit 1
    fi
done

# Set up build directory
mkdir -p /tmp/pov_build
cd /tmp/pov_build

# Copy all source .c and .h files from the source/ directory
cp /app/povray-2.2/source/*.c .
cp /app/povray-2.2/source/*.h .

# Copy the GCC-specific unix machine file as unix.c
cp /app/povray-2.2/machine/unix/gcc.c unix.c

# Patch unix.c: 'struct libm_exception' was renamed to 'struct exception' in modern glibc.
# Replace the type name so it compiles on current systems.
sed -i 's/struct libm_exception/struct exception/g' unix.c

# Use the GCC config header as config.h
cp /app/povray-2.2/machine/unix/gccconf.h config.h

# Define the source object list (all source .c files + unix.c)
SRCS="bezier.c blob.c bound.c boxes.c camera.c colour.c cones.c csg.c \
      discs.c dump.c express.c gif.c gifdecod.c hfield.c iff.c image.c \
      lighting.c matrices.c normal.c objects.c parse.c pigment.c planes.c \
      point.c poly.c povray.c quadrics.c raw.c ray.c render.c spheres.c \
      targa.c texture.c tokenize.c triangle.c txttest.c vect.c unix.c"

# Compile flags:
# -std=gnu89    : old K&R C style function declarations
# -w            : suppress all warnings (1992 code has many)
# -O            : optimize
# -D_STDC_=1    : tells gccconf.h to use ANSI prototyping (it checks _STDC_ not __STDC__)
CFLAGS="-std=gnu89 -w -O -I. -D_STDC_=1"

echo "Compiling POV-Ray 2.2..."
for src in $SRCS; do
    obj="${src%.c}.o"
    gcc $CFLAGS -c "$src" -o "$obj"
done

# Link
OBJS=$(echo $SRCS | sed 's/\.c/.o/g')
gcc -o povray $OBJS -lm

echo "Build successful!"

# Install binary
install -m 0755 povray /usr/local/bin/povray

echo "Installed POV-Ray 2.2 at /usr/local/bin/povray"

# Verify it runs
/usr/local/bin/povray -h 2>&1 | head -5 || true

echo "Done!"
