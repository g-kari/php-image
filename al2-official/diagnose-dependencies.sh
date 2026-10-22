#!/usr/bin/env bash
# Short evidence only; no compiler, publication, production host or user computer.
set -euo pipefail
test "${GITHUB_REPOSITORY:-}" = g-kari/php-image
python3 -c 'import ast;from pathlib import Path
for p in Path("al2-official").glob("*.py"):ast.parse(p.read_text(),filename=str(p))
print("DEPENDENCY_DIAGNOSTIC_HOST_SYNTAX_PASSED")'
for file in al2-official/*.sh; do bash -n "$file"; done
python3 - <<'PY'
import ast,re
from pathlib import Path
tree=ast.parse(Path("al2-official/dependency-inventory.py").read_text())
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="validate_optional_rpm"]
if len(functions)!=1:raise RuntimeError("Optional RPM policy missing")
ns={"re":re}
exec(compile(ast.Module(body=functions,type_ignores=[]),"optional-rpm-policy","exec"),ns)
check=ns["validate_optional_rpm"]
check("libcurl-devel",{"returncode":0,"output":"libcurl-devel|0|8.3.0|1.amzn2.0.13|x86_64\n"})
check("postgresql-devel",{"returncode":1,"output":"package postgresql-devel is not installed\n"})
for name,result in [
 ("libcurl-devel",{"returncode":1,"output":"rpm database failure\n"}),
 ("libcurl-devel",{"returncode":2,"output":"package libcurl-devel is not installed\n"}),
 ("libcurl-devel",{"returncode":0,"output":"package libcurl-devel is not installed\n"}),
 ("libcurl-devel",{"returncode":0,"output":"postgresql-devel|0|8.3.0|1.amzn2.0.13|x86_64\n"}),
 ("postgresql-devel",{"returncode":1,"output":"package postgresql-devel is not installed\nunexpected\n"})]:
 try:check(name,result)
 except RuntimeError:pass
 else:raise RuntimeError("Optional SDK policy accepted unexpected query output")
print("OPTIONAL_RPM_DIAGNOSTIC_POLICY_UNIT_PASSED")
PY
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
 mounts=(-v "$PWD:/work:ro" -v "$PWD/out/$series:/out")
 if [[ "$series" != 7.4 ]]; then mounts+=(-v "$PWD/out/7.4/dependency-diagnostic:/sdk-evidence:ro"); fi
 cid="$(docker run -d --platform linux/amd64 --memory 3g --cpus 2 --pids-limit 512 -e CI_DISPOSABLE_BUILD=1 "${mounts[@]}" "$base" sleep infinity)"
 if ! docker exec "$cid" bash /work/al2-official/acquire-vendor.sh "$series" > "out/$series/baseline.log" 2>&1; then
  tail -n 160 "out/$series/baseline.log"; exit 1
 fi
 grep -E 'PASSED|INSTALLED|AUDIT_RECORDED' "out/$series/baseline.log" || true
 docker exec "$cid" python3 /work/al2-official/audit-pecl.py "$series" /out/qa/vendor-pecl-audit.json
 docker exec "$cid" python3 /work/al2-official/dependency-inventory.py "$series"
 docker rm -f "$cid" >/dev/null; cid=""
done
echo DEPENDENCY_DIAGNOSTIC_ONLY_NOT_FULL_QA
