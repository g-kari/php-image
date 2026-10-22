#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
test "${CI_DISPOSABLE_BUILD:-}" = 1 && test -f /.dockerenv
case "$series" in 7.4|8.0|8.1|8.2) ;; *) exit 2;; esac
. /etc/os-release
test "$ID" = amzn && test "$VERSION_ID" = 2 && test "$(uname -m)" = x86_64
yum install -y amazon-linux-extras yum-utils rpm-build cpio git patch python3
amazon-linux-extras enable "php$series"
binary="amzn2extra-php$series"
source="$binary-source"
yum repolist all
mkdir -p /tmp/acquire /out
python3 - "$series" <<'PY' > /tmp/pins
import json,sys
p=json.load(open("/work/al2-official/source-lock.json"))["series"][sys.argv[1]]
for k in ["srpm","sha256","version","release","commit","parent","trivial"]: print(p[k])
PY
mapfile -t pins < /tmp/pins
srpm="${pins[0]}"; expected="${pins[1]}"; commit="${pins[4]}"; parent="${pins[5]}"
yumdownloader --source --disablerepo='*' --enablerepo="$binary" --enablerepo="$source" --destdir=/tmp/acquire "php-${pins[2]}-${pins[3]}"
test "$(find /tmp/acquire -type f -name '*.src.rpm' | wc -l)" -eq 1
test -f "/tmp/acquire/$srpm"
printf '%s  %s\n' "$expected" "/tmp/acquire/$srpm" | sha256sum -c -
rpm --checksig --verbose "/tmp/acquire/$srpm" | tee /out/official-srpm-signature.txt
grep -Eq '(RSA|DSA).*[Ss]ignature.*: OK' /out/official-srpm-signature.txt
if grep -Eiq 'NOKEY|NOT OK|BAD|NOTTRUSTED' /out/official-srpm-signature.txt; then exit 1; fi
test "$(rpm -qp --qf '%{NAME}|%{VERSION}|%{RELEASE}' "/tmp/acquire/$srpm")" = "php|${pins[2]}|${pins[3]}"
useradd -m builder
install -d -o builder -g builder /home/builder/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cp "/tmp/acquire/$srpm" /out/original-"$srpm"
# RPM payload and vendor spec are data until the unprivileged preparation phase below.
cd /home/builder/rpmbuild/SOURCES
rpm2cpio "/tmp/acquire/$srpm" | cpio -idm --no-absolute-filenames
test -f php.spec
cp php.spec /out/official-php.spec
mv php.spec /home/builder/rpmbuild/SPECS/official-php.spec
mkdir /tmp/official-php-git
git -C /tmp/official-php-git init -q
git -C /tmp/official-php-git remote add origin https://github.com/php/php-src.git
git -C /tmp/official-php-git fetch --depth=2 --no-tags origin "$commit"
test "$(git -C /tmp/official-php-git rev-parse FETCH_HEAD)" = "$commit"
test "$(git -C /tmp/official-php-git rev-parse "$commit^")" = "$parent"
git -C /tmp/official-php-git show --no-patch --format=fuller "$commit" > /out/upstream-security-commit.txt
git -C /tmp/official-php-git diff --binary --full-index "$parent" "$commit" > php-upstream-cve2026.patch
test -s php-upstream-cve2026.patch
cp php-upstream-cve2026.patch /out/
sha256sum php-upstream-cve2026.patch > /out/upstream-security-patch.sha256
git -C /tmp/official-php-git diff --name-only "$parent" "$commit" > /out/upstream-security-patch-files.txt
python3 /work/al2-official/prepare-spec.py /home/builder/rpmbuild/SPECS/official-php.spec /home/builder/rpmbuild/SPECS/php.spec /work/al2-official/source-lock.json "$series" | tee /out/spec-diff.txt
chown -R builder:builder /home/builder/rpmbuild
# This phase only prepares official sources; no compile, installation, or publication.
original_nevr="$(rpmspec -q --srpm --qf '%{NAME}|%{VERSION}|%{RELEASE}' /home/builder/rpmbuild/SPECS/official-php.spec)"
patched_nevr="$(rpmspec -q --srpm --qf '%{NAME}|%{VERSION}|%{RELEASE}' /home/builder/rpmbuild/SPECS/php.spec)"
test "$original_nevr" = "php|${pins[2]}|${pins[3]}"
test "$patched_nevr" = "$original_nevr.cve2026_109618_109619.1"
printf 'original=%s\npatched=%s\n' "$original_nevr" "$patched_nevr" | tee /out/parsed-nevr.txt
su - builder -c "rpmbuild -bp --nodeps rpmbuild/SPECS/php.spec"
cp /home/builder/rpmbuild/SPECS/php.spec /out/recipe.spec
rpm -qa | sort > /out/preparation-rpms.txt
echo "OFFICIAL_SECURITY_PATCH_PREPARATION_PASSED series=$series commit=$commit srpm=$srpm"
