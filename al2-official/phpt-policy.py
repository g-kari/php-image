#!/usr/bin/env python3
"""Retain original PHPT FAILs; reject any failure without a narrow reviewed explanation."""
import hashlib,json,re,sys,tarfile
from pathlib import Path
series=sys.argv[1];root=Path("/out")
log=(root/"build.log").read_text(errors="replace")
def number(label):
    matches=re.findall(r"(?m)^"+re.escape(label)+r"\s*:\s*(\d+)",log)
    if not matches and label=="Tests borked" and "BORK" not in log:return 0
    if len(matches)!=1:raise RuntimeError("Missing/ambiguous PHPT summary "+label)
    return int(matches[0])
statistics={key:number(key) for key in ("Tests failed","Tests skipped","Tests passed","Expected fail","Tests warned","Tests borked")}
session={"rfc1867","rfc1867_inter","rfc1867_sid_cookie","rfc1867_sid_get","rfc1867_sid_get_2",
 "rfc1867_sid_invalid","rfc1867_sid_only_cookie","rfc1867_sid_post"}
allow=json.load(open("/work/al2-official/known-phpt-diffs.json"))["series"][series]
def normalize(value):
    value=value.replace("\r","")
    value=re.sub(r"/home/builder/rpmbuild/BUILD/php-[0-9.]+/","<SOURCE>/",value)
    value=re.sub(r"/tmp/php[A-Za-z0-9]{6}\b","/tmp/php<FIXTURE>",value)
    return value.rstrip()+"\n"
results=[];expected=[]
with tarfile.open("/out/prepared-source.tar.gz","r:gz") as source:
    members={(m.name[2:] if m.name.startswith("./") else m.name):m for m in source.getmembers()}
    for path in sorted((root/"build-evidence").rglob("*.diff")):
        rel=path.relative_to(root/"build-evidence")
        candidate=str(rel.with_suffix(".phpt"))
        member=members.get(candidate)
        if member is None:raise RuntimeError("PHPT source absent for "+candidate)
        text=source.extractfile(member).read().decode(errors="replace")
        diff=path.read_text(errors="replace")
        record={"test":"/".join(rel.parts[1:]).replace(".diff",".phpt"),"actual_status":"FAIL",
                "diff_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"diff":diff}
        if re.search(r"(?m)^--XFAIL(?:_EXTERNAL)?--\s*$",text):
            record["actual_status"]="XFAIL";expected.append(record);continue
        name=path.stem;where="/".join(rel.parts[1:])
        if where not in allow or normalize(diff)!=allow[where]:
            print("UNCLASSIFIED_DIFF_BEGIN "+where+"\n"+diff+"\nUNCLASSIFIED_DIFF_END",flush=True)
            raise RuntimeError("Known PHPT diff changed beyond the exact reviewed oracle: "+where)
        if where.startswith("ext/session/tests/") and name in session:
            if not ("NULL" in diff or ("session id is too long" in diff and name=="rfc1867_sid_invalid")):
                raise RuntimeError("Unclassified upload-progress diff")
            record["classification"]="Intentional callback removal; direct vendor/patched FPM progress contrast is separately required."
        elif where=="tests/lang/bug45392.diff":
            changes=re.findall(r"(?m)^\d+[+-]\s?(.*)$",diff)
            if changes!=[""]:raise RuntimeError("OOM output difference is not the single known newline")
            record["classification"]="Official allocator diagnostic adds one leading newline; original FAIL retained."
        elif where in ("ext/openssl/tests/sni_server.diff","ext/openssl/tests/sni_server_key_cert.diff"):
            if "certificate verify failed" not in diff:raise RuntimeError("Unexpected SNI failure")
            record["classification"]="Historical server fixture certificates expired 2026-04-02. Current strict local TLS positive/negative/positive and normal CA origin checks separately required."
        elif series=="7.4" and where=="ext/date/tests/bug33415-2.diff":
            if "+04" not in diff or "+0330" not in diff:raise RuntimeError("Unexpected date diff")
            record["classification"]="Historical Tehran tzdata expectation corrected in tzdb2022b; unchanged vendor binary and exact tzdata NEVRA are separately compared."
        else:raise RuntimeError("Unclassified PHPT failure: "+where)
        results.append(record)
if len(results)!=statistics["Tests failed"] or statistics["Tests warned"]!=0 or statistics["Tests borked"]!=0:
    raise RuntimeError("PHPT failure inventory/count mismatch")
report={"series":series,"statistics":statistics,"original_failures":results,"expected_fail_evidence":expected,
 "status":"no_unclassified_failure","timeout_policy":"Any new timeout changes an exact failure oracle or count and blocks; vendor SKIP/XFAIL remain separate.","all_tests_passed":False,
 "limitations":["The original vendor suite uses the without-shared Apache build CLI and has many SKIPs.",
 "Known FAILs have explanations and replacement runtime gates; they are not relabeled PASS."]}
(root/"qa"/"PHPT-RESULTS.json").write_text(json.dumps(report,indent=2,sort_keys=True))
print("PHPT_REVIEWED_FAILURE_INVENTORY "+json.dumps({"series":series,"statistics":statistics,
 "actual_failures":[r["test"] for r in results],"all_tests_passed":False}))
