#!/usr/bin/env bash
# Short evidence only; no compiler, publication, production host or user computer.
set -euo pipefail
test "${GITHUB_REPOSITORY:-}" = g-kari/php-image
python3 -c 'import ast;from pathlib import Path
for p in Path("al2-official").glob("*.py"):ast.parse(p.read_text(),filename=str(p))
print("DEPENDENCY_DIAGNOSTIC_HOST_SYNTAX_PASSED")'
for file in al2-official/*.sh; do bash -n "$file"; done
test ! -e out
mkdir out
base="$(python3 -c 'import json;print(json.load(open("al2-official/source-lock.json"))["base"])')"
cid=""
cleanup() {
 if [[ -n "$cid" ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
for series in 7.4 8.0 8.1; do
 mkdir "out/$series"
 cid="$(docker run -d --platform linux/amd64 --memory 3g --cpus 2 --pids-limit 512 -e CI_DISPOSABLE_BUILD=1 -v "$PWD:/work:ro" -v "$PWD/out/$series:/out" "$base" sleep infinity)"
 if ! docker exec "$cid" bash /work/al2-official/runtime.sh "$series" baseline > "out/$series/baseline.log" 2>&1; then
  tail -n 160 "out/$series/baseline.log"; exit 1
 fi
 grep -E 'PASSED|INSTALLED|AUDIT_RECORDED' "out/$series/baseline.log" || true
 docker exec "$cid" python3 /work/al2-official/dependency-inventory.py "$series"
 docker rm -f "$cid" >/dev/null; cid=""
done
echo DEPENDENCY_DIAGNOSTIC_ONLY_NOT_FULL_QA
