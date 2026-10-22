%global debug_package %{nil}
%global prefix /opt/php-al2-full/%{series}-%{source_short}-%{recipe_short}-%{build_id}
Name: %{package_name}
Version: %{source_version}
Release: 1.full.%{build_id}%{?dist}
Summary: Independent PHP build with AL2 main-source runtime feature coverage
License: PHP and Zend and BSD and MIT and ASL 1.0
URL: https://github.com/g-kari/php-image
Source0: php-%{series}.tar
Source1: php-%{series}.json
Source2: test-cli.py
BuildRequires: gcc gcc-c++ make autoconf bison re2c pkgconfig python3
BuildRequires: libxml2-devel libcurl-devel zlib-devel sqlite-devel
BuildRequires: bzip2-devel libedit-devel libjpeg-turbo-devel libpng-devel freetype-devel libwebp-devel
BuildRequires: gmp-devel libdb-devel tokyocabinet-devel aspell-devel libicu-devel enchant-devel libsodium-devel
BuildRequires: libxslt-devel oniguruma-devel libzip-devel cyrus-sasl-devel openldap-devel postgresql-devel unixODBC-devel net-snmp-devel
BuildRequires: libacl-devel systemd-devel
%if "%{series}" == "8.2"
BuildRequires: openssl11-devel
%else
BuildRequires: openssl-devel
%endif
Requires: ca-certificates
AutoReqProv: yes

%description
This independent-prefix full-feature variant does not replace AWS PHP,
system libraries, handlers, configuration or sockets. No service is activated.
CLI/CGI/phpdbg and FPM/embedded are built separately so PCNTL and libedit
are not enabled in the persistent FPM engine. Consult the recorded source
and feature manifests; this is not an AWS ABI or full application guarantee.

%prep
%setup -q -n %{source_dir}

