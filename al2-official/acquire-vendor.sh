#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
test "${CI_DISPOSABLE_BUILD:-}" = 1 && test -f /.dockerenv
case "$series" in 7.4|8.0|8.1) ;; *) exit 2;; esac
. /etc/os-release
test "$ID" = amzn && test "$VERSION_ID" = 2 && test "$(uname -m)" = x86_64
yum install -y amazon-linux-extras yum-utils python3 binutils gcc cpio make gzip tar diffutils curl openssl ca-certificates
amazon-linux-extras enable "php$series"
topic="amzn2extra-php$series"; source="$topic-source"
mkdir -p /out/vendor/{main,pecl,sources} /out/qa
yum repolist -v > /out/qa/vendor-repositories.txt
python3 - "$series" <<'PY' > /tmp/vendor-main-requests
import json,sys
s=sys.argv[1];p=json.load(open("/work/al2-official/source-lock.json"))["series"][s]
names=json.load(open("/work/al2-official/packages.json"))["main"][s]
for name in names:print(name+"-"+p["version"]+"-"+p["release"]+".x86_64")
PY
mapfile -t requests < /tmp/vendor-main-requests
yumdownloader --disablerepo='*' --enablerepo="$topic" --destdir=/out/vendor/main "${requests[@]}"
verify_signature() {
 local package="$1" report="$2"
 rpm --checksig --verbose "$package" > "$report"
 grep -Eiq 'RSA.*[Ss]ignature.*key ID c87f5b1a: OK' "$report"
 if grep -Eiq 'NOKEY|NOT OK|BAD|NOTTRUSTED' "$report"; then exit 1; fi
}
for file in /out/vendor/main/*.rpm; do verify_signature "$file" "/out/qa/$(basename "$file").signature.txt"; done
python3 - "$series" <<'PY' > /tmp/vendor-pecl-requests
import json,sys
for item in json.load(open("/work/al2-official/packages.json"))["pecl"][sys.argv[1]]:
 print("|".join([item["name"],item["version"],item["release"],item["sha256"]]))
PY
while IFS='|' read -r name version release sha; do
 test -n "$name" || continue
 yumdownloader --disablerepo='*' --enablerepo="$topic" --destdir=/out/vendor/pecl "$name-$version-$release.x86_64"
 yumdownloader --source --disablerepo='*' --enablerepo="$topic" --enablerepo="$source" --destdir=/out/vendor/sources "$name-$version-$release"
 case "$name" in
 php-pecl-apcu|php-pecl-igbinary|php-pecl-imagick|php-pecl-msgpack)
  yumdownloader --disablerepo='*' --enablerepo="$topic" --destdir=/out/vendor/pecl "$name-devel-$version-$release.noarch"
 ;;
 esac
 file="/out/vendor/sources/$name-$version-$release.src.rpm"
 printf '%s  %s\n' "$sha" "$file" | sha256sum -c -
 test "$(rpm -qp --qf '%{NAME}|%{VERSION}|%{RELEASE}' "$file")" = "$name|$version|$release"
 verify_signature "$file" "/out/qa/$(basename "$file").signature.txt"
done < /tmp/vendor-pecl-requests
for file in /out/vendor/pecl/*.rpm; do
 test -e "$file" || continue
 verify_signature "$file" "/out/qa/$(basename "$file").signature.txt"
done
# Keep the OS/repository security policy unchanged. Local signature enforcement is not disabled.
yum install -y /out/vendor/main/*.rpm
if compgen -G '/out/vendor/pecl/*.rpm' > /dev/null; then yum install -y /out/vendor/pecl/*.rpm; fi
yum install -y php-pear
rpm -qa | sort > /out/qa/vendor-environment-rpms.txt
find /out/vendor -type f -name '*.rpm' -print0 | sort -z | xargs -0 sha256sum > /out/qa/vendor-rpm-sha256.txt
echo "OFFICIAL_VENDOR_COHORT_INSTALLED series=$series"
