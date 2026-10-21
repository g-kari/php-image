# Rebuild ALL PHP binaries and bundled shared extensions from the fixed upstream tree.
# The old official php:8.1-fpm is provenance/compatibility input, NOT evidence of a fix.
FROM docker.io/library/php:8.1-fpm@sha256:a3118db1911fdd3b3ac66605122ddc859286688ced86fc860fec6d19cc2d6c55 AS build
USER root
COPY sources/php-8.1.tar /work/php.tar
COPY sources/php-8.1.json /work/source.json
COPY scripts/test-cli.py /work/test-cli.py
RUN set -eux; \
    apt-get update; apt-get upgrade -y; \
    apt-get install -y --no-install-recommends bison python3 libargon2-dev libcurl4-openssl-dev libonig-dev libreadline-dev libsodium-dev libsqlite3-dev libssl-dev libxml2-dev zlib1g-dev; \
    python3 -c 'import hashlib,json; m=json.load(open("/work/source.json")); assert m["sha"]=="1d7dec178a094e6e75b229ce22754045f8c6070a"; assert hashlib.sha256(open("/work/php.tar","rb").read()).hexdigest()==m["archive_sha256"]'; \
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
    sha256sum /stage/usr/local/bin/php /stage/usr/local/sbin/php-fpm > /stage/usr/local/share/php-mitigation/binaries.sha256

FROM docker.io/library/php:8.1-fpm@sha256:a3118db1911fdd3b3ac66605122ddc859286688ced86fc860fec6d19cc2d6c55
LABEL org.opencontainers.image.source="https://github.com/g-kari/php-image" \
      org.opencontainers.image.description="PHP 8.1 FPM with upstream minimal EOL mitigations for CVE-2026-109618 and CVE-2026-109619; not renewed support" \
      org.opencontainers.image.licenses="PHP-3.01 AND Zend-2.0"
# APT updates here and in build use the same Debian suite. All runtime changes are inventoried.
RUN set -eux; apt-get update; apt-get upgrade -y; rm -rf /var/lib/apt/lists/*
COPY --from=build /stage/usr/local/ /usr/local/
# Original source tar was vulnerable; replace it so docker-php-ext-install cannot use it.
COPY sources/php-8.1.tar /usr/src/php-mitigation.tar
RUN set -eux; \
    rm -f /usr/src/php.tar.xz; \
    xz -c /usr/src/php-mitigation.tar > /usr/src/php.tar.xz; \
    rm /usr/src/php-mitigation.tar; \
    rm -rf /usr/src/php; \
    dpkg-query -W > /usr/local/share/php-mitigation/runtime-dpkg.txt; \
    php --version; php-fpm -t; \
    php -r 'if (!extension_loaded("Zend OPcache") || !extension_loaded("sodium")) exit(1);'
STOPSIGNAL SIGQUIT
EXPOSE 9000
CMD ["php-fpm"]
