#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"; phase="${2:?}"
case "$phase" in vendor|patched|rollback) ;; *) exit 2;; esac
dir="/out/qa/$phase"; mkdir -p "$dir"
fpm_pid=""; tls_pid=""
cleanup() {
 if [[ -n "$tls_pid" ]]; then
  kill -TERM "$tls_pid" 2>/dev/null || true
  wait "$tls_pid" 2>/dev/null || true
 fi
 if [[ -n "$fpm_pid" ]]; then
  kill -TERM "$fpm_pid" 2>/dev/null || true
  wait "$fpm_pid" 2>/dev/null || true
 fi
}
last_probe="initialization"; last_output=""
on_exit() {
 local rc=$?
 if [[ "$rc" != 0 ]]; then
  echo "PHASE_FAILURE series=$series phase=$phase stage=$last_probe status=$rc" >&2
  if [[ -n "$last_output" && -f "$last_output" ]]; then tail -c 10000 "$last_output" >&2 || true; fi
  if [[ -f "$dir/fpm.log" ]]; then tail -n 40 "$dir/fpm.log" >&2 || true; fi
  if [[ -f "$dir/tls-local-server.jsonl" ]]; then tail -c 4000 "$dir/tls-local-server.jsonl" >&2 || true; fi
 fi
 cleanup
 exit "$rc"
}
trap on_exit EXIT
check_probe() {
 python3 -c 'import json,sys
p=json.load(open(sys.argv[1]))
if not isinstance(p,dict) or p.get("features",{}).get("local_features")!="passed" or p.get("pecl",{}).get("bounded_local_checks")!="passed":
 raise RuntimeError("SAPI did not return the expected completed feature result")
' "$last_output"
 echo "SAPI_PROBE_PASSED phase=$phase stage=$last_probe"
}
for file in /work/al2-official/*.php; do php -l "$file"; done
php --ini > "$dir/php-ini-paths.txt"
php-config --configure-options > "$dir/configure-options.txt"
rpm -q tzdata glibc openssl-libs libcurl > "$dir/core-dependencies.txt"
pear version > "$dir/pear-version.txt"
pecl version > "$dir/pecl-version.txt"
for binary in php zts-php phpdbg zts-phpdbg; do
 command -v "$binary" >/dev/null
 last_probe="SAPI $binary"; last_output="$dir/$binary.json"
 echo "SAPI_PROBE_BEGIN phase=$phase binary=$binary"
 if [[ "$binary" = *phpdbg ]]; then
  timeout 20 "$binary" -d apc.enable_cli=1 -qrr /work/al2-official/probe-entry.php "$series" > "$dir/$binary.json"
 else
  timeout 20 "$binary" -d apc.enable_cli=1 /work/al2-official/probe-entry.php "$series" > "$dir/$binary.json"
 fi
 check_probe
done
last_probe="SAPI php-cgi"; last_output="$dir/php-cgi-response.bin"
REDIRECT_STATUS=1 REQUEST_METHOD=GET SCRIPT_FILENAME=/work/al2-official/probe-entry.php \
 QUERY_STRING="series=$series" timeout 20 php-cgi > "$dir/php-cgi-response.bin"
python3 /work/al2-official/cgi-response.py "$dir/php-cgi-response.bin" "$dir/php-cgi.json" "$dir/php-cgi-headers.json"
last_output="$dir/php-cgi.json"
check_probe
for config in php-config zts-php-config; do
 last_probe="Header ABI $config"; last_output="$dir/abi-$config.txt"
 binary="${config%-config}"
 # php-config describes php; zts-php-config describes zts-php.
 zts="$("$binary" -r 'echo (int)PHP_ZTS;')"
 read -r -a includes <<< "$("$config" --includes)"
 if [[ "$zts" = 1 ]]; then includes+=(-DZTS); fi
 gcc "${includes[@]}" /work/al2-official/abi-probe.c -o "/tmp/abi-$config"
 "/tmp/abi-$config" > "$dir/abi-$config.txt"
 "$config" --phpapi > "$dir/api-$config.txt"
done
php -r 'echo json_encode(["default_multipart"=>ini_get("max_multipart_body_parts"),"timezone"=>timezone_version_get(),"tehran"=>(new DateTime("1977-10-25 17:17:17",new DateTimeZone("Asia/Tehran")))->format("Y-m-d H:i:s T"),"next_tuesday"=>(new DateTime("1977-10-25 17:17:17",new DateTimeZone("Asia/Tehran")))->modify("next Tuesday")->format("Y-m-d H:i:s T")]);' > "$dir/date-and-defaults.json"
last_probe="CLI OOM"; last_output="$dir/cli-oom.json"
python3 /work/al2-official/cli-oom.py "$series" "$phase"
last_probe="packaged FPM syntax"; last_output="$dir/packaged-fpm-syntax.txt"
php-fpm -t > "$dir/packaged-fpm-syntax.txt" 2>&1
# Private CI-only configuration. Does not replace the packaged service, pool or INI.
php-fpm -d max_multipart_body_parts=3 --nodaemonize --fpm-config /work/al2-official/fpm.conf > "$dir/fpm.log" 2>&1 &
fpm_pid="$!"
last_probe="FPM runtime"; last_output="$dir/fpm.json"
python3 /work/al2-official/fastcgi.py "$series" "$phase" "$dir/fpm.json"
cleanup; fpm_pid=""
if [[ "$phase" != rollback ]]; then
 last_probe="strict public TLS curl-first"; last_output="$dir/tls-public-origin-curl-first.json"
 timeout 65 php /work/al2-official/tls-origin.php curl-first > "$dir/tls-public-origin-curl-first.json"
 last_probe="strict public TLS stream-first"; last_output="$dir/tls-public-origin-stream-first.json"
 timeout 65 php /work/al2-official/tls-origin.php stream-first > "$dir/tls-public-origin-stream-first.json"
 if [[ ! -f /tmp/public-sni-fixture.pem ]]; then
  curl --fail --silent --show-error --proto '=https' --connect-timeout 5 --max-time 20 \
   'https://raw.githubusercontent.com/php/php-src/09a9f29a0402bb87bb448cb2e3149ccbec1699c6/ext/openssl/tests/bug76705.pem' > /tmp/public-sni-fixture.pem
 fi
 printf '%s  %s\n' '440d8620a1a81265474246beab99731a4ec7f5e8c5c0b777de196223ce584e13' /tmp/public-sni-fixture.pem | sha256sum -c -
 # Extract an already-public test certificate only; no key or CA is generated or installed.
 openssl x509 -in /tmp/public-sni-fixture.pem -out /tmp/ci-sni-ca.pem
 rm -f /tmp/ci-sni-ready
 timeout 35 php /work/al2-official/sni-server.php /tmp/public-sni-fixture.pem > "$dir/tls-local-server.jsonl" 2>&1 &
 tls_pid="$!"
 for _ in $(seq 1 50); do test ! -f /tmp/ci-sni-ready || break; sleep 0.1; done
 test -f /tmp/ci-sni-ready
 last_probe="strict local TLS"; last_output="$dir/tls-local-strict.json"
 timeout 25 php /work/al2-official/sni-client.php /tmp/ci-sni-ca.pem > "$dir/tls-local-strict.json"
 wait "$tls_pid"; tls_pid=""
fi
last_probe="embedded and Apache SAPIs"; last_output=""
python3 /work/al2-official/sapi-probes.py "$series" "$phase"
last_probe="native ELF inventory"; last_output=""
python3 /work/al2-official/native-snapshot.py "$series" "$dir/native.json"
rpm -q --qf '%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}\n' $(python3 -c 'import json,sys;print(" ".join(json.load(open("/work/al2-official/packages.json"))["main"][sys.argv[1]]))' "$series") | sort > "$dir/installed-main.txt"
find /usr/lib64/php/modules /usr/lib64/php-zts/modules -maxdepth 1 -type f -name '*.so' -print0 | sort -z | xargs -0 sha256sum > "$dir/modules.sha256"
echo "OFFICIAL_COHORT_PHASE_PASSED series=$series phase=$phase"
