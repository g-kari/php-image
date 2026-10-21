%global debug_package %{nil}
%global shortsha %(echo %{source_sha} | cut -c1-8)
%global prefix /opt/php-mitigation/%{series}-%{shortsha}-%{build_id}
Name: %{package_name}
Version: %{source_version}
Release: 0.mitigation.%{build_id}%{?dist}
Summary: Independently packaged EOL PHP with narrowly scoped upstream mitigations
License: PHP and Zend and BSD
URL: https://github.com/g-kari/php-image
Source0: php-%{series}.tar
Source1: php-%{series}.json
Source2: test-cli.py
BuildRequires: gcc gcc-c++ make autoconf bison re2c pkgconfig python3
BuildRequires: openssl-devel libxml2-devel libcurl-devel zlib-devel sqlite-devel
Requires: ca-certificates
AutoReqProv: yes

%description
Full fixed upstream tree for CVE-2026-109618 and CVE-2026-109619.
This is an independent prefix, not an AWS RPM replacement or renewed support.
No production service is enabled or started by package installation.

%prep
%setup -q -n php-src

%build
./buildconf --force
export CFLAGS="%{optflags} -fstack-protector-strong -fPIC"
export LDFLAGS="-Wl,-z,relro -Wl,-z,now"
./configure --prefix=%{prefix} \
 --with-config-file-path=/etc/%{name} \
 --with-config-file-scan-dir=/etc/%{name}/conf.d \
 --enable-option-checking=fatal --enable-fpm \
 --with-fpm-user=nobody --with-fpm-group=nobody \
 --enable-opcache --enable-mysqlnd --with-mysqli=mysqlnd --with-pdo-mysql=mysqlnd \
 --with-openssl --with-curl --with-zlib --with-pdo-sqlite --with-sqlite3 \
 --enable-sockets --enable-bcmath --disable-cgi --without-pear
make %{?_smp_mflags}

%check
python3 %{SOURCE2} sapi/cli/php

%install
make install INSTALL_ROOT=%{buildroot}
mkdir -p %{buildroot}/etc/%{name}/conf.d %{buildroot}/var/lib/%{name}/sessions
chmod 1733 %{buildroot}/var/lib/%{name}/sessions
cp php.ini-production %{buildroot}/etc/%{name}/php.ini
cat > %{buildroot}/etc/%{name}/conf.d/10-opcache.ini <<'EOF'
zend_extension=opcache.so
EOF
cat > %{buildroot}/etc/%{name}/conf.d/20-session.ini <<'EOF'
session.save_path=/var/lib/%{name}/sessions
; Upstream EOL mitigation disables upload-progress callbacks in source.
EOF
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
Description=Independent EOL PHP %{series} FPM mitigation build
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
mkdir -p %{buildroot}%{prefix}/share/mitigation
cp %{SOURCE1} %{buildroot}%{prefix}/share/mitigation/source.json
sapi/cli/php -n -r 'echo json_encode(["version"=>PHP_VERSION,"version_id"=>PHP_VERSION_ID,"int_size"=>PHP_INT_SIZE,"zts"=>PHP_ZTS,"debug"=>PHP_DEBUG,"os"=>PHP_OS,"extensions"=>get_loaded_extensions()], JSON_PRETTY_PRINT), PHP_EOL;' > %{buildroot}%{prefix}/share/mitigation/php-build-info.txt
cp config.nice %{buildroot}%{prefix}/share/mitigation/
sha256sum %{buildroot}%{prefix}/bin/php %{buildroot}%{prefix}/sbin/php-fpm | sed 's|%{buildroot}||g' > %{buildroot}%{prefix}/share/mitigation/binaries.sha256
mkdir -p %{buildroot}%{_docdir}/%{name}
# Preserve both licenses without a name collision.
cp Zend/LICENSE %{buildroot}%{_docdir}/%{name}/LICENSE.Zend
cp LICENSE %{buildroot}%{_docdir}/%{name}/LICENSE.PHP

%files
%{prefix}
%config(noreplace) /etc/%{name}
%dir /var/lib/%{name}
%dir %attr(1733,root,root) /var/lib/%{name}/sessions
/usr/lib/systemd/system/%{name}.service
%{_docdir}/%{name}
