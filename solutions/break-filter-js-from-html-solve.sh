#!/bin/bash
set -e

# The filter uses BeautifulSoup with html.parser to strip:
#   - <script> tags (decomposed)
#   - <frame>, <iframe>, <object>, <embed> tags (decomposed)
#   - All "on*" event handler attributes
#
# Bypass: BeautifulSoup's html.parser misparses the malformed comment
# opener "<!-->". It treats the subsequent content as a comment and
# therefore does NOT see the <script> tag inside as a real tag —
# so it is never decomposed. Chrome's HTML parser, however, closes
# the comment immediately at "<!-->" (empty comment) and then parses
# the remaining "<script>alert(1)</script>" as live script, triggering
# the alert.

cat > /app/out.html << 'EOF'
<!-->asdf<script>alert(1)</script> -->
EOF
