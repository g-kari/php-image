#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
bash /work/al2-official/prepare.sh "$series"
# Standard RPM build-system tool; the minimal AL2 container does not include make.
yum install -y make
yum-builddep -y /home/builder/rpmbuild/SPECS/php.spec
# Reparse after vendor build macros/headers/dependencies are installed.
rpmspec -q --srpm --qf '%{NAME}|%{VERSION}|%{RELEASE}\n' /home/builder/rpmbuild/SPECS/php.spec | tee /out/parsed-build-nevr.txt
grep -Eq '^php\|[0-9.]+\|[^|]+\.cve2026_109618_109619\.1$' /out/parsed-build-nevr.txt
# Original vendor spec and its self-test policy remain unchanged. The log/result inventory is retained.
# Independent fail-closed runtime/regression gates are required before any eventual publication.
su - builder -c "rpmbuild -ba --define '_smp_mflags -j2' rpmbuild/SPECS/php.spec"
mapfile -t binaries < <(find /home/builder/rpmbuild/RPMS -type f -name '*.rpm' | sort)
mapfile -t sources < <(find /home/builder/rpmbuild/SRPMS -type f -name '*.src.rpm' | sort)
test "${#binaries[@]}" -ge 26
test "${#sources[@]}" -eq 1
mkdir -p /out/rpms
cp "${binaries[@]}" /out/rpms/
cp "${sources[@]}" /out/
rpm -qp --qf '%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}\n' "${binaries[@]}" | sort > /out/built-package-metadata.txt
while IFS= read -r rpmfile; do
 echo "BUILT_PACKAGE_FILES_BEGIN $(basename "$rpmfile")"
 rpm -qpl "$rpmfile"
 echo "BUILT_PACKAGE_FILES_END $(basename "$rpmfile")"
done < <(printf '%s\n' "${binaries[@]}") > /out/built-package-files.txt
rpm -qa | sort > /out/build-rpms.txt
cp /home/builder/rpmbuild/SPECS/php.spec /out/recipe.spec
find /home/builder/rpmbuild/BUILD -type f \( -name 'config.nice' -o -name 'config.log' -o -name 'php_test_results_*.txt' -o -name '*.diff' \) -print > /out/build-evidence-paths.txt
mkdir -p /out/build-evidence
# Include actual SDK/header/compiler inputs, not merely their paths.
cp /work/al2-official/build-sdk-lock.json /out/build-sdk-lock.json
cd /home/builder/rpmbuild/BUILD
while IFS= read -r -d '' file; do
 cp --parents "$file" /out/build-evidence/
done < <(find . -type f \( -name 'config.nice' -o -name 'config.log' -o -name 'php_config.h' -o -name 'php_test_results_*.txt' -o -name '*.diff' -o -name 'sdk-headers.txt' -o -name 'sdk-macros.txt' -o -name 'sdk-probe-result.json' -o -name 'sdk-extension-compile-rules.txt' -o -name 'sdk-actual-unit-probes.json' -o -name 'sdk-unit-*-headers.txt' -o -name 'sdk-unit-*-macros.txt' -o -path '*/.build-header-sdk/manifest.json' \) -print0)
echo BUILT_PACKAGE_METADATA_BEGIN
cat /out/built-package-metadata.txt
echo BUILT_PACKAGE_METADATA_END
echo "OFFICIAL_SECURITY_RPM_BUILD_PASSED series=$series packages=${#binaries[@]}"
