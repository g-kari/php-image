# Licensing and upstream notices

Repository-specific build scripts and test harnesses are provided under the MIT license in LICENSE.
They do not relicense PHP, Zend Engine, bundled third-party components, the historical official Docker image, or OS/runtime dependencies.

The complete pinned PHP source archive is included inside each source RPM. Preserve its original LICENSE, Zend/LICENSE, third-party license/copyright notices and the source provenance when redistributing. The PHP name must not be used to claim official PHP Project or AWS support.

The earlier separate-prefix RPM/image recipes include PHP/Zend license texts and a source manifest; their full component-notice payload completeness has not been retroactively audited here. New AWS-layout split RPMs retain the original vendor notice/package layout rather than embedding a manifest and every license in each RPM. Their matching companion upstream-license-notices.tar.gz, LICENSE-NOTICE.md, complete SRPM and external provenance provide version-matched notice/source evidence; keep these together when redistributing. Runtime package inventories identify externally linked OS libraries; their original package copyright/license files and source obligations still apply. A top-level PHP/Zend OCI label is not an exhaustive license statement for every image layer.

Docker inputs: historical Docker Official Images PHP recipes, https://github.com/docker-library/php .
PHP source: https://github.com/php/php-src .
Amazon Linux source-package information: https://docs.aws.amazon.com/linux/al2/ug/amazon-linux-source-packages.html .

For an exact distribution, inspect the source RPM, generated SBOM/inventories, immutable image digest and original package licenses. This project provides no trademark endorsement or extended maintenance promise.
