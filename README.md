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
