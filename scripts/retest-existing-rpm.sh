#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
mkdir -p sources
cp out/source.json "sources/php-$series.json"
base="$(python3 -c 'import json;print(json.load(open("sources.lock.json"))["al2"]["base"])')"
docker pull --platform linux/amd64 "$base"
# The original RPM package build ID is 5; no compilation occurs here.
cid="$(docker run -d --memory 1g --cpus 2 --pids-limit 128 -p 127.0.0.1:19000:9000 \
 -v "$PWD/out:/out" -v "$PWD/tests:/tests:ro" -v "$PWD/al2:/recipes:ro" \
 "$base" bash /recipes/runtime-test.sh "$series" 5)"
trap 'if [ -n "${cid:-}" ];then docker logs "$cid" > out/runtime-failure.log 2>&1;docker rm -f "$cid" >/dev/null;fi' EXIT
for _ in $(seq 1 120); do
 if docker logs "$cid" 2>&1 | grep -q 'ready to handle connections';then break;fi
 test "$(docker inspect -f '{{.State.Running}}' "$cid")" = true
 sleep 2
done
python3 tests/fpm.py 19000 enabled "$series" | tee out/fpm-test.json
prefix="$(python3 -c 'import json,sys;m=json.load(open("out/source.json"));print(m["prefix_root"]+"/"+sys.argv[1]+"-"+m["sha"][:8]+"-5")' "$series")"
docker exec "$cid" "$prefix/bin/php" -d opcache.enable_cli=1 /tests/runtime.php al2 | tee out/runtime-functions.json
docker exec "$cid" sh -c 'rpm -qa | sort' > out/runtime-rpms.txt
bash scripts/install-syft.sh
docker commit "$cid" php-al2-runtime:scan >/dev/null
tools/syft docker:php-al2-runtime:scan -o spdx-json=out/sbom.spdx.json
cp sources.lock.json out/sources.lock.json
docker stop -t 10 "$cid" >/dev/null
docker logs "$cid" > out/runtime.log 2>&1
docker rm "$cid" >/dev/null
cid=""
