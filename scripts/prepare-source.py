#!/usr/bin/env python3
"""Fetch exactly the committed upstream tree. No credentials or moving branch builds."""
import hashlib, json, pathlib, subprocess, sys
series = sys.argv[1]
lock = json.loads(pathlib.Path("sources.lock.json").read_text())
item = lock["versions"][series]
sha = item["sha"]
out = pathlib.Path("sources")
out.mkdir(exist_ok=True)
repo = out / ("git-" + series)
subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["git", "-C", str(repo), "fetch", "--depth=1", lock["upstream"], sha], check=True)
actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "FETCH_HEAD"], text=True).strip()
assert actual == sha, (actual, sha)
tree = subprocess.check_output(["git", "-C", str(repo), "rev-parse", sha + "^{tree}"], text=True).strip()
tar = out / ("php-" + series + ".tar")
with tar.open("wb") as f:
    subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", "--prefix=php-src/", sha], stdout=f, check=True)
digest = hashlib.sha256(tar.read_bytes()).hexdigest()
manifest = dict(item, series=series, tree=tree, archive_sha256=digest, upstream=lock["upstream"])
(out / ("php-" + series + ".json")).write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
