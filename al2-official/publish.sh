#!/usr/bin/env bash
# Trusted-main only; no rebuild, no new keys/permissions, no PR/fork token.
set -euo pipefail
series="${1:?}"; case "$series" in 7.4|8.0|8.1) ;; *) exit 2;; esac
test "${GITHUB_REPOSITORY:?}" = g-kari/php-image
test "${GITHUB_REF:?}" = refs/heads/main
test "${GITHUB_EVENT_NAME:?}" = push
[[ "${GITHUB_SHA:?}" =~ ^[0-9a-f]{40}$ ]]
tag="al2-official-$series-${GITHUB_SHA:0:12}"
python3 - "$series" <<'PY'
import hashlib,json,os,pathlib,sys
root=pathlib.Path("release");p=json.load(open(root/"provenance.json"))
if p["recipe_commit"]!=os.environ["GITHUB_SHA"] or p["series"]!=sys.argv[1]:raise RuntimeError("Wrong recipe/series")
if json.load(open("out/qa/FINAL-RESULT.json"))["status"]!="passed":raise RuntimeError("Runtime gate absent")
if json.load(open("out/qa/PHPT-RESULTS.json"))["status"]!="no_unclassified_failure":raise RuntimeError("PHPT unclassified")
for name,sha in p["rpm_sha256"].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise RuntimeError("Tested RPM bytes changed")
for line in (root/"SHA256SUMS").read_text().splitlines():
    sha,name=line.split("  ",1)
    if pathlib.Path(name).name!=name or hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise RuntimeError("Asset checksum mismatch")
PY
assert_main() {
 test "$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq .object.sha)" = "$GITHUB_SHA" || {
  echo "Main advanced; stop without replacing old or partially published outputs." >&2; exit 1;
 }
}
assert_main
existing="$(gh api "repos/$GITHUB_REPOSITORY/releases?per_page=100" --jq '.[] | select(.tag_name == "'$tag'") | .id')"
test -z "$existing" || { echo "Existing release/draft requires reconciliation, not blind recreate." >&2; exit 1; }
# The displayed target_commitish is not evidence of the actual Git tag target.
# Use a new lightweight tag for this exact tested commit; do not move or overwrite any existing tag.
tag_exists="$(gh api "repos/$GITHUB_REPOSITORY/git/matching-refs/tags/$tag" --jq '.[] | select(.ref == "refs/tags/'$tag'") | .ref')"
test -z "$tag_exists" || { echo "Existing tag requires reconciliation; refusing to move/reuse it." >&2; exit 1; }
assert_main
gh api -X POST "repos/$GITHUB_REPOSITORY/git/refs" -f ref="refs/tags/$tag" -f sha="$GITHUB_SHA" > created-tag.json
assert_tag() {
 gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$tag" > exact-tag.json
 python3 - <<'PY'
import json,os
p=json.load(open("exact-tag.json"))
# This publisher creates only lightweight commit refs. An annotated/replaced/unknown ref stops.
if p["object"]["type"]!="commit" or p["object"]["sha"]!=os.environ["GITHUB_SHA"]:
    raise RuntimeError("Actual tag is not the exact tested commit")
PY
}
assert_tag
gh release create "$tag" release/* --repo "$GITHUB_REPOSITORY" --target "$GITHUB_SHA" \
 --draft --prerelease --title "Unofficial AL2 PHP $series AWS-layout security rebuild (${GITHUB_SHA:0:12})" \
 --notes-file release/RELEASE-NOTES.md
id="$(gh api "repos/$GITHUB_REPOSITORY/releases?per_page=100" --jq '.[] | select(.tag_name == "'$tag'" and .target_commitish == "'$GITHUB_SHA'") | .id')"
[[ "$id" =~ ^[0-9]+$ ]]
gh api "repos/$GITHUB_REPOSITORY/releases/$id" > release-assets.json
python3 - <<'PY'
import hashlib,json,pathlib
root=pathlib.Path("release");expected={p.name:p for p in root.iterdir() if p.is_file()}
actual={p["name"]:p for p in json.load(open("release-assets.json"))["assets"]}
if set(actual)!=set(expected):raise RuntimeError("Incomplete draft assets")
for name,path in expected.items():
    item=actual[name]
    if not path.stat().st_size or item["size"]!=path.stat().st_size or item.get("digest")!="sha256:"+hashlib.sha256(path.read_bytes()).hexdigest():
        raise RuntimeError("Draft asset size/digest mismatch: "+name)
PY
assert_main
assert_tag
gh api -X PATCH "repos/$GITHUB_REPOSITORY/releases/$id" -F draft=false > published-release.json
python3 - <<'PY'
import json,os
p=json.load(open("published-release.json"))
if p["draft"] or p["target_commitish"]!=os.environ["GITHUB_SHA"]:raise RuntimeError("Release not publicly promoted")
print("OFFICIAL_LAYOUT_RELEASE_PUBLISHED "+p["html_url"])
PY
assert_tag
# Public anonymous metadata reachability, separate from authenticated publishing.
url="$(python3 -c 'import json;print(json.load(open("published-release.json"))["url"])')"
curl --fail --silent --show-error --proto '=https' --connect-timeout 5 --max-time 20 "$url" > anonymous-release.json
python3 - <<'PY'
import json
a=json.load(open("anonymous-release.json"));b=json.load(open("published-release.json"))
if a["id"]!=b["id"] or a["draft"] or {x["name"]:x.get("digest") for x in a["assets"]}!={x["name"]:x.get("digest") for x in b["assets"]}:
    raise RuntimeError("Anonymous release metadata mismatch")
print("OFFICIAL_LAYOUT_RELEASE_ANONYMOUSLY_VISIBLE "+a["html_url"])
PY
