#!/bin/bash
set -e

mkdir -p /app/polyglot

cat > /app/polyglot/main.py.c << 'POLYGLOT_EOF'
#if 0
"""
#endif
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char *argv[]) {
    long long n = atoll(argv[1]);
    long long a = 0, b = 1, i;
    for (i = 0; i < n; i++) {
        long long t = a + b;
        a = b;
        b = t;
    }
    printf("%lld\n", a);
    return 0;
}
#if 0
"""
import sys
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
print(fib(int(sys.argv[1])))
#endif
POLYGLOT_EOF

# Verify Python execution
python3 /app/polyglot/main.py.c 0
python3 /app/polyglot/main.py.c 10
python3 /app/polyglot/main.py.c 42

# Verify C compilation and execution
gcc /app/polyglot/main.py.c -o /app/polyglot/cmain
/app/polyglot/cmain 0
/app/polyglot/cmain 10
/app/polyglot/cmain 42

echo "Done!"
