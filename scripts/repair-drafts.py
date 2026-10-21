#!/usr/bin/env python3
"""Recover these exact draft artifacts. No rebuild, no image push, no asset deletion."""
import datetime, hashlib, json, os, pathlib, re, subprocess, sys, time, urllib.parse
REPO="g-kari/php-image"
SOURCE="3e399dfb045304bdb0681d57471b653a1dbdc379"
RUN=39645578662
JOBS={"al2:7.4":119380133565,"al2:8.0":119380133630,"al2:8.1":119380133654,
      "fpm:7.4":119380132928,"fpm:8.0":119380133542,"fpm:8.1":119380133540}
SHAS={"7.4":"712e60f9edfd03f0960fc4fc3c2c375f42b90aa2","8.0":"82f8f31b16a035c1b67cc253e79f7cc288f4cc20","8.1":"1d7dec178a094e6e75b229ce22754045f8c6070a"}
mode,target,series=sys.argv[1:]
key=target+":"+series
if key not in JOBS or os.environ["GITHUB_REPOSITORY"]!=REPO: raise RuntimeError("Wrong repair scope")
tag=target+"-"+series+"-"+SOURCE[:12]
out=pathlib.Path("out")
out.mkdir(exist_ok=True)
def gh(*args):
    return subprocess.check_output(["gh","api",*args])
def api(path):
    return json.loads(gh(path))
def current():
    if api("repos/"+REPO+"/git/ref/heads/main")["object"]["sha"]!=SOURCE:
        raise RuntimeError("Main advanced; do not publish superseded artifacts")
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def release():
    matches=[r for r in api("repos/"+REPO+"/releases?per_page=100") if r["tag_name"]==tag]
    if len(matches)!=1: raise RuntimeError("Exact draft missing or duplicated")
    r=matches[0]
    if r["target_commitish"]!=SOURCE:raise RuntimeError("Wrong release source")
    return r
def validate_gates():
    run=api("repos/"+REPO+"/actions/runs/"+str(RUN))
    if run["head_sha"]!=SOURCE or run["head_branch"]!="main" or run["event"]!="push":
        raise RuntimeError("Unexpected build run")
    deadline=time.monotonic()+600
    while True:
        job=api("repos/"+REPO+"/actions/jobs/"+str(JOBS[key]))
        step=next((s for s in job["steps"] if s["name"].startswith("Build and test")),None)
        if step and step["status"]=="completed":
            if step["conclusion"]!="success":raise RuntimeError("Build/runtime gate failed")
            return
        if time.monotonic()>deadline:raise RuntimeError("Build gate still pending")
        time.sleep(15)
def verify_assets(r):
    for a in r["assets"]:
        name=a["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+",name):raise RuntimeError("Unsafe asset name")
        path=out/name
        with path.open("wb") as f:
            subprocess.run(["gh","api","-H","Accept: application/octet-stream","repos/"+REPO+"/releases/assets/"+str(a["id"])],stdout=f,check=True)
        if path.stat().st_size!=a["size"] or "sha256:"+digest(path)!=a.get("digest"):
            raise RuntimeError("Downloaded asset digest/size mismatch: "+name)
if mode=="download":
    current();validate_gates()
    r=release()
    if not r["draft"]:raise RuntimeError("Release already public; reconcile rather than overwrite")
    verify_assets(r)
    sums={}
    for line in (out/"SHA256SUMS").read_text().splitlines():
        sha,name=line.split(None,1)
        name=name.strip().removeprefix("./")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+",name) or not re.fullmatch(r"[0-9a-f]{64}",sha):
            raise RuntimeError("Invalid original checksum entry")
        sums[name]=sha
    for p in out.iterdir():
        if p.name!="SHA256SUMS" and sums.get(p.name)!=digest(p):
            raise RuntimeError("Original manifest mismatch: "+p.name)
    missing=sorted(set(sums)-{p.name for p in out.iterdir()})
    if target=="fpm" and missing:raise RuntimeError("Incomplete FPM artifacts")
    source_path=out/"source.json"
    if not source_path.exists():
        candidate=out/("php"+series.replace(".","")+"-mitigation-source.json")
        if digest(candidate)!=sums.get("source.json"):raise RuntimeError("Missing source manifest not reproducible")
        source_path.write_bytes(candidate.read_bytes())
    source=json.loads(source_path.read_text())
    prov=json.loads((out/"provenance.json").read_text())
    test=json.loads((out/"fpm-test.json").read_text())
    if source["sha"]!=SHAS[series] or prov["recipe_commit"]!=SOURCE or prov["series"]!=series or not test["oom_recovery_passed"]:
        raise RuntimeError("Wrong source/provenance/runtime profile")
    (pathlib.Path("repair-state.json")).write_text(json.dumps({"release":r,"original_checksums":sums,"missing":missing,"target":target,"series":series}))
    print(json.dumps({"verified_existing_artifacts":tag,"missing_uploads":missing}))
