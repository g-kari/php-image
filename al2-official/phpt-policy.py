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
statistics={key:number(key) for key in ("Tests failed","Tests skipped","Tests passed","Expected fail","Tests warned","Tests borked","Number of tests")}
print("PHPT_ORIGINAL_STATISTICS "+json.dumps(statistics,sort_keys=True),flush=True)
def review_warnings(text,series,members,source):
    blocks=re.findall(r"(?m)^WARNED TEST SUMMARY\n-{5,}\n([\s\S]*?)^={5,}\s*$",text.replace("\r",""))
    if not blocks:return []
    if len(blocks)!=1:raise RuntimeError("Ambiguous PHPT WARN summary")
    lines=[line for line in blocks[0].splitlines() if line.strip()]
    print("PHPT_ORIGINAL_WARNINGS "+json.dumps(lines),flush=True)
    expected="Test hrtime() aligns with microtime() [ext/standard/tests/hrtime/hrtime.phpt] (warn: XFAIL section but test passes)"
    if series!="8.0" or lines!=[expected]:raise RuntimeError("Unclassified PHPT WARN summary")
    candidates=[m for name,m in members.items() if name.endswith("/ext/standard/tests/hrtime/hrtime.phpt")]
    if len(candidates)!=1:raise RuntimeError("WARN source fixture missing or ambiguous")
    data=source.extractfile(candidates[0]).read()
    expected_sha="c969e0d308fbbfaa89a7bae6a5e245c67b884a7bf31825eb31b02e77ba848f73"
    if hashlib.sha256(data).hexdigest()!=expected_sha:raise RuntimeError("Known WARN source fixture changed")
    return [{"test":"ext/standard/tests/hrtime/hrtime.phpt","actual_status":"WARN","summary":expected,
      "source_sha256":expected_sha,"classification":"The unchanged upstream timing test has an XFAIL section but matches its expected output. Retained as WARN, not relabeled PASS."}]
session={"rfc1867","rfc1867_inter","rfc1867_sid_cookie","rfc1867_sid_get","rfc1867_sid_get_2",
 "rfc1867_sid_invalid","rfc1867_sid_only_cookie","rfc1867_sid_post"}
allow=json.load(open("/work/al2-official/known-phpt-diffs.json"))["series"][series]
def retained_diff_status(source):
    return "XFAIL" if re.search(r"(?m)^--XFAIL(?:_EXTERNAL)?--\s*$",source) else "FAIL"
def abnormal_actual_hunks(diff):
    records=[]
    for line in diff.split("\n"):
        if line.endswith("\r"):line=line[:-1]
        match=re.fullmatch(r"[0-9]{3,}\+ (.*)",line)
        if not match:continue
        actual=match.group(1).strip(" \t")
        if actual=="** ERROR: process timed out **":
            records.append({"kind":"timeout","actual":actual})
        elif re.fullmatch(r"Termsig=-?[0-9]+",actual):
            records.append({"kind":"signal","actual":actual})
    return records
def normalize(value):
    value=value.replace("\r","")
    value=re.sub(r"/home/builder/rpmbuild/BUILD/php-[0-9.]+/","<SOURCE>/",value)
    value=re.sub(r"/tmp/php[A-Za-z0-9]{6}\b","/tmp/php<FIXTURE>",value)
    return value.rstrip()+"\n"
results=[];expected=[];unclassified=[];warning_error=None
with tarfile.open("/out/prepared-source.tar.gz","r:gz") as source:
    members={(m.name[2:] if m.name.startswith("./") else m.name):m for m in source.getmembers()}
    try:warnings=review_warnings(log,series,members,source)
    except RuntimeError as error:
        warning_error=str(error);warnings=[]
        print("PHPT_WARNING_CLASSIFICATION_BLOCKED "+warning_error,flush=True)
    for path in sorted((root/"build-evidence").rglob("*.diff")):
        rel=path.relative_to(root/"build-evidence")
        candidate=str(rel.with_suffix(".phpt"))
        member=members.get(candidate)
        if member is None:raise RuntimeError("PHPT source absent for "+candidate)
        text=source.extractfile(member).read().decode(errors="replace")
        diff=path.read_text(errors="replace")
        record={"test":"/".join(rel.parts[1:]).replace(".diff",".phpt"),"actual_status":"FAIL",
                "diff_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"diff":diff}
        record["actual_status"]=retained_diff_status(text)
        abnormal=abnormal_actual_hunks(diff)
        if abnormal:
            record["classification_error"]="Added actual timeout/signal sentinel blocks even when upstream marks this test XFAIL."
            record["abnormal_actual_hunks"]=abnormal
            unclassified.append(record);continue
        if record["actual_status"]=="XFAIL":
            expected.append(record);continue
        name=path.stem;where="/".join(rel.parts[1:])
        if where not in allow or normalize(diff)!=allow[where]:
            unclassified.append(record)
            continue
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
if unclassified or warning_error:
    blocked={"series":series,"statistics":statistics,"status":"blocked","all_tests_passed":False,
      "classified_failures":results,"unclassified_failures":unclassified,"original_warnings":warnings,
      "warning_classification_error":warning_error,"expected_fail_evidence":expected}
    (root/"qa"/"PHPT-RESULTS.json").write_text(json.dumps(blocked,indent=2,sort_keys=True))
    print("PHPT_UNCLASSIFIED_TESTS "+json.dumps([item["test"] for item in unclassified]),flush=True)
    for item in unclassified[:100]:
        print("UNCLASSIFIED_DIFF_BEGIN "+item["test"]+"\n"+item["diff"][:30000]+"\nUNCLASSIFIED_DIFF_END",flush=True)
    raise RuntimeError("Unclassified PHPT evidence blocks publication; all available failures were collected")
if len(results)!=statistics["Tests failed"] or len(warnings)!=statistics["Tests warned"] or statistics["Tests borked"]!=0:
    print("PHPT_INVENTORY_MISMATCH "+json.dumps({"statistics":statistics,"classified_failures":len(results),"classified_warnings":len(warnings)}),flush=True)
    raise RuntimeError("PHPT failure inventory/count mismatch")
report={"series":series,"statistics":statistics,"original_failures":results,"original_warnings":warnings,"expected_fail_evidence":expected,
 "status":"no_unclassified_failure","timeout_policy":"Added actual timeout/Termsig sentinels block even for XFAIL; new ordinary FAIL diffs/counts also block. Original suite statuses and vendor SKIP/XFAIL remain separate.","all_tests_passed":False,
 "limitations":["The original vendor suite uses the without-shared Apache build CLI and has many SKIPs.",
 "Known FAILs have explanations and replacement runtime gates; they are not relabeled PASS."]}
(root/"qa"/"PHPT-RESULTS.json").write_text(json.dumps(report,indent=2,sort_keys=True))
print("PHPT_REVIEWED_FAILURE_INVENTORY "+json.dumps({"series":series,"statistics":statistics,
 "actual_failures":[r["test"] for r in results],"original_warnings":warnings,"all_tests_passed":False}))
