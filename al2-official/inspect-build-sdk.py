#!/usr/bin/env python3
"""Inspect exact AWS-published SDK candidates without installing their headers/libraries."""
import hashlib,json,os,re,subprocess
from pathlib import Path
if os.environ.get("CI_DISPOSABLE_BUILD")!="1" or not Path("/.dockerenv").is_file():raise RuntimeError("Disposable SDK evidence only")
out=Path("/out/exact-sdk");out.mkdir()
def run(argv,timeout=120):
    p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if p.returncode:raise RuntimeError("SDK command failed: "+repr(argv)+"\n"+p.stderr.decode("utf-8","replace")[-4000:]+"\n"+p.stdout.decode("utf-8","replace")[-4000:])
    if len(p.stdout)>1000000 or len(p.stderr)>100000:raise RuntimeError("Diagnostic output bound")
    return p.stdout.decode("utf-8","replace")
def emit(name,data):
    (out/(name+".json")).write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    print("EXACT_SDK_EVIDENCE "+json.dumps({"name":name,"evidence":data},sort_keys=True),flush=True)
key=Path("/etc/pki/rpm-gpg/RPM-GPG-KEY-amazon-linux-2")
fp=run(["gpg2","--batch","--with-colons","--with-fingerprint",str(key)])
fingerprints=[line.split(":")[9] for line in fp.splitlines() if line.startswith("fpr:")]
if fingerprints!=["99E617FE5DB527C0D8BD5F8E11CF1F95C87F5B1A"]:raise RuntimeError("Unexpected preexisting AWS public key fingerprint")
emit("preexisting-aws-key",{"fingerprints":fingerprints,"file_sha256":hashlib.sha256(key.read_bytes()).hexdigest(),"inspection":fp})
emit("configured-core-repository",run(["yum","repolist","-v","amzn2-core"]))
requests=[
 ["libcurl-devel","7.79.1","7.amzn2.0.1","x86_64"],
 ["libcurl-devel","7.88.1","1.amzn2.0.1","x86_64"],
 ["postgresql-devel","9.2.24","1.amzn2.0.1","x86_64"],
 ["postgresql-devel","9.2.24","6.amzn2","x86_64"],
 ["postgresql-devel","9.2.24","8.amzn2","x86_64"]]
packages=out/"rpms";packages.mkdir()
for row in requests:
    name=row[0]+"-"+row[1]+"-"+row[2]+"."+row[3]
    emit("location-"+name,run(["repoquery","--disablerepo=*","--enablerepo=amzn2-core","--location",name]))
    run(["yumdownloader","--disablerepo=*","--enablerepo=amzn2-core","--destdir="+str(packages),name])
    package=packages/(name+".rpm")
    if not package.is_file() or package.is_symlink() or package.stat().st_size>16000000:raise RuntimeError("SDK RPM download bound")
    signature=run(["rpm","--checksig","--verbose",str(package)])
    if not re.search(r"RSA.*[Ss]ignature.*key ID c87f5b1a: OK",signature,re.I) or re.search(r"(^|[^A-Za-z0-9_])(NOKEY|NOT OK|BAD|NOTTRUSTED)([^A-Za-z0-9_]|$)",signature,re.I):raise RuntimeError("SDK signature unverified")
    identity=run(["rpm","-qp","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}|%{LICENSE}",str(package)])
    fields=identity.split("|")
    if len(fields)!=7 or [fields[0],fields[2],fields[3],fields[4]]!=row:raise RuntimeError("SDK RPM identity mismatch")
    requires=run(["rpm","-qp","--requires",str(package)])
    files=run(["rpm","-qpl",str(package)]).splitlines()
    headers={}
    for path in files:
        if not re.search(r"/(curl|curlver|system|pg_config(?:_x86_64|_manual|_ext)?)\.h$",path):continue
        if not path.startswith("/usr/include/") or ".." in Path(path).parts:raise RuntimeError("Unexpected SDK header path")
        p=subprocess.run(["bash","-o","pipefail","-c",'rpm2cpio "$1" | cpio -i --quiet --to-stdout "$2"',"_",str(package),"."+path],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
        raw=p.stdout
        if p.returncode or p.stderr or not raw or len(raw)>300000:raise RuntimeError("Raw header extraction failed: "+p.stderr.decode("utf-8","replace")[-1000:])
        text=raw.decode("utf-8","replace")
        if path.endswith("/curl.h") and "CURLINFO_LASTONE" not in text:raise RuntimeError("Incomplete curl header")
        (out/(name+"-"+path.replace("/","_"))).write_bytes(raw)
        relevant=[{"line":index+1,"text":line} for index,line in enumerate(text.splitlines()) if re.search(r"CURLINFO_LASTONE|CURLVERSION_NOW|CURLVERSION_(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH)|CURL_MAX_READ_SIZE|LIBCURL_VERSION|PG_VERSION_STR|PG_VERSION_NUM|include.*pg_config",line)]
        headers[path]={"sha256":hashlib.sha256(raw).hexdigest(),"size":len(raw),"relevant_lines":relevant}
    expected="/usr/include/curl/curl.h" if row[0]=="libcurl-devel" else "/usr/include/pg_config_x86_64.h"
    if expected not in headers:raise RuntimeError("Architecture-specific target header missing")
    emit("package-"+name,{"identity":identity,"rpm_sha256":hashlib.sha256(package.read_bytes()).hexdigest(),"signature":signature,"requires":requires,"headers":headers})
print("EXACT_SDK_HEADER_DIAGNOSTIC_COMPLETE")
