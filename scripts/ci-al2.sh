#!/usr/bin/env bash
set -euo pipefail
series="${1:?}"
base="$(python3 -c 'import json; print(json.load(open("sources.lock.json"))["al2"]["base"])')"
mkdir -p out
python3 scripts/prepare-source.py "$series"
docker pull --platform linux/amd64 "$base"
docker image inspect "$base" > out/al2-image-inspect.json
docker run --rm --platform linux/amd64 --memory 6g --cpus 2 --pids-limit 512 \
 -e CI_DISPOSABLE_BUILD=1 -e BUILD_ID="${GITHUB_RUN_NUMBER:?}" -v "$PWD:/work:ro" -v "$PWD/out:/out" \
 "$base" bash /work/al2/build.sh "$series" 2>&1 | tee out/build.log
cid="$(docker run -d --platform linux/amd64 --memory 1g --cpus 2 --pids-limit 128 \
 -p 127.0.0.1:19000:9000 -v "$PWD/out:/out" -v "$PWD/tests:/tests:ro" \
 -v "$PWD/al2:/recipes:ro" "$base" bash /recipes/runtime-test.sh "$series" "$GITHUB_RUN_NUMBER")"
trap 'docker logs "$cid" > out/runtime.log 2>&1; docker rm -f "$cid" >/dev/null' EXIT
# Initial yum installation can take longer than FPM readiness. Wait without hiding failure.
for _ in $(seq 1 120); do
 if docker logs "$cid" 2>&1 | grep -q 'ready to handle connections'; then break; fi
 test "$(docker inspect -f '{{.State.Running}}' "$cid")" = true
 sleep 2
done
python3 tests/fpm.py 19000 | tee out/fpm-test.json
docker exec "$cid" sh -c 'rpm -qa | sort' > out/runtime-rpms.txt
cp "sources/php-$series.json" out/source.json
cp sources.lock.json out/
cp al2/php-mitigation.spec out/recipe.spec
python3 - "$series" <<'PY'
import json,os,pathlib,sys
out=pathlib.Path("out")
(out/"provenance.json").write_text(json.dumps({"series":sys.argv[1],"architecture":"x86_64",
"recipe_commit":os.environ["GITHUB_SHA"],"run":os.environ["GITHUB_SERVER_URL"]+"/"+os.environ["GITHUB_REPOSITORY"]+"/actions/runs/"+os.environ["GITHUB_RUN_ID"],
"source":json.load(open(out/"source.json")),"tests":["CLI functional","CLI OOM exit without shutdown callback","RPM dependency installation","glibc unchanged","FPM config","FPM OPcache + session worker reuse","multipart upload","OOM worker replacement"],"limits":["not full upstream test suite","not application compatibility proof","unsigned RPM","no renewed upstream or OS support"]},indent=2)+"\n")
PY
docker logs "$cid" > out/runtime.log 2>&1
(cd out && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
