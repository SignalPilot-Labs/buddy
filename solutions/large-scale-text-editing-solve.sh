#!/bin/bash
# Solution for large-scale-text-editing challenge
# Transforms /app/input.csv using Vim macros written to /app/apply_macros.vim
#
# Each input row: " field1 , field2 , field3 "
# Each output row: FIELD3;FIELD2;FIELD1;OK
#
# 3 macros:
#   a — strip leading/trailing whitespace and spaces around commas
#   b — reorder comma-separated fields: f1,f2,f3 → f3;f2;f1
#   c — uppercase entire line and append ;OK
#
# Total keystrokes: ~100 (well under 200 limit)

set -e

cat > /app/apply_macros.vim << 'VIMEOF'
call setreg('a', ":s/^\\s*//\<CR>:s/\\s*$//\<CR>:s/\\s*,\\s*/,/g\<CR>")
:%normal! @a
call setreg('b', ":s/\\([^,]*\\),\\([^,]*\\),\\(.*\\)/\\3;\\2;\\1/\<CR>")
:%normal! @b
call setreg('c', ":s/.*/\\U&;OK/\<CR>")
:%normal! @c
:wq
VIMEOF

echo "Macros written to /app/apply_macros.vim:"
cat /app/apply_macros.vim

vim -s /app/apply_macros.vim /app/input.csv

echo "Transformation complete. First 5 lines of output:"
head -5 /app/input.csv
