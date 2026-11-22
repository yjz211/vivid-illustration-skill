#!/bin/sh
# figure_check.sh — POSIX wrapper delegating to cross-platform figure_check.py
PY=""
for _c in "$VIVID_PYTHON" python3 python; do
    [ -z "$_c" ] && continue
    if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "import sys" >/dev/null 2>&1; then
        PY="$_c"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "CRITICAL: Python 3 interpreter not found (set VIVID_PYTHON or install python3)" >&2
    exit 1
fi
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 exec "$PY" "$(dirname "$0")/figure_check.py" "$@"
