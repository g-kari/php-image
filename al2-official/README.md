# Official AL2 SRPM security-backport rebuild

This supersedes the unshipped independent-prefix full-feature experiment in PR2. Existing seven published minimal artifacts remain immutable and are not this official-layout variant.

The goal is to retain the exact per-series Amazon Linux 2 PHP source RPM, existing vendor patches, package names/splits, install paths, configuration, SAPIs, NTS/ZTS, extension selection, dependencies and service definitions. The intended spec differences are one complete official upstream two-CVE patch plus identifiable local Release metadata. No production or user computer installation is performed.

Source versions stay at the pinned AWS baseline (7.4.33, 8.0.30, 8.1.34, 8.2.34). The latter receives the normal 8.2 upstream security commit as a backport, not a false 8.2.35 version claim. Legacy sources receive the official EOL minimal mitigation and retain its OOM/implied feature tradeoffs.

The first stage only verifies the original SRPM SHA256/signature, records its spec, obtains the pinned official PHP commit and complete parent-to-commit patch, and applies it with zero fuzz after the existing vendor patches. A preparation pass is not a binary/runtime/compatibility success.

Our resulting RPMs will not be Amazon-signed official packages. Local Release/provenance, unsigned signatures, compiler/dependency snapshot, timestamps, build IDs, checksums and resulting bytes can differ even if functional changes are restricted to the security patch. Exact bit-for-bit reproduction is not promised. Before distribution, compare full package metadata/files/configuration, provided API/ABI, native linking and real NTS/ZTS/SAPI/module behavior against the acquired official RPMs, including unchanged genuine PECL packages where available. System libraries and global security settings are not replaced or weakened.
