#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
test "${CI_DISPOSABLE_BUILD:-}" = 1 && test -f /.dockerenv
[[ "${BUILD_ID:-}" =~ ^[0-9]{1,12}$ ]]
[[ "${RECIPE_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
case "$series" in 7.4|8.0|8.1|8.2) ;; *) exit 2;; esac
. /etc/os-release
test "$ID" = amzn && test "$VERSION_ID" = 2 && test "$(uname -m)" = x86_64
openssl_devel=openssl-devel
if [[ "$series" = 8.2 ]]; then openssl_devel=openssl11-devel; fi
yum install -y gcc gcc-c++ make autoconf bison re2c pkgconfig python3 rpm-build \
 libxml2-devel libcurl-devel zlib-devel sqlite-devel bzip2-devel libedit-devel \
 libjpeg-turbo-devel libpng-devel freetype-devel libwebp-devel gmp-devel libdb-devel tokyocabinet-devel \
 aspell-devel libicu-devel enchant-devel libsodium-devel libxslt-devel oniguruma-devel libzip-devel \
 cyrus-sasl-devel openldap-devel postgresql-devel unixODBC-devel net-snmp-devel libacl-devel systemd-devel "$openssl_devel"
python3 - "$series" <<'PY' > /tmp/build-macros
import hashlib,json,sys
if not __debug__: raise RuntimeError("Optimized verification forbidden")
s=sys.argv[1];m=json.load(open("/work/sources/php-"+s+".json"))
expected={"7.4":"712e60f9edfd03f0960fc4fc3c2c375f42b90aa2","8.0":"82f8f31b16a035c1b67cc253e79f7cc288f4cc20","8.1":"1d7dec178a094e6e75b229ce22754045f8c6070a","8.2":"09a9f29a0402bb87bb448cb2e3149ccbec1699c6"}
if m["sha"]!=expected[s]: raise RuntimeError("Source mismatch")
if hashlib.sha256(open("/work/sources/php-"+s+".tar","rb").read()).hexdigest()!=m["archive_sha256"]: raise RuntimeError("Archive mismatch")
version={"7.4":"7.4.34","8.0":"8.0.30","8.1":"8.1.34","8.2":"8.2.35"}[s]
print("%global series "+s+"\n%global source_version "+version+"\n%global source_short "+m["sha"][:8]+"\n%global source_dir "+m.get("source_dir","php-src")+"\n%global package_name php"+s.replace(".","")+"-al2-full")
PY
useradd -m builder
mkdir -p /home/builder/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cp "/work/sources/php-$series.tar" "/work/sources/php-$series.json" /home/builder/rpmbuild/SOURCES/
cp /work/scripts/test-cli.py /home/builder/rpmbuild/SOURCES/
{ cat /tmp/build-macros; printf '%%global build_id %s\n%%global recipe_short %s\n' "$BUILD_ID" "${RECIPE_SHA:0:12}"; cat /work/al2-parity/php-full.spec; } > /home/builder/rpmbuild/SPECS/php-full.spec
chown -R builder:builder /home/builder/rpmbuild
su - builder -c "rpmbuild -ba --define '_smp_mflags -j2' rpmbuild/SPECS/php-full.spec"
cp /home/builder/rpmbuild/RPMS/x86_64/*.rpm /home/builder/rpmbuild/SRPMS/*.rpm /out/
cp /home/builder/rpmbuild/SPECS/php-full.spec /out/
rpm -qa | sort > /out/build-rpms.txt
