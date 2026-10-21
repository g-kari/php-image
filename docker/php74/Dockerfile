# Rebuild ALL PHP binaries and bundled shared extensions from the fixed upstream tree.
# The old official php:7.4-fpm is provenance/compatibility input, NOT evidence of a fix.
FROM docker.io/library/php:7.4-fpm@sha256:3ac7c8c74b2b047c7cb273469d74fc0d59b857aa44043e6ea6a0084372811d5b AS build
USER root
COPY sources/php-7.4.tar /work/php.tar
COPY sources/php-7.4.json /work/source.json
COPY scripts/test-cli.py /work/test-cli.py
RUN set -eux; \
    sed -i 's|http://deb.debian.org/debian-security|https://archive.debian.org/debian-security|g; s|http://security.debian.org/debian-security|https://archive.debian.org/debian-security|g' /etc/apt/sources.list; \
    apt-get update; apt-get upgrade -y; \
    apt-get install -y --no-install-recommends bison python3 libargon2-dev libcurl4-openssl-dev libonig-dev libreadline-dev libsodium-dev libsqlite3-dev libssl-dev libxml2-dev zlib1g-dev; \
    python3 -I -c 'import hashlib,json; m=json.load(open("/work/source.json")); assert m["sha"]=="712e60f9edfd03f0960fc4fc3c2c375f42b90aa2"; assert hashlib.sha256(open("/work/php.tar","rb").read()).hexdigest()==m["archive_sha256"]'; \
    mkdir -p /work/src /stage; tar -xf /work/php.tar -C /work/src --strip-components=1; \
    cd /work/src; ./buildconf --force; \
    export CFLAGS="$PHP_CFLAGS" CPPFLAGS="$PHP_CPPFLAGS" LDFLAGS="$PHP_LDFLAGS"; \
    ./configure --prefix=/usr/local --with-config-file-path="$PHP_INI_DIR" --with-config-file-scan-dir="$PHP_INI_DIR/conf.d" \
      --enable-option-checking=fatal --with-mhash --with-pic --enable-ftp --enable-mbstring --enable-mysqlnd \
      --with-password-argon2 --with-sodium=shared --with-pdo-sqlite=/usr --with-sqlite3=/usr \
      --with-curl --with-iconv --with-openssl --with-readline --with-zlib --disable-phpdbg --without-pear \
      --with-libdir="lib/$(dpkg-architecture --query DEB_BUILD_MULTIARCH)" --disable-cgi --enable-fpm \
      --with-fpm-user=www-data --with-fpm-group=www-data; \
    make -j2; python3 /work/test-cli.py sapi/cli/php; \
    make install INSTALL_ROOT=/stage; \
    mkdir -p /stage/usr/local/share/php-mitigation; \
    cp /work/source.json config.nice /stage/usr/local/share/php-mitigation/; \
    sapi/cli/php -n -r 'echo json_encode(["version"=>PHP_VERSION,"version_id"=>PHP_VERSION_ID,"int_size"=>PHP_INT_SIZE,"zts"=>PHP_ZTS,"debug"=>PHP_DEBUG,"os"=>PHP_OS,"extensions"=>get_loaded_extensions()], JSON_PRETTY_PRINT), PHP_EOL;' > /stage/usr/local/share/php-mitigation/php-build-info.txt; \
    cp LICENSE /stage/usr/local/share/php-mitigation/LICENSE.PHP; \
    cp Zend/LICENSE /stage/usr/local/share/php-mitigation/LICENSE.Zend; \
    dpkg-query -W > /stage/usr/local/share/php-mitigation/build-dpkg.txt; \
    cp /etc/os-release /stage/usr/local/share/php-mitigation/base-os-release; \
    find /stage/usr/local -type f -name '*.a' -delete; \
    cd /stage; find usr/local/bin/php usr/local/sbin/php-fpm usr/local/lib/php/extensions -type f -print0 | sort -z | xargs -0 sha256sum > usr/local/share/php-mitigation/binaries.sha256

FROM docker.io/library/php:7.4-fpm@sha256:3ac7c8c74b2b047c7cb273469d74fc0d59b857aa44043e6ea6a0084372811d5b
ARG RECIPE_REVISION
ARG SOURCE_ARCHIVE_SHA256
ENV PHP_VERSION="7.4.34-dev" PHP_URL="" PHP_ASC_URL="" PHP_SHA256="" \
    PHPMITIGATION_SOURCE_SHA="712e60f9edfd03f0960fc4fc3c2c375f42b90aa2" \
    PHPMITIGATION_SOURCE_ARCHIVE_SHA256="$SOURCE_ARCHIVE_SHA256"
LABEL org.opencontainers.image.revision="$RECIPE_REVISION" \
      io.php-mitigation.source-sha="712e60f9edfd03f0960fc4fc3c2c375f42b90aa2" \
      io.php-mitigation.source-archive-sha256="$SOURCE_ARCHIVE_SHA256"
LABEL org.opencontainers.image.source="https://github.com/g-kari/php-image" \
      org.opencontainers.image.description="PHP 7.4 FPM with upstream minimal EOL mitigations for CVE-2026-109618 and CVE-2026-109619; not renewed support" \
      org.opencontainers.image.licenses="PHP-3.01 AND Zend-2.0"
# APT updates here and in build use the same Debian suite. All runtime changes are inventoried.
RUN set -eux; sed -i 's|http://deb.debian.org/debian-security|https://archive.debian.org/debian-security|g; s|http://security.debian.org/debian-security|https://archive.debian.org/debian-security|g' /etc/apt/sources.list; \
    apt-get update; apt-get upgrade -y; rm -rf /var/lib/apt/lists/*
COPY --from=build /stage/usr/local/ /usr/local/
# Original source tar was vulnerable; replace it so docker-php-ext-install cannot use it.
COPY sources/php-7.4.tar /usr/src/php-mitigation.tar
# Historical 7.4 official images did not enable OPcache by default.
# Enable the rebuilt module explicitly; this is a documented deliberate config delta.
RUN docker-php-ext-enable opcache
RUN set -eux; \
    rm -f /usr/src/php.tar.xz; \
    xz -c /usr/src/php-mitigation.tar > /usr/src/php.tar.xz; \
    rm /usr/src/php-mitigation.tar; \
    rm -rf /usr/src/php; \
    dpkg-query -W > /usr/local/share/php-mitigation/runtime-dpkg.txt; \
    test -n "$PHPMITIGATION_SOURCE_ARCHIVE_SHA256"; \
    test "$(xz -dc /usr/src/php.tar.xz | sha256sum | cut -d' ' -f1)" = "$PHPMITIGATION_SOURCE_ARCHIVE_SHA256"; \
    php -r 'if (PHP_VERSION !== getenv("PHP_VERSION")) exit(1);'; \
    cd /; sha256sum -c /usr/local/share/php-mitigation/binaries.sha256; \
    php --version; php-fpm -t; \
    php -r 'if (!extension_loaded("Zend OPcache") || !extension_loaded("sodium")) exit(1);'
STOPSIGNAL SIGQUIT
EXPOSE 9000
CMD ["php-fpm"]
