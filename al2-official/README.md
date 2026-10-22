# AWS-layout AL2 PHP security rebuild

This replaces the unshipped custom full-feature experiment. Existing seven separate-prefix/FPM releases remain immutable and are a different artifact family.

## Scope
Only x86_64 PHP 7.4.33 / 8.0.30 / 8.1.34 are rebuilt from exact signed AWS source RPMs. All vendor patches, configure flags, SAPIs, extension selection, 28/26/26 normal binary splits, names, paths, config, scriptlets and services are retained. The spec changes add the complete official two-CVE commit after vendor patches and append .cve2026_109618_109619.1 to Release. The full source RPM and original/modified specs accompany publication.

For 8.2 use [AWS official 8.2.35-1.amzn2.0.1](https://alas.aws.amazon.com/AL2/ALAS2PHP8.2-2026-015.html), which explicitly addresses both CVEs. The obsolete 8.2.34 custom-backport candidate is not published.

These are unofficial, unsigned rebuilds, not Amazon-signed packages. Release/build IDs, compiler/dependency snapshots, timestamps and native bytes differ; bit-for-bit equivalence and all-application/private-extension ABI compatibility are not promised. Named zts binaries are tested by actual PHP_ZTS, not assumed thread-safe: the original 8.x vendor flag may yield non-ZTS behavior.

## Test gates, without concealing failures
The AWS spec's original %check is retained: build-apache CLI, make test, NO_INTERACTION=1 REPORT_EXIT_STATUS=1 MALLOC_CHECK_=2, SKIP_ONLINE_TESTS=1 SKIP_IO_CAPTURE_TESTS=1, unset TZ/LANG/LC_ALL. The vendor spec comments out exit1 after test failure. Thus a successful rpmbuild is not a full-suite pass.

The full original PHPT log, PASS/FAIL/SKIP/XFAIL/WARN/BORK statistics, paired source fixtures and diff files are retained. A separate fail-closed policy requires exact reviewed known diffs (only controlled source-root/version and six-character upload tempfile normalization, plus one validated ephemeral loopback port in each of two exact historical PHP8.1 SNI diagnostic lines). Unknown changes, crashes or timeout differences stop publication. Original FAILs stay FAIL. Historical expired SNI fixtures get separate strict TLS positive/negative/positive checks; Tehran is compared with an unchanged installed vendor binary and unchanged tzdata. This is not a blanket skip list.

Because the vendor suite uses a without-shared engine and many SKIPs, additional bounded checks use the actual installed full RPM cohort: normal/named-ZTS CLI/phpdbg, CGI, FPM, private prefork Apache DSOs and embedded library; 47/49 core extension feature coverage and genuine vendor PECL runtime/devel packages; serialization/cache, DB/LDAP client registration (not live remote servers), real image/ZIP/DBA/PDO-SQLite operations, TLS, upload/session/progress/OOM recovery. CLI OOM exit code and FPM worker exit1 are distinguished from signals/crashes. Public TLS client operations run in both orders, not a claimed reversed MINIT/loader initialization.

Metadata, paths/modes/owners/config bytes/scriptlets/dependencies/License, header/API layouts and ELF exports/version providers are compared with exact AWS binaries. All main subpackages update together in a fresh AL2 container with locally modified config fixtures; preserved configs and system libraries are checked, then saved original RPMs are restored and compared. The tests do not activate a real systemd host unit or production handler, prove all private ABIs, or cover every application/FIPS/proxy/server integration.

## Tradeoffs and deployment boundary
The official EOL minimal patch exits the executing OOM process with code1 without normal shutdown callbacks and disables builtin session upload-progress even when INI enables it; ordinary upload remains. 7.4 adds the total multipart-part limit (8.0/8.1 already had it). API numbers remaining equal do not prove OPcache private-internal compatibility; update the matching cohort and replace all old workers using your reviewed deployment plan. Do not delete OPcache caches blindly.

Unlike the old separate-prefix RPMs, these packages can replace system PHP and affect existing handlers/services. No real server or user computer is installed/modified by CI. Do not install all optional packages merely because the complete split is available. Rollback to saved vulnerable originals is a test/contingency, not a secure steady state.

## Publication and licensing
Only a normal reviewed main merge enables the trusted-main job. PR jobs are read-only. The main job rebuilds, runs every gate, and publishes those exact tested bytes via a draft Release after full asset hash/size verification and current-main checks. No new keys, credentials, yum signing repository, paid storage or permanent permissions are introduced. See [LICENSE-NOTICE.md](../LICENSE-NOTICE.md), the complete source RPM and matching upstream-license-notices.tar.gz; MIT covers only original repository scripts.

Unverified or failed targets are never promoted. Existing minimal releases are not overwritten.

## Exact 8.1 PHPT classification
The original 8.1 suite has fifteen observed FAILs: three OOM shutdown/output-buffer callback differences, eight upload-progress callback differences, two expired historical SNI fixtures, one transition-count expectation and one historical RSA OAEP error-code expectation. All remain FAIL. Every accepted 8.1 fixture is bound to reviewed upstream bytes and a complete normalized diff, not a keyword. Only the two specific historical SNI diagnostics may normalize their validated ephemeral loopback port.

The two date/OpenSSL environment explanations also require rerunning those unchanged official PHPTs with the exact original signed vendor PHP binary in the same runtime container before update. Both must retain FAIL and reproduce the exact patched-build diff. This is a narrow control, not an assertion that the complete vendor suite or all environment compatibility passes.

Additional actual timeout/signal markers exposed in a PHPT diff block even if upstream labels the test XFAIL. Expected/deleted/context lines are not rewritten. This detects only those exposed markers, not every possible crash hidden by a broad upstream EXPECTF/REGEX. Original suite statistics remain unchanged.


## Build-environment parity corrections (verification pending)
The additional build-only SDK inputs are explicit differences beyond the security patch/Release edit. Signed AWS libcurl-devel7.79.1 headers for7.4, libcurl-devel7.88.1 headers for8.0, and PostgreSQL9.2.24-6 headers for7.4 reproduce the original registered SDK API values. They are extracted into a private build include directory, not installed as old system packages. Current runtime libcurl/libpq/OpenSSL/glibc stay installed. Exact SDK RPMs, helper and hash/identity lock are part of each affected complete SRPM. Original configure flags/link flags and package/service paths remain unchanged. Real Makefile compiler-header traces and the final registered functions/classes/constants comparison must pass before publication. The PG_VERSION_STR compiler description belongs to the selected PostgreSQL SDK, not necessarily the PHP compiler.

The exact APCu5.1.18 NUL-prefixed serializer hook constant is a process-local function address. Raw values remain in every phase record. Only that one value is compared as the same signed ELF hash/symbol/file-offset, requiring integer type, same-fd file identity and same-process executable mapping identity. No ordinary constant or missing/changed module is ignored.

Only /var/cache/ldconfig/aux-cache is recorded separately as glibc's generated inode/ctime/size/dev lookup cache. Its raw bytes/hash/stat/owner/strict format and semantic SONAME/flags/OS-version multiset remain evidence and must validate. This is not the loader cache: /etc/ld.so.cache, loader/libc/OpenSSL and all other owned system files still require byte equality. Unknown file, API, library or cache-semantic differences block publication.
