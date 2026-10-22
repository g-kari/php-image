#!/usr/bin/env bash
# Credential-free, disposable cloud CI. Never use on production or a user's computer.
set -euo pipefail
series="${1:?}"; mode="${2:-full}"
case "$mode" in full|preflight) ;; *) exit 2;; esac
case "$series" in 7.4|8.0|8.1) ;; *) exit 2;; esac
test "${GITHUB_REPOSITORY:-}" = g-kari/php-image
test "${GITHUB_SHA:-}" != ""
python3 -c 'import ast,json,sys
from pathlib import Path
for p in [*Path("al2-official").glob("*.py"),Path("scripts/classify-ci.py")]:
    ast.parse(p.read_text(),filename=str(p))
data=json.load(open("al2-official/known-phpt-diffs.json"))
for series,mapping in data["series"].items():
    if len(mapping)!=(12 if series=="7.4" else 11):raise RuntimeError("Failure oracle inventory changed")
    for name,text in mapping.items():
        if not text.endswith("\n") or "UNCLASSIFIED" in text:raise RuntimeError("Invalid oracle")
print("QA_HARNESS_SYNTAX_AND_ORACLE_INVENTORY_PASSED")
'
python3 al2-official/test-signature-policy.py
for file in al2-official/*.sh; do bash -n "$file"; done
test ! -e out
mkdir out
base="$(python3 -c 'import json;print(json.load(open("al2-official/source-lock.json"))["base"])')"
cid=""
cleanup() {
 if [[ -n "$cid" ]]; then
  docker logs "$cid" > out/runtime-container.log 2>&1 || true
  docker rm -f "$cid" >/dev/null 2>&1 || true
 fi
}
trap cleanup EXIT
cid="$(docker run -d --platform linux/amd64 --memory 3g --cpus 2 --pids-limit 512 \
 -e CI_DISPOSABLE_BUILD=1 -v "$PWD:/work:ro" -v "$PWD/out:/out" "$base" sleep infinity)"
run_phase() {
 local phase="$1"
 if ! docker exec "$cid" bash /work/al2-official/runtime.sh "$series" "$phase" > "out/runtime-$phase.log" 2>&1; then
  tail -n 180 "out/runtime-$phase.log"; return 1
 fi
 grep -E 'PASSED|INSTALLED|AUDIT_RECORDED' "out/runtime-$phase.log" || true
}
# Cheap baseline/fixture validation precedes the 20-30 minute compiler job.
run_phase baseline
if [[ "$mode" = preflight ]]; then
 docker stop "$cid" >/dev/null
 docker logs "$cid" > out/runtime-container.log 2>&1
 docker rm "$cid" >/dev/null; cid=""
 trap - EXIT
 echo "OFFICIAL_VENDOR_BASELINE_PREFLIGHT_PASSED series=$series"
 exit 0
fi
if ! docker run --rm --platform linux/amd64 --memory 6g --cpus 2 --pids-limit 512 \
 -e CI_DISPOSABLE_BUILD=1 -v "$PWD:/work:ro" -v "$PWD/out:/out" \
 "$base" bash /work/al2-official/build.sh "$series" > out/build.log 2>&1; then
 tail -n 180 out/build.log; exit 1
fi
grep -q '^OFFICIAL_SECURITY_RPM_BUILD_PASSED ' out/build.log
# Preserve the full vendor PHPT log, but do not flood Actions' readable log transport.
grep -E '^Tests (failed|skipped|passed|warned)|^Expected fail|^Number of tests|^OFFICIAL_' out/build.log
docker exec "$cid" python3 /work/al2-official/phpt-policy.py "$series"
run_phase update
bash scripts/install-syft.sh
tools/syft "docker:$(docker commit "$cid")" -o spdx-json=out/sbom.spdx.json
run_phase rollback
docker exec "$cid" python3 /work/al2-official/licenses.py "$series"
docker exec "$cid" chown -R "$(id -u):$(id -g)" /out
docker stop "$cid" >/dev/null
docker logs "$cid" > out/runtime-container.log 2>&1
docker rm "$cid" >/dev/null; cid=""
trap - EXIT
python3 al2-official/finalize.py "$series"
cat out/qa/FINAL-RESULT.json
echo "OFFICIAL_AL2_FINAL_QA_PASSED series=$series recipe=$GITHUB_SHA"
