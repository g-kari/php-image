#!/usr/bin/env bash
# Called only after the same job's build/runtime gates succeed, from trusted main.
set -euo pipefail
target="${1:?}"; series="${2:?}"
[[ "$target" = al2 || "$target" = fpm ]]
[[ "$series" = 7.4 || "$series" = 8.0 || "$series" = 8.1 || ( "$series" = 8.2 && "$target" = al2 ) ]]
[[ "${GITHUB_REPOSITORY:?}" = g-kari/php-image ]]
[[ "${GITHUB_SHA:?}" =~ ^[0-9a-f]{40}$ ]]
short="${GITHUB_SHA:0:12}"
release_tag="$target-$series-$short"
kind="minimal EOL mitigation"
if [[ "$series" = 8.2 ]]; then kind="official 8.2.35 security release"; fi
test -s out/fpm-test.json
test -s out/provenance.json
test -s out/sbom.spdx.json
python3 - <<'PY'
import json,os
if not __debug__: raise RuntimeError("Optimized Python verification forbidden")
p=json.load(open("out/provenance.json"))
if p["recipe_commit"] != os.environ["GITHUB_SHA"]: raise RuntimeError("Wrong recipe commit")
if not json.load(open("out/fpm-test.json"))["oom_recovery_passed"]: raise RuntimeError("Missing OOM recovery gate")
PY
if gh release view "$release_tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
 echo "Release already exists; refusing to overwrite or assume an incomplete upload succeeded." >&2
 exit 1
fi
# Scan evidence before any registry or Release publication.
scan_evidence() {
 if grep -IRnE --exclude='*.rpm' --exclude='*.gz' --exclude='SHA256SUMS' \
  '(-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})' out; then
  echo "Potential secret in publication evidence; refusing publication." >&2; exit 1
 fi
}
scan_evidence
assert_current_head() {
 local current
 current="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq .object.sha)"
 test "$current" = "$GITHUB_SHA" || {
  echo "Commit superseded before publication. Stop without overwriting or hiding prior outcomes." >&2
  exit 1
 }
}
assert_current_head
if [[ "$target" = fpm ]]; then
 image="ghcr.io/$GITHUB_REPOSITORY:$series-fpm-cve2026-$short"
 docker tag php-mitigation:test "$image"
 tested_id="$(docker image inspect -f '{{.Id}}' "$image")"
 # Temporary job-lifetime authentication, not a new persistent credential.
 export DOCKER_CONFIG
 DOCKER_CONFIG="$(mktemp -d)"
 trap 'docker logout ghcr.io >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"' EXIT
 printf '%s' "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
 # No mutable/latest tag. An uncertain push failure must be reconciled, not blindly retried.
 assert_current_head
 docker push "$image" | tee out/registry-push.txt
 digest_ref="$(docker image inspect -f '{{index .RepoDigests 0}}' "$image")"
 [[ "$digest_ref" =~ ^ghcr.io/g-kari/php-image@sha256:[0-9a-f]{64}$ ]]
 docker pull "$digest_ref"
 test "$(docker image inspect -f '{{.Id}}' "$digest_ref")" = "$tested_id"
 printf '%s\n' "$image" "$digest_ref" > out/IMAGE.txt
 docker save "$image" | gzip -n > "out/php-$series-fpm-docker-load.tar.gz"
 docker logout ghcr.io >/dev/null
 rm -rf "$DOCKER_CONFIG"
 trap - EXIT
 gzip -n -c "sources/php-$series.tar" > "out/php-$series-fixed-source.tar.gz"
fi
# No secret is provided to build containers or included in their layers. Scan text evidence as well.
if grep -IRnE --exclude='*.rpm' --exclude='*.gz' --exclude='SHA256SUMS' \
 '(-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})' out; then
 echo "Potential secret in publication evidence; refusing publication." >&2; exit 1
fi
cp NOTICE.md out/NOTICE.md
cat > out/RELEASE-NOTES.md <<EOF
# $target PHP $series $kind ($short)

Only this series/CPU build and bounded runtime checks passed for this artifact.
Recipe commit: $GITHUB_SHA
Run: $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID

The official PHP source commit is recorded in source.json and provenance.json.
PHP 7.4/8.0/8.1: minimal EOL mitigation for CVE-2026-109618/109619, not renewed support.
AL2 PHP 8.2: official signed PHP 8.2.35 security release, independently built for an EOL OS.
No build restores Amazon Linux 2 or old Debian security maintenance.
It is not a full test-suite pass or an application compatibility guarantee.
AL2 packages are unsigned, separate-prefix packages, not AWS replacements.
AL2 systemd unit/packaged Unix-socket activation remains untested here.
PHP 7.4/8.0 FPM retain historical Debian 11 inputs; Debian 11 LTS ended 2026-08-31.
No repository signature checks or expiry checks were disabled.

For FPM, IMAGE.txt identifies the pushed registry digest and the docker-load tar is the exact tested image.
GHCR public visibility/anonymous pull is a separate check; do not infer it from an authenticated push.
See README and NOTICE at this recipe commit before installation or redistribution.
EOF
(cd out && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
# Draft first. Public release only after every asset upload is present.
assert_current_head
gh release create "$release_tag" out/* --repo "$GITHUB_REPOSITORY" \
 --target "$GITHUB_SHA" --draft --prerelease --title "$target PHP $series $kind ($short)" \
 --notes-file out/RELEASE-NOTES.md
gh api "repos/$GITHUB_REPOSITORY/releases/tags/$release_tag" > release-assets.json
python3 - <<'PY'
import hashlib,json,pathlib
if not __debug__: raise RuntimeError("Optimized Python verification forbidden")
expected={p.name:p for p in pathlib.Path("out").iterdir() if p.is_file()}
actual={p["name"]:p for p in json.load(open("release-assets.json"))["assets"]}
if set(actual) != set(expected): raise RuntimeError("Incomplete release assets")
for name,path in expected.items():
    item=actual[name]
    if item["size"] != path.stat().st_size: raise RuntimeError("Asset size mismatch: "+name)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if item.get("digest") != "sha256:"+sha: raise RuntimeError("Asset digest missing/mismatch: "+name)
PY
assert_current_head
gh release edit "$release_tag" --repo "$GITHUB_REPOSITORY" --draft=false
echo "Published verified $target PHP $series Release: $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/releases/tag/$release_tag"
