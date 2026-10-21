#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
mkdir -p out
python3 scripts/prepare-source.py "$series"
docker buildx build --platform linux/amd64 --load --progress=plain \
 -f "docker/php${series/./}/Dockerfile" -t php-mitigation:test . 2>&1 | tee out/build.log
docker run --rm --network none php-mitigation:test php --version
docker run --rm --network none -v "$PWD/scripts:/tests:ro" php-mitigation:test php -r 'if (!extension_loaded("Zend OPcache") || !extension_loaded("sodium")) exit(1);'
cid="$(docker run -d --memory 256m --cpus 2 --pids-limit 64 -p 127.0.0.1:19000:9000 \
 -v "$PWD/tests:/tests:ro" php-mitigation:test php-fpm -F -y /tests/fpm.conf)"
trap 'docker logs "$cid" > out/runtime.log 2>&1; docker rm -f "$cid" >/dev/null' EXIT
python3 tests/fpm.py 19000 | tee out/fpm-test.json
docker exec "$cid" php --ini > out/php-ini.txt
docker exec "$cid" php -m > out/php-modules.txt
docker exec "$cid" sh -c 'cat /usr/local/share/php-mitigation/source.json' > out/source.json
docker exec "$cid" sh -c 'sha256sum /usr/local/bin/php /usr/local/sbin/php-fpm' > out/binaries.sha256
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
(cd out && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
