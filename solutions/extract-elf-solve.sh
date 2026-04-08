#!/bin/bash
set -e

cat > /app/extract.js << 'JSEOF'
const fs = require('fs');

function parseELF(filePath) {
    const buf = fs.readFileSync(filePath);

    // Check ELF magic
    if (buf[0] !== 0x7f || buf[1] !== 0x45 || buf[2] !== 0x4c || buf[3] !== 0x46) {
        throw new Error('Not an ELF file');
    }

    const is64 = buf[4] === 2;
    const isLE = buf[5] === 1;

    function readU16(offset) {
        return isLE ? buf.readUInt16LE(offset) : buf.readUInt16BE(offset);
    }
    function readU32(offset) {
        return isLE ? buf.readUInt32LE(offset) : buf.readUInt32BE(offset);
    }
    function readU64(offset) {
        if (isLE) {
            const lo = buf.readUInt32LE(offset);
            const hi = buf.readUInt32LE(offset + 4);
            return hi * 0x100000000 + lo;
        } else {
            const hi = buf.readUInt32BE(offset);
            const lo = buf.readUInt32BE(offset + 4);
            return hi * 0x100000000 + lo;
        }
    }
    function readAddr(offset) {
        return is64 ? readU64(offset) : readU32(offset);
    }
    function readOff(offset) {
        return is64 ? readU64(offset) : readU32(offset);
    }

    // ELF header
    let e_shoff, e_shentsize, e_shnum, e_shstrndx;
    if (is64) {
        e_shoff = readU64(40);
        e_shentsize = readU16(58);
        e_shnum = readU16(60);
        e_shstrndx = readU16(62);
    } else {
        e_shoff = readU32(32);
        e_shentsize = readU16(46);
        e_shnum = readU16(48);
        e_shstrndx = readU16(50);
    }

    // Read section headers
    const sections = [];
    for (let i = 0; i < e_shnum; i++) {
        const base = e_shoff + i * e_shentsize;
        let sh;
        if (is64) {
            sh = {
                sh_name: readU32(base),
                sh_type: readU32(base + 4),
                sh_flags: readU64(base + 8),
                sh_addr: readU64(base + 16),
                sh_offset: readU64(base + 24),
                sh_size: readU64(base + 32),
            };
        } else {
            sh = {
                sh_name: readU32(base),
                sh_type: readU32(base + 4),
                sh_flags: readU32(base + 8),
                sh_addr: readU32(base + 12),
                sh_offset: readU32(base + 16),
                sh_size: readU32(base + 20),
            };
        }
        sections.push(sh);
    }

    // Read section name string table
    const strtab = sections[e_shstrndx];
    function getSectionName(nameOffset) {
        let end = strtab.sh_offset + nameOffset;
        while (buf[end] !== 0 && end < buf.length) end++;
        return buf.slice(strtab.sh_offset + nameOffset, end).toString('ascii');
    }

    // Find target sections
    const targetSections = ['.text', '.data', '.rodata'];
    const result = {};

    for (const section of sections) {
        const name = getSectionName(section.sh_name);
        if (targetSections.includes(name) && section.sh_size > 0) {
            // Read 4-byte words
            const numWords = Math.floor(section.sh_size / 4);
            for (let i = 0; i < numWords; i++) {
                const fileOffset = section.sh_offset + i * 4;
                const addr = section.sh_addr + i * 4;
                const value = isLE ? buf.readUInt32LE(fileOffset) : buf.readUInt32BE(fileOffset);
                result[addr] = value;
            }
        }
    }

    console.log(JSON.stringify(result));
}

const filePath = process.argv[2];
if (!filePath) {
    console.error('Usage: node extract.js <elf-file>');
    process.exit(1);
}

parseELF(filePath);
JSEOF

echo "ELF extractor written to /app/extract.js"

# Test with existing ELF files if available
if [ -f /app/test.o ]; then
    node /app/extract.js /app/test.o | head -c 200
fi
