#!/usr/bin/env python3
"""Classify actual paths; unknown ranges run both suites. No publication authority."""
import json,os,re,subprocess,sys
from pathlib import Path
def classify(paths):
    docs={"README.md","NOTICE.md","VERIFY.md","LICENSE-NOTICE.md","LICENSE"}
    classifier={"scripts/classify-ci.py",".github/workflows/verify.yml"}
    shared={"scripts/install-syft.sh"}
    official=lambda p:p.startswith("al2-official/") or p==".github/workflows/al2-official.yml"
    archived=lambda p:p.startswith("al2-parity/") or p==".github/workflows/al2-parity.yml"
    minimal=any(p not in (docs|classifier) and not official(p) and not archived(p) for p in paths)
    return minimal,any(official(p) or p in classifier or p in shared for p in paths)
def main():
    if sys.argv[1:]==["--self-test"]:
        cases=[([], (False,False)),(["README.md"],(False,False)),
          (["al2-official/build.sh"],(False,True)),
          (["al2-parity/old.sh"],(False,False)),
          (["scripts/ci-al2.sh"],(True,False)),
          (["scripts/install-syft.sh"],(True,True)),
          (["docker/Dockerfile","al2-official/build.sh"],(True,True)),
          (["scripts/classify-ci.py",".github/workflows/verify.yml"],(False,True))]
        for paths,expected in cases:
            if classify(paths)!=expected: raise RuntimeError("Classifier self-test failed")
        print("CI_SCOPE_SELF_TEST_PASSED");return
    if sys.argv[1:]: raise RuntimeError("Unexpected arguments")
    event=json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    kind=os.environ["GITHUB_EVENT_NAME"]
    if kind=="workflow_dispatch":
        minimal=official=True
    else:
        base=event["pull_request"]["base"]["sha"] if kind=="pull_request" else event.get("before","")
        head=os.environ["GITHUB_SHA"]
        if not re.fullmatch("[0-9a-f]{40}",base) or base=="0"*40 or not re.fullmatch("[0-9a-f]{40}",head):
            minimal=official=True
        else:
            try:
                # Include both sides of renames: moving legacy code cannot hide a deletion.
                raw=subprocess.check_output(["git","diff","--no-renames","--name-only","-z",base,head],stderr=subprocess.PIPE)
            except subprocess.CalledProcessError:
                minimal=official=True
            else:
                paths=[p.decode("utf-8",errors="strict") for p in raw.split(b"\0") if p]
                minimal,official=classify(paths)
    with open(os.environ["GITHUB_OUTPUT"],"a") as out:
        out.write("minimal="+str(minimal).lower()+"\nofficial="+str(official).lower()+"\n")
    print(json.dumps({"minimal_recipes_changed":minimal,"official_recipes_changed":official}))
if __name__=="__main__":main()
