# Legacy PHP mitigation builds

Amazon Linux 2 PHP 7.4 / 8.1 self-build packages and a patched PHP 8.1 FPM container.

Implementation and verification are in progress. No binary or container is currently claimed as tested or published.

This project packages the official PHP project's minimal EOL mitigations for CVE-2026-109618 and CVE-2026-109619. It does not restore upstream support, fix every known vulnerability, or make Amazon Linux 2 a supported operating system.

Pinned upstream mitigation commits:
- PHP 7.4: https://github.com/php/php-src/commit/712e60f9edfd03f0960fc4fc3c2c375f42b90aa2
- PHP 8.1: https://github.com/php/php-src/commit/1d7dec178a094e6e75b229ce22754045f8c6070a

Existing system PHP installations must not be overwritten without an application-specific migration and rollback plan.
