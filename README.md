# Legacy PHP mitigation builds

Amazon Linux 2 PHP 7.4 / 8.0 / 8.1 self-build RPMs and patched PHP-FPM container images.

**Build implementation and independent review are in progress. No binary or container is currently claimed as tested or published.**

This project packages the PHP project's **minimal EOL mitigations** for CVE-2026-109618 and CVE-2026-109619. It does not restore upstream support, fix every known vulnerability, or make Amazon Linux 2 or old Debian releases supported. Upgrade to maintained PHP and OS versions as soon as possible.

## Scope

- Fixed complete upstream source trees, not a partial patch selection.
- AL2 packages use a separate prefix and package names. They do **not** replace AWS PHP RPMs, system libraries, handlers, PATH, services, configuration or sockets.
- RPM/SRPM and FPM container results are tracked separately for each version and CPU.
- Initial CPU target is x86_64 / linux/amd64 only.
- No production service starts automatically.
- No new signing keys, personal access tokens, self-hosted runners or paid infrastructure.
- Old official images are only compatibility inputs, not patched images.
- Applications relying on session upload-progress callbacks or OOM shutdown handlers must be retested. These behaviors deliberately change.

## Pinned upstream sources

See [sources.lock.json](sources.lock.json). PHP 7.4: `712e60f9edfd03f0960fc4fc3c2c375f42b90aa2`; PHP 8.0: `82f8f31b16a035c1b67cc253e79f7cc288f4cc20`; PHP 8.1: `1d7dec178a094e6e75b229ce22754045f8c6070a`.

