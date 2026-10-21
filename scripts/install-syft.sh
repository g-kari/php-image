#!/usr/bin/env bash
set -euo pipefail
# Official upstream release and GitHub release-asset digest, pinned at review time.
mkdir -p tools
curl --fail --location --retry 3 --retry-delay 3 \
 https://github.com/anchore/syft/releases/download/v1.55.0/syft_1.55.0_linux_amd64.tar.gz \
 -o tools/syft.tar.gz
echo 'bb65249542db5fedeeb4d3f9b018b75e7264dbfbbb10486f044581a92f90490d  tools/syft.tar.gz' | sha256sum --check -
tar -xzf tools/syft.tar.gz -C tools syft
tools/syft version
