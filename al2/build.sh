#!/usr/bin/env bash
set -euo pipefail
series="${1:?series}"
case "$series" in
  7.4) sha=712e60f9edfd03f0960fc4fc3c2c375f42b90aa2; version=7.4.34; package=php74-mitigation;;
  8.0) sha=82f8f31b16a035c1b67cc253e79f7cc288f4cc20; version=8.0.30; package=php80-mitigation;;
  8.1) sha=1d7dec178a094e6e75b229ce22754045f8c6070a; version=8.1.34; package=php81-mitigation;;
  *) exit 2;;
esac
test "$(uname -m)" = x86_64
grep -q 'Amazon Linux 2' /etc/system-release
yum install -y gcc gcc-c++ make autoconf bison re2c pkgconfig rpm-build \
 openssl-devel libxml2-devel libcurl-devel zlib-devel sqlite-devel python3
useradd -m builder
mkdir -p /home/builder/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} /out
cp "/work/sources/php-$series.tar" "/work/sources/php-$series.json" /home/builder/rpmbuild/SOURCES/
cp /work/scripts/test-cli.py /home/builder/rpmbuild/SOURCES/
cp /work/al2/php-mitigation.spec /home/builder/rpmbuild/SPECS/
chown -R builder:builder /home/builder/rpmbuild
su - builder -c "rpmbuild -ba --define 'series $series' --define 'source_sha $sha' --define 'source_version $version' --define 'package_name $package' --define 'build_id ${BUILD_ID:?}' --define '_smp_mflags -j2' rpmbuild/SPECS/php-mitigation.spec"
cp /home/builder/rpmbuild/RPMS/x86_64/*.rpm /home/builder/rpmbuild/SRPMS/*.rpm /out/
cp /home/builder/rpmbuild/SPECS/php-mitigation.spec "/out/$package.spec"
rpm -qa | sort > "/out/$package-build-rpms.txt"
cp /etc/system-release "/out/$package-system-release.txt"
cp "/work/sources/php-$series.json" "/out/$package-source.json"
