#!/usr/bin/env python3
"""Fetch exactly the committed upstream tree. No credentials or moving branch builds."""
import hashlib, json, pathlib, subprocess, sys, lzma, tempfile, urllib.request
if not __debug__: raise RuntimeError("Optimized Python would disable verification; refusing")
series = sys.argv[1]
lock = json.loads(pathlib.Path("sources.lock.json").read_text())
item = lock["versions"][series]
sha = item["sha"]
out = pathlib.Path("sources")
out.mkdir(exist_ok=True)
tar = out / ("php-" + series + ".tar")
verified_signer = None
if item.get("kind") == "official-release":
    distribution = out / ("php-" + series + ".tar.xz")
    signature = out / ("php-" + series + ".tar.xz.asc")
    for url,path in [(item["url"],distribution),(item["signature_url"],signature)]:
        with urllib.request.urlopen(url,timeout=90) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(distribution.read_bytes()).hexdigest() != item["distribution_sha256"]:
        raise RuntimeError("Official release distribution checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="php-public-keyring-") as homedir:
        fingerprints=item["allowed_signing_fingerprints"]
        subprocess.run(["gpg","--homedir",homedir,"--batch","--keyserver","hkps://keyserver.ubuntu.com","--recv-keys",*fingerprints],check=True,timeout=180)
        result=subprocess.run(["gpg","--homedir",homedir,"--batch","--status-fd","1","--verify",str(signature),str(distribution)],check=True,capture_output=True,text=True,timeout=30)
        valid=[line.split() for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
        for fields in valid:
            if fields[2] in fingerprints or fields[-1] in fingerprints:
                verified_signer=fields[2]
        if not verified_signer: raise RuntimeError("Release signed by an unexpected fingerprint")
        print(result.stdout)
    tar.write_bytes(lzma.decompress(distribution.read_bytes()))
    tree = None
else:
    repo = out / ("git-" + series)
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "fetch", "--depth=1", lock["upstream"], sha], check=True)
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "FETCH_HEAD"], text=True).strip()
    if actual != sha: raise RuntimeError("Upstream source SHA mismatch: " + actual)
    tree = subprocess.check_output(["git", "-C", str(repo), "rev-parse", sha + "^{tree}"], text=True).strip()
    tar = out / ("php-" + series + ".tar")
    with tar.open("wb") as f:
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", "--prefix=php-src/", sha], stdout=f, check=True)
digest = hashlib.sha256(tar.read_bytes()).hexdigest()
manifest = dict(item, series=series, tree=tree, archive_sha256=digest, upstream=lock["upstream"], verified_signer=verified_signer)
(out / ("php-" + series + ".json")).write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
