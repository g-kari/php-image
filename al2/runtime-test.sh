#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"; build_id="${2:?}"
case "$series" in
  7.4) sha=712e60f9; pkg=php74-mitigation;;
  8.0) sha=82f8f31b; pkg=php80-mitigation;;
  8.1) sha=1d7dec17; pkg=php81-mitigation;;
  8.2) sha=09a9f29a; pkg=php82-security;;
  *) exit 2;;
esac
before="$(rpm -q glibc)"
yum localinstall -y /out/"$pkg"-*.x86_64.rpm
test "$(rpm -q glibc)" = "$before"
prefix_root=/opt/php-mitigation
if [[ "$series" = 8.2 ]]; then prefix_root=/opt/php-security; fi
prefix="$prefix_root/$series-$sha-$build_id"
"$prefix/bin/php" --version
"$prefix/bin/php" --ini
"$prefix/bin/php" -m
"$prefix/sbin/php-fpm" -t -y "/etc/$pkg/php-fpm.conf"
"$prefix/bin/php" -r 'if (!extension_loaded("Zend OPcache") || !extension_loaded("curl") || !extension_loaded("openssl")) exit(1);'
ldd "$prefix/bin/php"; ldd "$prefix/sbin/php-fpm"
rpm -V "$pkg" > /out/rpm-verify.txt
sha256sum "$prefix/bin/php" "$prefix/sbin/php-fpm" > /out/binaries.sha256
cp "$prefix/share/mitigation/source.json" /out/runtime-source.json
exec "$prefix/sbin/php-fpm" -F -y /tests/fpm-al2.conf