elif mode=="publish":
    current();validate_gates()
    state=json.load(open("repair-state.json"))
    r=release()
    if r["id"]!=state["release"]["id"] or not r["draft"]:raise RuntimeError("Release state changed")
    if target=="al2":
        # Runtime validation of the SAME already-built RPM is repeated, not compilation.
        for name in ["runtime-functions.json","fpm-test.json","sbom.spdx.json","runtime-source.json","binaries.sha256"]:
            if not (out/name).is_file():raise RuntimeError("Missing repeated runtime proof: "+name)
        if not json.load(open(out/"fpm-test.json"))["oom_recovery_passed"]:raise RuntimeError("Repeated FPM gate failed")
        if json.load(open(out/"runtime-functions.json"))["checks"]!="passed":raise RuntimeError("Shared-library gate failed")
        if json.load(open(out/"runtime-source.json"))["sha"]!=SHAS[series]:raise RuntimeError("Installed source mismatch")
        if digest(out/"binaries.sha256")!=state["original_checksums"]["binaries.sha256"]:
            raise RuntimeError("Installed RPM bytes differ from the originally tested binary hashes")
        # GitHub rejects zero-byte upload bodies. Preserve the successful empty-result meaning explicitly.
        if (out/"rpm-verify.txt").read_bytes()!=b"":raise RuntimeError("rpm -V reported a change")
        (out/"rpm-verify.txt").write_text("rpm -V completed successfully with no modified files; original command output was empty.\n")
        (out/"PUBLICATION-VERIFICATION.json").write_text(json.dumps({"source_commit":SOURCE,"original_build_run":RUN,
            "same_original_rpm_reinstalled_and_retested":True,"repair_run":os.environ["GITHUB_RUN_ID"],
            "observed_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "note":"Missing upload-only runtime evidence regenerated from the same original RPM. No binary rebuild or image push."},indent=2)+"\n")
        # Preserve original evidence instead of deleting/clobbering it.
        old={a["name"]:a for a in r["assets"]}
        for name,a in list(old.items()):
            path=out/name
            if path.is_file() and ("sha256:"+digest(path)!=a["digest"] or name=="SHA256SUMS"):
                backup=name+".original-upload"
                if backup in old:raise RuntimeError("Prior partial repair requires reconciliation")
                gh("--method","PATCH","repos/"+REPO+"/releases/assets/"+str(a["id"]),"-f","name="+backup)
                if name=="SHA256SUMS":path.rename(out/backup)
                else:
                    original=next(x for x in state["release"]["assets"] if x["name"]==name)
                    with (out/backup).open("wb") as fp:
                        subprocess.run(["gh","api","-H","Accept: application/octet-stream","repos/"+REPO+"/releases/assets/"+str(original["id"])],stdout=fp,check=True)
        lines=[digest(p)+"  ./"+p.name for p in sorted(out.iterdir()) if p.is_file() and p.name!="SHA256SUMS"]
        (out/"SHA256SUMS").write_text("\n".join(lines)+"\n")
        current()
        present={a["name"]:a for a in api("repos/"+REPO+"/releases/"+str(r["id"]))["assets"]}
        for p in sorted(out.iterdir()):
            if not p.is_file():continue
            if p.name in present:
                if present[p.name]["digest"]!="sha256:"+digest(p):raise RuntimeError("Existing asset changed unexpectedly")
                continue
            if p.stat().st_size==0:raise RuntimeError("Cannot upload an empty asset")
            url="https://uploads.github.com/repos/"+REPO+"/releases/"+str(r["id"])+"/assets?name="+urllib.parse.quote(p.name)
            gh("--method","POST","-H","Content-Type: application/octet-stream",url,"--input",str(p))
    final=api("repos/"+REPO+"/releases/"+str(r["id"]))
    local={p.name:p for p in out.iterdir() if p.is_file()}
    remote={a["name"]:a for a in final["assets"]}
    if set(local)!=set(remote):raise RuntimeError("Final asset set mismatch")
    for name,p in local.items():
        a=remote[name]
        if a["size"]!=p.stat().st_size or a["digest"]!="sha256:"+digest(p):raise RuntimeError("Final asset hash mismatch: "+name)
    current()
    published=json.loads(gh("--method","PATCH","repos/"+REPO+"/releases/"+str(r["id"]),"-F","draft=false"))
    if published["draft"]:raise RuntimeError("Release is still a draft")
    print("PUBLIC_RELEASE_URL="+published["html_url"])
    if target=="fpm":
        print((out/"IMAGE.txt").read_text())
        try:
            pkg=api("users/g-kari/packages/container/php-image")
            print("PACKAGE_METADATA="+json.dumps({k:pkg.get(k) for k in ["name","html_url","visibility"]}))
        except subprocess.CalledProcessError: print("Package UI metadata unavailable; visibility still separate.")
else:raise RuntimeError("Unknown repair mode")
