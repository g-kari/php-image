#!/usr/bin/env bash
# Exact SDK read-only extraction; no PHP/core/C fixture compilation.
set -euo pipefail
test "$GITHUB_REPOSITORY" = g-kari/php-image
python3 -c 'import ast;from pathlib import Path
for p in Path("al2-official").glob("*.py"):ast.parse(p.read_text(),filename=str(p))
print("EXACT_SDK_HOST_SYNTAX_PASSED")'
for file in al2-official/*.sh; do bash -n "$file"; done
test ! -e out; mkdir out
base="$(python3 -c 'import json;print(json.load(open("al2-official/source-lock.json"))["base"])')"
cid=""
cleanup(){ if [[ -n "$cid" ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
cid="$(docker run -d --platform linux/amd64 --memory 2g --cpus 2 --pids-limit 256 -e CI_DISPOSABLE_BUILD=1 -v "$PWD:/work:ro" -v "$PWD/out:/out" "$base" sleep infinity)"
if ! docker exec "$cid" yum install -y yum-utils python3 cpio gnupg2 > out/sdk-bootstrap.log 2>&1; then tail -n 100 out/sdk-bootstrap.log; exit 1; fi
docker exec "$cid" python3 /work/al2-official/inspect-build-sdk.py
docker rm -f "$cid" >/dev/null; cid=""
echo EXACT_SDK_DIAGNOSTIC_ONLY_NOT_FULL_QA
