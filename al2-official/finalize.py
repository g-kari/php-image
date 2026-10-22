#!/usr/bin/env python3
import gzip,hashlib,json,os,re,shutil,tarfile,sys
from pathlib import Path
series=sys.argv[1];out=Path("out");release=Path("release");release.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=json.load(open(out/"qa/FINAL-RESULT.json"));phpt=json.load(open(out/"qa/PHPT-RESULTS.json"))
if result["status"]!="passed" or phpt["status"]!="no_unclassified_failure":raise RuntimeError("Final gates missing")
if json.load(open(out/"qa/rpm-comparison.json"))["status"]!="passed":raise RuntimeError("RPM comparison failed")
if json.load(open(out/"qa/vendor-pecl-audit.json"))["unresolved"]:raise RuntimeError("Unresolved PECL callsite")
lock=json.load(open("al2-official/source-lock.json"))["series"][series]
sources=list(out.glob("php-*.src.rpm"))
if len(sources)!=1:raise RuntimeError("Source RPM missing or ambiguous")
for p in [*sorted((out/"rpms").glob("*.rpm")),*sources]:
    shutil.copy2(p,release/p.name)
for name in ("recipe.spec","official-php.spec","spec-diff.txt","built-package-metadata.txt","built-package-files.txt","sbom.spdx.json","php-upstream-cve2026.patch","upstream-security-commit.txt","upstream-security-patch-files.txt","official-srpm-signature.txt","parsed-nevr.txt","build-rpms.txt"):
    p=out/name
    if not p.is_file() or not p.stat().st_size:raise RuntimeError("Required evidence missing: "+name)
    shutil.copy2(p,release/p.name)
for name in ("LICENSE","NOTICE.md","LICENSE-NOTICE.md"):shutil.copy2(name,release/name)
with tarfile.open(release/"qa-evidence.tar.gz","w:gz") as archive:
    for name in ("qa","build-evidence","license-evidence"):
        archive.add(out/name,arcname=name,recursive=True)
    for p in sorted(out.glob("*.log")):archive.add(p,arcname="logs/"+p.name)
with tarfile.open(release/"upstream-license-notices.tar.gz","w:gz") as archive:
    archive.add(out/"license-evidence",arcname="license-evidence")
rpm_digests={p.name:sha(p) for p in release.glob("*.rpm")}
provenance={"schema":1,"series":series,"arch":"x86_64","recipe_commit":os.environ["GITHUB_SHA"],
 "workflow_run":os.environ["GITHUB_SERVER_URL"]+"/"+os.environ["GITHUB_REPOSITORY"]+"/actions/runs/"+os.environ["GITHUB_RUN_ID"],
 "official_srpm":lock["srpm"],"official_srpm_sha256":lock["sha256"],"upstream_security_commit":lock["commit"],
 "upstream_security_parent":lock["parent"],"patch_sha256":sha(release/"php-upstream-cve2026.patch"),
 "rpm_sha256":rpm_digests,"source_spec_delta":"Complete upstream security patch plus explicit local Release suffix; all vendor build flags/patches/splits retained.",
 "license_inventory_sha256":sha(out/"license-evidence/LICENSE-INVENTORY.json"),
 "qa_status":"passed bounded gates; original known PHPT failures are retained, not relabeled",
 "original_phpt_statistics":phpt["statistics"],"amazon_signed_output":False,
 "limits":result["limits"]}
(release/"provenance.json").write_text(json.dumps(provenance,indent=2,sort_keys=True)+"\n")
notes="""# Unofficial AL2 official-layout PHP security rebuild
This is not Amazon-signed or an Amazon/PHP supported release. x86_64 only.
The exact full source/security SHA and input SRPM hash are in provenance.json.
All main-source subpackages were rebuilt together; normal AWS paths, package splits, vendor flags, config and services are retained.
Unlike the older separate-prefix artifacts, these packages replace the corresponding installed system PHP cohort.
Install only the matching series/cohort after staging review; do not install every optional package just because it is available.
Original vendor PHPT tests run unchanged. Known FAILs/SKIPs/XFAILs and exact explanations remain in qa-evidence.tar.gz; this is NOT an all-tests-pass statement.
Additional packaged-SAPI/module, PECL, ELF/header/API, strict TLS, upload/session/OOM, official-to-rebuild config-preserving update and original-RPM rollback checks passed in a disposable AL2 container.
Systemd unit activation and real applications remain untested. API numbering does not prove every private extension ABI.
The official EOL patch terminates OOM execution with exit1 without normal shutdown callbacks and disables builtin session upload-progress; normal uploads still work.
7.4 additionally introduces the multipart total-part limit. Existing unmodified third-party/private modules require separate vendor review.
Rollback to the original saved RPMs restores known vulnerabilities. No real server was modified.
See LICENSE-NOTICE.md, upstream-license-notices.tar.gz and the complete source RPM before redistribution. Repository MIT is not a license for PHP or all dependencies.
No public yum repository/signing key is introduced; no signature checks were disabled.
"""
(release/"RELEASE-NOTES.md").write_text(notes)
# Text-only evidence contains no environment dumps or credentials. Public upstream fixture keys remain in original source archives, not this scan scope.
secret=re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}")
for p in release.iterdir():
    if p.suffix not in (".rpm",".gz") and secret.search(p.read_bytes()):raise RuntimeError("Potential secret in public evidence: "+p.name)
(release/"SHA256SUMS").write_text("".join(sha(p)+"  "+p.name+"\n" for p in sorted(release.iterdir()) if p.name!="SHA256SUMS"))
print("FINAL_PUBLICATION_SET_READY "+json.dumps({"series":series,"files":len(list(release.iterdir())),"rpm_sha256":rpm_digests},sort_keys=True))
