#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"; action="${2:?}"
test "${CI_DISPOSABLE_BUILD:-}" = 1 && test -f /.dockerenv
case "$series" in 7.4|8.0|8.1) ;; *) exit 2;; esac
if [[ "$action" = baseline ]]; then
 bash /work/al2-official/acquire-vendor.sh "$series"
 python3 - <<'PY'
import json,pathlib
# Harmless private-fixture comments, not a production configuration migration.
files=["/etc/php.ini","/etc/php-fpm.d/www.conf","/etc/httpd/conf.d/php.conf","/etc/php.d/20-calendar.ini"]
for name in files:
 p=pathlib.Path(name)
 if not p.is_file():raise RuntimeError("Expected baseline config missing: "+name)
 marker="\n# CI local config preservation fixture\n" if name.endswith("php.conf") else "\n; CI local config preservation fixture\n"
 p.write_text(p.read_text()+marker)
pathlib.Path("/out/qa/local-config-fixtures.json").write_text(json.dumps(files))
PY
 python3 /work/al2-official/audit-pecl.py "$series" /out/qa/vendor-pecl-audit.json
 python3 /work/al2-official/snapshot-invariants.py "$series" vendor
 bash /work/al2-official/phase.sh "$series" vendor
elif [[ "$action" = update ]]; then
 python3 /work/al2-official/compare-rpms.py /out/vendor/main /out/rpms "$series" /out/qa/rpm-comparison.json
 mapfile -t cohort < <(find /out/rpms -maxdepth 1 -type f -name '*.rpm' ! -name '*debuginfo*' ! -name '*debugsource*' | sort)
 test "${#cohort[@]}" -ge 26
 # No --nodeps, --replacefiles, --nogpgcheck or repository security-policy override.
 yum localupdate -y "${cohort[@]}"
 python3 /work/al2-official/snapshot-invariants.py "$series" patched
 bash /work/al2-official/phase.sh "$series" patched
elif [[ "$action" = rollback ]]; then
 # Only this disposable QA container is restored to the saved original cohort.
 # A real rollback to these versions reintroduces the two CVEs.
 yum downgrade -y /out/vendor/main/*.rpm
 python3 /work/al2-official/snapshot-invariants.py "$series" rollback
 bash /work/al2-official/phase.sh "$series" rollback
 python3 /work/al2-official/validate-results.py "$series"
else
 exit 2
fi
