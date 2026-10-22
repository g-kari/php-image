#!/usr/bin/env python3
"""Run two unchanged official fixtures with the installed, signed vendor PHP."""
import hashlib,json,os,re,subprocess,sys,tarfile,time
from pathlib import Path,PurePosixPath
from phpt_support import normalize_diff
if sys.argv[1:]!=["8.1"] or os.environ.get("CI_DISPOSABLE_BUILD")!="1" or not Path("/.dockerenv").is_file():
    raise RuntimeError("Only the disposable AL2 8.1 reference phase is supported")
series="8.1";out=Path("/out");target=Path("/tmp/php-vendor-phpt-reference")
pin=json.load(open("/work/al2-official/source-lock.json"))["series"][series]
actual=subprocess.check_output(["rpm","-q","--qf","%{VERSION}|%{RELEASE}","php-common"]).decode()
if actual!=pin["version"]+"|"+pin["release"]:raise RuntimeError("Reference is not the exact original vendor RPM")
binary=Path("/usr/bin/php")
binary_sha=hashlib.sha256(binary.read_bytes()).hexdigest()
vendor=json.load(open(out/"qa/vendor/native.json"))
if vendor["/usr/bin/php"]["sha256"]!=binary_sha:raise RuntimeError("Reference binary differs from observed vendor baseline")
if target.exists():raise RuntimeError("Reference scratch already exists")
target.mkdir()
version_root="php-"+pin["version"];count=total=0;seen=set()
with tarfile.open(out/"prepared-source.tar.gz","r:gz") as archive:
    for member in archive.getmembers():
        path=PurePosixPath(member.name)
        if not path.parts:
            if member.isdir():continue
            raise RuntimeError("Unexpected empty archive member")
        if path.is_absolute() or ".." in path.parts or path.parts[0]!=version_root:
            raise RuntimeError("Unsafe/foreign prepared-source member")
        destination=target.joinpath(*path.parts)
        if member.isdir():destination.mkdir(parents=True,exist_ok=True);continue
        # Never materialize archive links, special files or executable metadata.
        if not member.isfile():continue
        if str(path) in seen:raise RuntimeError("Duplicate source member")
        seen.add(str(path));count+=1;total+=member.size
        if count>50000 or total>768*1024*1024 or member.size>128*1024*1024:
            raise RuntimeError("Prepared reference source exceeds bounds")
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(archive.extractfile(member).read())
source=target/version_root
tests=["ext/date/tests/bug80963.phpt","ext/openssl/tests/openssl_error_string_basic.phpt"]
expected=json.load(open("/work/al2-official/known-phpt-diffs.json"))["source_sha256"][series]
for test in tests:
    if hashlib.sha256((source/test).read_bytes()).hexdigest()!=expected[test]:
        raise RuntimeError("Unchanged official reference fixture bytes differ: "+test)
evidence=out/"qa/vendor-phpt-reference";evidence.mkdir()
environment=os.environ.copy()
for key in ("TZ","LANG","LC_ALL","TEST_PHP_ARGS","TEST_PHP_EXTRA_ARGS","TEST_PHP_CGI_EXECUTABLE"):
    environment.pop(key,None)
environment.update({"TEST_PHP_EXECUTABLE":str(binary),"NO_INTERACTION":"1","REPORT_EXIT_STATUS":"1",
                    "SKIP_ONLINE_TESTS":"1","SKIP_IO_CAPTURE_TESTS":"1","MALLOC_CHECK_":"2"})
command=[str(binary),str(source/"run-tests.php"),"-q","--offline","--set-timeout","30",
         "-p",str(binary),"-c","/etc/php.ini",*tests]
started=time.monotonic()
result=subprocess.run(command,cwd=str(source),env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
(evidence/"run-tests.log").write_bytes(result.stdout)
log=result.stdout.decode(errors="replace")
def number(label):
    matches=re.findall(r"(?m)^"+re.escape(label)+r"\s*:\s*(\d+)",log)
    if not matches and label=="Expected fail" and not re.search(r"\bXFAIL(?:ED)?\b|EXPECTED FAIL",log):
        # Upstream prints this row only when XFAILED > 0. The two exact
        # selected fixtures have no XFAIL sections; all other counts stay required.
        return 0
    if len(matches)!=1:raise RuntimeError("Reference summary missing/ambiguous: "+label)
    return int(matches[0])
stats={label:number(label) for label in ("Number of tests","Tests failed","Tests passed","Tests skipped","Tests warned","Expected fail")}
if result.returncode!=1 or stats!={"Number of tests":2,"Tests failed":2,"Tests passed":0,"Tests skipped":0,"Tests warned":0,"Expected fail":0} or "BORK" in log:
    print(log[-12000:],flush=True)
    raise RuntimeError("Original vendor reference did not reproduce exactly two non-crashing fixture failures")
records={}
for test in tests:
    diff_path=(source/test).with_suffix(".diff");output_path=(source/test).with_suffix(".out")
    if not diff_path.is_file() or not output_path.is_file():raise RuntimeError("Reference evidence missing")
    diff=diff_path.read_text(errors="replace")
    if "** ERROR: process timed out **" in diff or re.search(r"(?m)^[0-9]{3,}\+ .*Termsig=",diff):
        raise RuntimeError("Reference timeout/signal is not an environment explanation")
    key=test.replace(".phpt",".diff")
    records[test]={"actual_status":"FAIL","source_sha256":expected[test],
      "diff":diff,"normalized_diff":normalize_diff(diff,series,key),
      "diff_sha256":hashlib.sha256(diff_path.read_bytes()).hexdigest(),
      "output_sha256":hashlib.sha256(output_path.read_bytes()).hexdigest()}
    (evidence/(Path(test).name+".diff")).write_bytes(diff_path.read_bytes())
    (evidence/(Path(test).name+".out")).write_bytes(output_path.read_bytes())
report={"series":series,"status":"recorded_not_yet_compared","original_statistics":stats,"original_exit":result.returncode,
        "php_common_version_release":actual,"php_sha256":binary_sha,"command":command,"tests":records,
        "dependencies":subprocess.check_output(["rpm","-q","tzdata","openssl-libs"]).decode().splitlines(),
        "seconds":round(time.monotonic()-started,3)}
(out/"qa/VENDOR-PHPT-REFERENCE.json").write_text(json.dumps(report,indent=2,sort_keys=True))
print("ORIGINAL_VENDOR_PHPT_REFERENCE_RECORDED "+json.dumps({"series":series,"statistics":stats,"tests":tests}),flush=True)
