# License, copyright and redistribution notices

## Scope and acknowledgements
The original build scripts and test harnesses written for this repository use the existing MIT license in LICENSE (copyright 2026 g-kari). MIT does not replace or modify the licenses of PHP, Zend Engine, bundled code, vendor packaging, PECL modules, Docker inputs or OS libraries. The pinned sources use PHP License 3.01 and Zend Engine License 2.00. Original texts, per-file grants, copyright notices, naming/endorsement restrictions and disclaimers remain applicable.

This product includes PHP software, freely available from <http://www.php.net/software/>.
This product includes the Zend Engine, freely available at http://www.zend.com
The Zend Engine is freely available at http://www.zend.com
This product includes software developed by the Apache Group for use in the Apache HTTP server project (http://www.apache.org/).
This product includes software developed by the University of California, Berkeley and its contributors.

These credits do not imply endorsement, Amazon signatures, renewed maintenance or a legal warranty.

The embedded verbatim PHP 8.0 hrtime PHPT fixture in al2-official/test-runtime-policies.py remains PHP License 3.01 material, not original MIT harness code. Exact upstream PHP 3.01 and Zend Engine 2.00 terms are retained under third-party-licenses/ for reference alongside this notice.

## Exact old-series AWS spec metadata
The inspected original 7.4/8.0/8.1 AWS specs declare the following legacy License strings; the rebuilt RPMs preserve them rather than assigning a new license.

| Package group | Original vendor License field |
|---|---|
| php, cli, dbg, fpm, devel, embedded | PHP and Zend and BSD and MIT and ASL 1.0 |
| common | PHP and BSD |
| mbstring | PHP and LGPLv2 and OpenLDAP |
| bundled-GD Amazon Linux gd | PHP and BSD |
| bcmath | PHP and LGPLv2+ |
| xmlrpc (7.4 only) | PHP and BSD |
| opcache, ldap, pdo, mysqlnd, pgsql, process, odbc, soap, snmp, xml, gmp, dba, pspell, intl, enchant, sodium; json (7.4 only) | PHP |

Names in the table omit the common php- prefix except the main php package. Subpackages without their own License inherit the main field. Disabled imap/interbase/tidy/pdo-dblib spec branches are not distributed features. This matrix is not the metadata of PHP 8.2, PECL or the earlier independent-prefix packages.

## Accompanying notices and source
For each newly verified official-layout distribution, download and retain the matching upstream-license-notices.tar.gz and LICENSE-NOTICE.md together with the binary RPMs and complete source RPM. The bundle preserves version-matched source-relative legal files, their hashes and actual RPM License/file inventories. It includes PHP, Zend, TSRM, FPM, README.REDIST.BINS, libbcmath, libmbfl, libmagic and timelib texts, plus other legal files found in the prepared source. The complete source RPM carries the original vendor source archives/patches, exact modified spec and full upstream security patch. Recipe/provenance and SHA256SUMS identify the bytes. Do not detach required notices when redistributing an individual RPM.

README.REDIST.BINS contains many BSD/Apache/GD/OpenLDAP/PCRE2/SLJIT/Phar-related notices; 7.4 additionally includes XMLRPC and 8.1 includes xxHash. It refers out to separate library license texts, so it is not a substitute for those files. The libbcmath/libmbfl LICENSE files contain LGPL 2.1 text while per-file grants include version-2-or-later and version-2/2.1 terms. Preserve those original grants and the corresponding materials needed to modify and rebuild covered components; do not relabel them uniformly.

External dependencies retain their own RPM notices and corresponding-source routes. SBOM, package/ELF inventories and preserved License strings are evidence, not an exhaustive legal assessment. The new QA compares actual required packaged notice hashes with the prepared source and retains supplemental notices absent from the original binary split, without silently changing the vendor payload.

## Artifact-family status
- New AWS-layout old-series RPMs: license/source/payload gates and companion notice bundle are required before publication. A prepared recipe alone is not a passed binary audit.
- Earlier independent-prefix AL2 RPMs and official-base Docker FPM images: their original recipes include PHP/Zend texts and source manifests, but this new complete vendor-layout license-payload audit has not been retroactively established for those releases. Consult their exact source RPM/image digest and upstream/component notices; do not read the repository MIT license as covering all layers.
- AWS official 8.2.35: prefer the AWS-signed packages and original AWS source/notice distribution. No custom 8.2.34 backport is being published.

## Primary sources
- [PHP 3.01](https://github.com/php/php-src/blob/712e60f9edfd03f0960fc4fc3c2c375f42b90aa2/LICENSE), [Zend 2.00](https://github.com/php/php-src/blob/712e60f9edfd03f0960fc4fc3c2c375f42b90aa2/Zend/LICENSE)
- [7.4 bundled notices](https://github.com/php/php-src/blob/712e60f9edfd03f0960fc4fc3c2c375f42b90aa2/README.REDIST.BINS), [8.0](https://github.com/php/php-src/blob/82f8f31b16a035c1b67cc253e79f7cc288f4cc20/README.REDIST.BINS), [8.1](https://github.com/php/php-src/blob/1d7dec178a094e6e75b229ce22754045f8c6070a/README.REDIST.BINS)
- [AWS source packages](https://docs.aws.amazon.com/linux/al2/ug/amazon-linux-source-packages.html)
