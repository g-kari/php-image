#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
mkdir -p out
python3 scripts/prepare-source.py "$series"
base="$(python3 -c 'import json,sys;print(json.load(open("sources.lock.json"))["containers"][sys.argv[1]]["base"])' "$series")"
docker pull --platform linux/amd64 "$base"
docker run --rm --network none "$base" php -m | sort > out/base-php-modules.txt
docker run --rm --network none "$base" php-config --configure-options > out/base-configure-options.txt
archive_sha="$(python3 -c 'import json,sys;print(json.load(open("sources/php-"+sys.argv[1]+".json"))["archive_sha256"])' "$series")"
docker buildx build --platform linux/amd64 --load --progress=plain \
 --build-arg RECIPE_REVISION="${GITHUB_SHA:?}" --build-arg SOURCE_ARCHIVE_SHA256="$archive_sha" \
 -f "docker/php${series/./}/Dockerfile" -t php-mitigation:test . 2>&1 | tee out/build.log
docker run --rm --network none php-mitigation:test php --version
docker run --rm --network none -v "$PWD/scripts:/tests:ro" php-mitigation:test php -r 'if (!extension_loaded("Zend OPcache") || !extension_loaded("sodium")) exit(1);'
cid="$(docker run -d --memory 256m --cpus 2 --pids-limit 64 -p 127.0.0.1:19000:9000 \
 -v "$PWD/tests:/tests:ro" php-mitigation:test php-fpm -F -y /tests/fpm.conf)"
trap 'if [ -n "${cid:-}" ]; then docker logs "$cid" > out/runtime-failure.log 2>&1; docker rm -f "$cid" >/dev/null; fi' EXIT
python3 tests/fpm.py 19000 | tee out/fpm-test.json
docker exec "$cid" php -d opcache.enable_cli=1 /tests/runtime.php docker | tee out/runtime-functions.json
docker exec "$cid" pear version > out/pear-version.txt
docker exec "$cid" pecl version > out/pecl-version.txt
docker exec "$cid" php --ini > out/php-ini.txt
docker exec "$cid" php -m | sort > out/php-modules.txt
if [[ "$series" = 7.4 || "$series" = 8.0 ]]; then
 # Explicit documented delta: these old official images shipped OPcache disabled.
 sed '/^Zend OPcache$/d' out/base-php-modules.txt > out/base-module-compare.txt
 sed '/^Zend OPcache$/d' out/php-modules.txt > out/fixed-module-compare.txt
 diff -u out/base-module-compare.txt out/fixed-module-compare.txt
else
 diff -u out/base-php-modules.txt out/php-modules.txt
fi
docker exec "$cid" sh -c 'cat /usr/local/share/php-mitigation/source.json' > out/source.json
docker exec "$cid" sh -c 'sha256sum /usr/local/bin/php /usr/local/sbin/php-fpm' > out/binaries.sha256
bash scripts/install-syft.sh
tools/syft docker:php-mitigation:test -o spdx-json=out/sbom.spdx.json
docker image inspect php-mitigation:test > out/image-inspect.json
docker history --no-trunc php-mitigation:test > out/image-history.txt
docker logs "$cid" > out/runtime.log 2>&1
cp sources.lock.json out/
python3 - "$series" <<'PY'
import json,os,pathlib,sys
pathlib.Path("out/provenance.json").write_text(json.dumps({"series":sys.argv[1],"platform":"linux/amd64",
"recipe_commit":os.environ["GITHUB_SHA"],"source":json.load(open("out/source.json")),
"run":os.environ["GITHUB_SERVER_URL"]+"/"+os.environ["GITHUB_REPOSITORY"]+"/actions/runs/"+os.environ["GITHUB_RUN_ID"],
"tests":["CLI functional","CLI OOM exit without shutdown callback","FPM OPcache + session worker reuse","multipart upload","OOM worker replacement"],
"limits":["not full upstream test suite","not application compatibility proof","not renewed upstream or base-OS support"]},indent=2)+"\n")
PY
docker stop -t 10 "$cid" >/dev/null
docker logs "$cid" > out/runtime.log 2>&1
docker rm "$cid" >/dev/null
cid=""
(cd out && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
