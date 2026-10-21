#!/usr/bin/env bash
set -euo pipefail
series="${1:?series}"
test "${CI_DISPOSABLE_BUILD:-}" = 1 && test -f /.dockerenv || {
 echo "Refusing direct host execution. Use scripts/ci-al2.sh with a disposable Docker container." >&2; exit 2;
}
[[ "${BUILD_ID:-}" =~ ^[0-9]{1,12}$ ]] || { echo "Invalid BUILD_ID" >&2; exit 2; }
case "$series" in
  7.4) sha=712e60f9edfd03f0960fc4fc3c2c375f42b90aa2; version=7.4.34; package=php74-mitigation;;
  8.0) sha=82f8f31b16a035c1b67cc253e79f7cc288f4cc20; version=8.0.30; package=php80-mitigation;;
  8.1) sha=1d7dec178a094e6e75b229ce22754045f8c6070a; version=8.1.34; package=php81-mitigation;;
  8.2) sha=09a9f29a0402bb87bb448cb2e3149ccbec1699c6; version=8.2.35; package=php82-security;;
  *) exit 2;;
esac
prefix_root=/opt/php-mitigation; source_dir=php-src; release_kind=0.mitigation
support_note="Official minimal EOL mitigations for CVE-2026-109618 and CVE-2026-109619; not renewed support."
if [[ "$series" = 8.2 ]]; then
 prefix_root=/opt/php-security; source_dir=php-8.2.35; release_kind=1.security
 support_note="Official signed PHP 8.2.35 security release; independently built for EOL Amazon Linux 2."
fi
test "$(uname -m)" = x86_64
. /etc/os-release
test "$ID" = amzn && test "$VERSION_ID" = 2
openssl_devel=openssl-devel
if [[ "$series" = 8.2 ]]; then openssl_devel=openssl11-devel; fi
yum install -y gcc gcc-c++ make autoconf bison re2c pkgconfig rpm-build \
 "$openssl_devel" libxml2-devel libcurl-devel zlib-devel sqlite-devel python3
python3 - "$series" "$sha" <<'PY'
import hashlib,json,sys
if not __debug__: raise RuntimeError("Optimized Python verification is forbidden")
m=json.load(open("/work/sources/php-"+sys.argv[1]+".json"))
assert m["sha"]==sys.argv[2]
assert hashlib.sha256(open("/work/sources/php-"+sys.argv[1]+".tar","rb").read()).hexdigest()==m["archive_sha256"]
PY
if [[ "$series" = 8.2 ]]; then
 pkg-config --atleast-version=1.1.1 openssl11
 { pkg-config --modversion openssl11; pkg-config --cflags openssl11; pkg-config --libs openssl11; rpm -ql openssl11-devel; } > /out/php82-openssl11-build-provider.txt
fi
useradd -m builder
mkdir -p /home/builder/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} /out
cp "/work/sources/php-$series.tar" "/work/sources/php-$series.json" /home/builder/rpmbuild/SOURCES/
cp /work/scripts/test-cli.py /home/builder/rpmbuild/SOURCES/
{
 printf '%%global series %s\n%%global source_sha %s\n%%global source_version %s\n%%global package_name %s\n%%global build_id %s\n' "$series" "$sha" "$version" "$package" "$BUILD_ID"
 printf '%%global prefix_root %s\n%%global source_dir %s\n%%global release_kind %s\n%%global support_note %s\n' "$prefix_root" "$source_dir" "$release_kind" "$support_note"
 cat /work/al2/php-mitigation.spec
} > /home/builder/rpmbuild/SPECS/php-mitigation.spec
chown -R builder:builder /home/builder/rpmbuild
su - builder -c "rpmbuild -ba --define '_smp_mflags -j2' rpmbuild/SPECS/php-mitigation.spec"
cp /home/builder/rpmbuild/RPMS/x86_64/*.rpm /home/builder/rpmbuild/SRPMS/*.rpm /out/
cp /home/builder/rpmbuild/SPECS/php-mitigation.spec "/out/$package.spec"
if [[ "$series" = 8.2 ]]; then cp /home/builder/rpmbuild/BUILD/php-8.2.35/php82-effective-openssl-provider.txt /out/; fi
rpm -qa | sort > "/out/$package-build-rpms.txt"
cp /etc/system-release "/out/$package-system-release.txt"
cp "/work/sources/php-$series.json" "/out/$package-source.json"
if [[ "$series" = 8.2 ]]; then
 cp /work/sources/php-8.2.tar.xz /work/sources/php-8.2.tar.xz.asc /out/
fi
