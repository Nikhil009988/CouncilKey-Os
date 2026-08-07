#!/usr/bin/env bash
# verify-no-traces.sh - Audit CouncilKey-Os for leftover temp/cache traces.
#
# Usage:
#   ./scripts/verify-no-traces.sh            # audit only (exit 1 on any FAIL)
#   ./scripts/verify-no-traces.sh --clean    # audit + delete found traces
set -uo pipefail

COUNCIL_HOME="${COUNCIL_HOME:-/var/lib/council}"
CLEAN=0
[ "${1:-}" = "--clean" ] && CLEAN=1

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "✅ PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "❌ FAIL: $1"; }

[ -d "$COUNCIL_HOME" ] || { echo "council home $COUNCIL_HOME does not exist - nothing to audit"; echo ""; echo "verify-no-traces: 0 PASS 0 FAIL"; exit 0; }

echo "verify-no-traces: auditing $COUNCIL_HOME (clean=$CLEAN)"
echo ""

# 1. Temporary files (*.tmp, *.temp, *.swp, *~, core dumps)
n=$(find "$COUNCIL_HOME" -type f \( -name '*.tmp' -o -name '*.temp' -o -name '*.swp' -o -name '*~' -o -name 'core.*' \) 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then pass "no temp files"; else fail "temp files found: $n"; [ "$CLEAN" -eq 1 ] && find "$COUNCIL_HOME" -type f \( -name '*.tmp' -o -name '*.temp' -o -name '*.swp' -o -name '*~' -o -name 'core.*' \) -delete 2>/dev/null; fi

# 2. Log files
n=$(find "$COUNCIL_HOME" -type f -name '*.log' 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then pass "no log files"; else fail "log files found: $n"; [ "$CLEAN" -eq 1 ] && find "$COUNCIL_HOME" -type f -name '*.log' -delete 2>/dev/null; fi

# 3. Python bytecode caches
n=$(find "$COUNCIL_HOME" -type d -name '__pycache__' 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then pass "no __pycache__ dirs"; else fail "__pycache__ dirs found: $n"; [ "$CLEAN" -eq 1 ] && find "$COUNCIL_HOME" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null; fi

# 4. Package manager caches (.cache, .npm, .pip, .cache/pip)
n=$(find "$COUNCIL_HOME" -type d \( -name '.cache' -o -name '.npm' -o -name '.pip' \) 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then pass "no package-manager caches"; else fail "package-manager cache dirs: $n"; [ "$CLEAN" -eq 1 ] && find "$COUNCIL_HOME" -type d \( -name '.cache' -o -name '.npm' -o -name '.pip' \) -exec rm -rf {} + 2>/dev/null; fi

# 5. Cache RAM usage under 512MB (heavy RAW data should be flushed on unplug)
cache_total=$(du -sb "$COUNCIL_HOME"/hermes/cache "$COUNCIL_HOME"/openclaw/cache "$COUNCIL_HOME"/codex/cache 2>/dev/null | awk '{s+=$1} END {print s+0}')
cache_mb=$((cache_total / 1024 / 1024))
if [ "$cache_total" -lt 536870912 ]; then pass "cache RAM under 512MB (${cache_mb}MB)"; else fail "cache RAM too big: ${cache_mb}MB"; fi

# 6. Browser profiles / private browsing leftovers
n=$(find "$COUNCIL_HOME" -type d \( -name '.mozilla' -o -name '.config' -o -name 'camofox*' -o -name '.chrome*' \) 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then pass "no browser profile leftovers"; else fail "browser profile dirs: $n"; [ "$CLEAN" -eq 1 ] && find "$COUNCIL_HOME" -type d \( -name '.mozilla' -o -name '.config' -o -name 'camofox*' -o -name '.chrome*' \) -exec rm -rf {} + 2>/dev/null; fi

# 7. /tmp/council leaks (mount-ram should vanish on unplug)
if [ -d /tmp/council ]; then
  fail "/tmp/council still exists (RAM tmpfs leak)"; [ "$CLEAN" -eq 1 ] && rm -rf /tmp/council
else
  pass "no /tmp/council leak"
fi

echo ""
echo "verify-no-traces: $PASS PASS, $FAIL FAIL"
[ "$FAIL" -eq 0 ]