%build
test -x configure || ./buildconf --force
cp -a . ../php-cli-tree
export CFLAGS="%{optflags} -fstack-protector-strong -fPIC"
export LDFLAGS="-Wl,-z,relro -Wl,-z,now"
if [ "%{series}" = 8.2 ]; then
 pcfile="$(rpm -ql openssl11-devel | grep '/openssl11.pc$')"
 test "$(printf '%s\n' "$pcfile" | wc -l)" -eq 1
 case "$pcfile" in /*/openssl11.pc) ;; *) exit 1;; esac
 test -f "$pcfile"
 pcdir="$(dirname "$pcfile")"
 private_pc="$PWD/.openssl11-pc"
 mkdir -p "$private_pc"
 for module in openssl libssl libcrypto; do
  test -f "$pcdir/${module}11.pc"
  ln -s "$pcdir/${module}11.pc" "$private_pc/$module.pc"
 done
 export PKG_CONFIG_PATH="$private_pc${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
 pkg-config --atleast-version=1.1.1 openssl
 test "$(pkg-config --modversion openssl)" = "$(pkg-config --modversion openssl11)"
fi
configure_common() {
 ./configure --prefix=%{prefix} --libdir=%{prefix}/lib64 --with-libdir=lib64 \
  --with-config-file-path=/etc/%{name} --with-config-file-scan-dir=/etc/%{name}/conf.d \
  --enable-option-checking=fatal --without-pear --with-openssl --with-system-ciphers --with-mhash \
  --with-curl --with-zlib --with-bz2 --enable-calendar --enable-exif --enable-ftp --with-gettext \
  --enable-opcache --enable-mysqlnd --with-mysqli=mysqlnd --with-pdo-mysql=mysqlnd \
  --with-mysql-sock=/var/lib/mysql/mysql.sock --with-pdo-sqlite --with-sqlite3 \
  --enable-sockets --enable-bcmath --enable-mbstring=shared --enable-mbregex \
  --enable-gd=shared --with-jpeg --with-freetype --with-webp --with-gmp=shared \
  --enable-dba=shared --with-db4=/usr --with-tcadb=/usr \
  --with-ldap=shared --with-ldap-sasl --with-pgsql=shared \
  --with-unixODBC=shared,/usr --with-pdo-odbc=shared,unixODBC,/usr --with-pdo-pgsql=shared,/usr \
  --with-snmp=shared,/usr --enable-soap=shared --with-xsl=shared --with-zip=shared \
  --with-pspell=shared --enable-intl=shared --with-enchant=shared --with-sodium=shared \
  --enable-shmop=shared --enable-sysvmsg=shared --enable-sysvshm=shared --enable-sysvsem=shared \
  "$@"
}
extra=""
if [ "%{series}" = 7.4 ]; then extra="--with-xmlrpc=shared"; fi
configure_common --enable-fpm --with-fpm-user=nobody --with-fpm-group=nobody \
 --with-fpm-acl --with-fpm-systemd --enable-embed=shared --disable-cgi \
 $extra > configure-web.log 2>&1 || { tail -150 configure-web.log; exit 1; }
make %{?_smp_mflags}
cp config.nice config-web.nice
cd ../php-cli-tree
configure_common --disable-fpm --disable-embed --enable-cgi --enable-pcntl --with-libedit \
 $extra > configure-cli.log 2>&1 || { tail -150 configure-cli.log; exit 1; }
make %{?_smp_mflags}
cp config.nice config-cli.nice

%check
python3 %{SOURCE2} sapi/cli/php %{series}
python3 %{SOURCE2} ../php-cli-tree/sapi/cli/php %{series}

%install
make install INSTALL_ROOT=%{buildroot}
install -m 0755 ../php-cli-tree/sapi/cli/php %{buildroot}%{prefix}/bin/php
install -m 0755 ../php-cli-tree/sapi/phpdbg/phpdbg %{buildroot}%{prefix}/bin/phpdbg
install -m 0755 ../php-cli-tree/sapi/cgi/php-cgi %{buildroot}%{prefix}/bin/php-cgi
mkdir -p %{buildroot}/etc/%{name}/conf.d %{buildroot}/var/lib/%{name}/sessions
chmod 1733 %{buildroot}/var/lib/%{name}/sessions
cp php.ini-production %{buildroot}/etc/%{name}/php.ini
for module in $(find %{buildroot}%{prefix}/lib64/php/extensions -type f -name '*.so' -printf '%%f\n' | sort); do
 if [ "$module" = opcache.so ]; then
  printf 'zend_extension=%%s\n' "$module" > %{buildroot}/etc/%{name}/conf.d/10-opcache.ini
 else
  printf 'extension=%%s\n' "$module" > "%{buildroot}/etc/%{name}/conf.d/20-${module%.so}.ini"
 fi
done
printf 'session.save_path=/var/lib/%{name}/sessions\n' > %{buildroot}/etc/%{name}/conf.d/30-session.ini
cat > %{buildroot}/etc/%{name}/php-fpm.conf <<'EOF'
[global]
pid=/run/%{name}/php-fpm.pid
error_log=/var/log/%{name}.log
daemonize=no
[www]
user=nobody
group=nobody
listen=/run/%{name}/php-fpm.sock
listen.mode=0600
pm=dynamic
pm.max_children=5
pm.start_servers=1
pm.min_spare_servers=1
pm.max_spare_servers=2
clear_env=yes
EOF
mkdir -p %{buildroot}/usr/lib/systemd/system
cat > %{buildroot}/usr/lib/systemd/system/%{name}.service <<'EOF'
[Unit]
Description=Independent AL2 full-feature PHP %{series}
After=network.target
[Service]
Type=simple
ExecStart=%{prefix}/sbin/php-fpm --nodaemonize --fpm-config /etc/%{name}/php-fpm.conf
ExecReload=/bin/kill -USR2 $MAINPID
RuntimeDirectory=%{name}
PrivateTmp=true
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOF
mkdir -p %{buildroot}%{prefix}/share/provenance
cp %{SOURCE1} %{buildroot}%{prefix}/share/provenance/source.json
cp config-web.nice ../php-cli-tree/config-cli.nice %{buildroot}%{prefix}/share/provenance/
%{buildroot}%{prefix}/bin/php -n -r 'echo json_encode(["version"=>PHP_VERSION,"api_int_size"=>PHP_INT_SIZE,"zts"=>PHP_ZTS,"static_modules"=>get_loaded_extensions()],JSON_PRETTY_PRINT),PHP_EOL;' > %{buildroot}%{prefix}/share/provenance/static-build-info.json
mkdir -p %{buildroot}%{_docdir}/%{name}
cp LICENSE %{buildroot}%{_docdir}/%{name}/LICENSE.PHP
cp Zend/LICENSE %{buildroot}%{_docdir}/%{name}/LICENSE.Zend

%files
%{prefix}
%config(noreplace) /etc/%{name}
%dir /var/lib/%{name}
%dir %attr(1733,root,root) /var/lib/%{name}/sessions
/usr/lib/systemd/system/%{name}.service
%{_docdir}/%{name}