[Official announcement](https://www.php.net/archive/2026.php), [PHP source licensing](https://github.com/php/php-src/blob/1d7dec178a094e6e75b229ce22754045f8c6070a/LICENSE).

**A version string or a successful compile alone does not prove mitigation.** Source SHA, generated source archive checksum, recipe commit, binary/package/image digest, and recorded runtime tests must be read together.

## Distribution and safety boundaries

The two deliverables are separate:
1. Amazon Linux 2 native x86_64 RPM/SRPM packages.
2. Non-AL2 Docker images derived from the historical official `php:7.4-fpm`, `php:8.0-fpm`, and `php:8.1-fpm` images, each pinned by digest. PHP 7.4 and 8.0 use their Bullseye-era inputs; 8.1 uses its Trixie-era input. These are not Amazon Linux images.

Build shell scripts under `al2/` are disposable-container recipes. **Never execute them directly on a production host.** The CI wrapper installs build tools only in a disposable container, compiles as an unprivileged builder, stages installation with INSTALL_ROOT, then installs/tests the RPM in a different fresh AL2 container. No host Docker socket is mounted inside the build container.

CI is limited to standard public GitHub-hosted runners. Test runs do not publish a binary. Release publication will use only the repository-scoped, job-lifetime GITHUB_TOKEN, not a PAT or new signing key.

### Native package compatibility

These packages are deliberately not binary-compatible replacements for every AWS PHP package or PECL extension. Their minimal native configuration includes CLI, FPM, OPcache, curl/OpenSSL, sockets, bcmath, SQLite, mysqlnd/mysqli/PDO MySQL. Existing extensions, `php.ini`, application handlers, cron/queue commands and web-server sockets require an explicit application-specific migration. Do not copy old `.so` modules blindly.

Each RPM installs under `/opt/php-mitigation/SERIES-SOURCE8-BUILD_ID`, with independent `/etc/php74-mitigation`, `/etc/php80-mitigation`, or `/etc/php81-mitigation` configuration. It does not enable or start FPM. Default socket access is intentionally restricted; choose the application user/group before service activation.

Updating the same RPM package name may remove the previous prefix. A build-ID path is provenance, **not a guarantee that an old RPM stays installed alongside the new one**.

### Installation, update, rollback

1. Download a version-specific Release's binary RPM, SRPM, rendered spec, SHA256SUMS, provenance and test records.
2. Verify SHA256SUMS against the trusted repository/Release commit and inspect the package contents/dependencies before installation. Checksums provide integrity, not a cryptographic publisher signature.
3. These initial independent RPMs are unsigned. Do not weaken `gpgcheck`, import an unverified key or enable an unsigned yum repository. Sites requiring signed packages should review and rebuild/sign the SRPM using their existing approved process.
4. On an isolated clone of the application host, install the reviewed local RPM using the site's normal package policy, inspect the absolute binary path and configuration, and run application/session/upload/TLS/DB/queue/OPcache tests.
5. Test FPM with its own service, master process and socket, then deliberately switch the web-server handler and cron/queue commands. A second pool in the old master is not a new PHP engine.
6. Before an update, save the current RPM, configuration and handler settings, plus an application/data rollback plan. Review `.rpmnew` files after upgrade. No service is auto-restarted by the package.
7. Rollback requires reinstalling the saved prior RPM and restoring matching configuration/handler/extension paths, followed by controlled master/worker/queue restart. The old binary may be vulnerable; rollback is an incident decision, not a safe default.

A signed versioned yum repository is deferred until an existing approved signing identity is supplied. GitHub Releases is the initial distribution route; no Cloudflare account or billing changes are necessary.

### Verification limits

The bounded gates cover compilation, CLI data handling, deliberate OOM exit without a shutdown callback, install-time dependency resolution, FPM config, OPcache loading, session requests in the same worker, ordinary multipart upload, and replacement of an OOM-killed worker.

They do not prove exploit resistance, execute the full upstream suite, test every extension/application, or directly prove that upload-progress callbacks are absent at runtime. Complete fixed-tree provenance is recorded separately. No ARM/multi-architecture claim is made.

Bullseye security packages moved to the official Debian archive after Debian 11 LTS ended on 2026-08-31. The 7.4/8.0 recipes use that official archive without disabling signature verification or date validation. This is frozen historical dependency availability, not continuing security support. See [Debian notice](https://www.debian.org/News/2026/20260831).

SBOM generation uses upstream Anchore Syft 1.55.0, verified against the pinned official release-asset SHA256. Build provenance JSON is descriptive evidence, not a new cryptographic signing identity or a security certification.

### Docker usage boundaries

Do not publish FastCGI port 9000 directly to the Internet. EXPOSE is documentation, not a request to publish that port. Use an isolated private container network or a Unix socket and an appropriately restricted web-server frontend. CI binds its test port only to 127.0.0.1.

The patched source is a Git tree, not a newly signed official PHP release tarball. The final image clears inherited PHP_URL, PHP_ASC_URL and PHP_SHA256 release-download values. PHPMITIGATION_SOURCE_SHA and PHPMITIGATION_SOURCE_ARCHIVE_SHA256 identify the rebuilt tree/archive; OCI revision identifies this repository's recipe commit. PHP_VERSION is aligned with the generated binary's source version, but is not proof of mitigation.

PEAR installation is not re-run from the network during rebuilding. Inherited PEAR/PECL tools from the pinned official base are not promoted as newly rebuilt components. Rebuild and compatibility-test additional extensions against the fixed source and the exact resulting image; do not mount an old extension directory or OPcache file cache.

The AL2 FPM smoke test does not start systemd inside a container. It validates the packaged FPM configuration syntax, then runs a dedicated test-only TCP configuration. Systemd unit activation, the packaged Unix socket, real-host RuntimeDirectory behavior and an application's actual handler remain deployment-site tests.

Additional bounded runtime checks exercise OpenSSL digest/randomness, curl version lookup, in-memory PDO SQLite and actual OPcache compile/cache lookup. Docker additionally tests mbstring/sodium and inherited PEAR/PECL version commands; AL2 additionally tests bcmath/mysqli availability. These are local functional checks, not a live DB/TLS integration test.
