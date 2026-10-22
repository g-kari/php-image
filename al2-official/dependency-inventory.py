#!/usr/bin/env python3
"""Read-only dependency/SDK evidence in an already disposable diagnostic container."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
series=sys.argv[1]
if series not in ("7.4","8.0","8.1") or os.environ.get("CI_DISPOSABLE_BUILD")!="1" or not Path("/.dockerenv").is_file():
    raise RuntimeError("Disposable AL2 diagnostic only")
out=Path("/out/dependency-diagnostic");out.mkdir()
def command(argv,timeout=120,allowed=(0,)):
    p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    if len(p.stdout)>1000000:raise RuntimeError("Diagnostic output exceeded bound")
    text=p.stdout.decode("utf-8","replace")
    if p.returncode not in allowed:raise RuntimeError("Diagnostic command failed: "+repr(argv)+"\n"+text[-12000:])
    return {"returncode":p.returncode,"output":text}
def emit(name,value):
    (out/(name+".json")).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
    print("DEPENDENCY_DIAGNOSTIC "+json.dumps({"series":series,"name":name,"evidence":value},sort_keys=True),flush=True)
def digest():
    names=command(["rpm","-ql","glibc","openssl-libs"])["output"].splitlines()+["/usr/bin/openssl"]
    result={}
    for name in sorted(set(names)):
        p=Path(name)
        if p.is_file():
            result[name]={"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"realpath":str(p.resolve())}
    return result
code=r"""$names=["CURLINFO_LASTONE","CURLVERSION_NOW","CURL_MAX_READ_SIZE","PGSQL_LIBPQ_VERSION_STR","\\0apc_register_serializer-0"];
$result=[];foreach($names as $name){if(defined($name)){$value=constant($name);$result[$name]=["type"=>gettype($value),"value"=>$value];}}
$all=get_defined_constants();foreach($all as $name=>$value){if(strpos($name,"apc_register_serializer")!==false){$result[$name]=["type"=>gettype($value),"value"=>$value];}}
$maps=@file("/proc/self/maps",FILE_IGNORE_NEW_LINES);if($maps!==false){$result["apcu_maps"]=array_values(array_filter($maps,function($line){return strpos($line,"/apcu.so")!==false;}));}
$curl=curl_version();$result["curl_runtime"]=["version"=>$curl["version"],"ssl_version"=>$curl["ssl_version"],"libz_version"=>$curl["libz_version"]];
echo json_encode($result,JSON_THROW_ON_ERROR);"""
observations=[json.loads(command(["php","-r",code])["output"]) for _ in range(2)]
emit("original-php-constants",observations)
if series=="7.4":
    source=json.load(open("/out/qa/vendor-pecl-audit.json"))
    apcu=[item for item in source["sources"] if item["name"]=="php-pecl-apcu"]
    if len(apcu)!=1:raise RuntimeError("APCu source inventory missing")
    expected={"apc_serializer.h":"a43db724d416aa391cbd7092408912788a9c5c86ad6355affef2d05558f6b6eb",
      "php_apc.c":"d220a3f4d1eba1594f8ae27a827652cc222a7fa245dabb6bf14c38dbdfab05bc",
      "apc.c":"b694c62302b705c29cf162189448436257b5ae88b39770f6a98b137b3185db18"}
    evidence={Path(item["path"]).name:item for item in apcu[0]["files"] if Path(item["path"]).name in expected}
    emit("apcu-source-pointer-registration",{"srpm":apcu[0]["srpm"],"srpm_sha256":apcu[0]["srpm_sha256"],"files":evidence,"expected_upstream_sha256":expected})
    module=Path("/usr/lib64/php/modules/apcu.so")
    emit("apcu-elf-pointer-symbol",{"sha256":hashlib.sha256(module.read_bytes()).hexdigest(),
      "symbols":[line for line in command(["readelf","--dyn-syms","--wide",str(module)])["output"].splitlines() if "_apc_register_serializer" in line],
      "program_headers":command(["readelf","--program-headers","--wide",str(module)])["output"]})
emit("original-php-build-metadata",command(["rpm","-q","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{BUILDTIME}\n","php-common","php-cli"]))
emit("actual-runtime-dependencies",command(["rpm","-q","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}\n","glibc","openssl-libs","libcurl","curl","postgresql-libs","libcurl-devel","postgresql-devel"],allowed=(0,1)))
before=digest()
emit("system-files-before-ldconfig",before)
command(["/sbin/ldconfig"])
after=digest()
changed={name:{"before":before.get(name),"after":after.get(name)} for name in sorted(set(before)|set(after)) if before.get(name)!=after.get(name)}
emit("system-files-after-ldconfig-differences",changed)
for name in changed:emit("changed-owner-"+str(len(name))+"-"+hashlib.sha256(name.encode()).hexdigest()[:8],command(["rpm","-qf",name]))
query=command(["repoquery","--disablerepo=*","--enablerepo=amzn2-core","--show-duplicates","--qf","%{name}|%{version}|%{release}|%{arch}","libcurl-devel","postgresql-devel"])
emit("available-sdk-nevras",query)
records=[]
for line in query["output"].splitlines():
    fields=line.split("|")
    if len(fields)==4 and fields[0] in ("libcurl-devel","postgresql-devel") and fields[3]=="x86_64":
        if any(not re.fullmatch(r"[A-Za-z0-9_.+~-]+",field) for field in fields):raise RuntimeError("Malformed SDK identity")
        records.append(fields)
# Query text is retained in full. Limit downloads to oldest/newest representative
# records per version, with a hard cap, not an unbounded historical SDK scan.
selected=[]
for package in ("libcurl-devel","postgresql-devel"):
    groups={}
    for row in records:
        if row[0]==package:groups.setdefault(row[1],[]).append(row)
    versions=sorted(groups,key=lambda v:tuple(int(x) if x.isdigit() else x for x in re.split(r"([0-9]+)",v)))
    if len(versions)>4:versions=[*versions[:2],*versions[-2:]]
    for version in versions:
        rows=groups[version]
        # repoquery --show-duplicates order is recorded, not assumed to prove
        # historical release ordering; inspect both endpoint records.
        for row in (rows[0],rows[-1]):
            if row not in selected:selected.append(row)
if not selected or len(selected)>16:raise RuntimeError("SDK candidate bound/availability")
emit("selected-sdk-records",selected)
sdk=out/"sdk-rpms";sdk.mkdir()
for row in selected:
    request=row[0]+"-"+row[1]+"-"+row[2]+"."+row[3]
    command(["yumdownloader","--disablerepo=*","--enablerepo=amzn2-core","--destdir="+str(sdk),request])
for package in sorted(sdk.glob("*.rpm")):
    if not package.is_file() or package.is_symlink() or package.stat().st_size>16000000:raise RuntimeError("SDK RPM bound")
    sig=command(["rpm","--checksig","--verbose",str(package)])["output"]
    if not re.search(r"RSA.*[Ss]ignature.*key ID c87f5b1a: OK",sig,re.I) or re.search(r"(^|[^A-Za-z0-9_])(NOKEY|NOT OK|BAD|NOTTRUSTED)([^A-Za-z0-9_]|$)",sig,re.I):
        raise RuntimeError("Untrusted SDK RPM signature")
    identity=command(["rpm","-qp","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}",str(package)])["output"]
    files=command(["rpm","-qpl",str(package)])["output"].splitlines()
    headers={}
    for path in files:
        if not re.search(r"/(curl|curlver|pg_config|pg_config_ext|pg_config_manual)\.h$",path):continue
        if not path.startswith("/usr/include/") or ".." in Path(path).parts:raise RuntimeError("Unexpected header path")
        result=command(["bash","-o","pipefail","-c",'rpm2cpio "$1" | cpio -i --quiet --to-stdout "$2"',"_",str(package),"."+path])
        text=result["output"]
        if not text or len(text)>300000:raise RuntimeError("Missing/oversized header")
        if path.endswith("/curl.h") and "CURLINFO_LASTONE" not in text:raise RuntimeError("curl header extraction incomplete")
        target=out/(package.name+"-"+Path(path).name);target.write_text(text)
        lines=text.splitlines();contexts=[]
        for index,line in enumerate(lines):
            if re.search(r"CURLINFO_LASTONE|CURLVERSION_NOW|CURLVERSION_(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH)|CURL_MAX_READ_SIZE|LIBCURL_VERSION|PG_VERSION_STR|PG_VERSION_NUM",line):
                contexts.append({"line":index+1,"text":line})
        headers[path]={"sha256":hashlib.sha256(text.encode()).hexdigest(),"relevant_lines":contexts}
    emit("sdk-"+package.name,{"rpm_sha256":hashlib.sha256(package.read_bytes()).hexdigest(),"identity":identity,"signature":sig,"headers":headers})
print("DEPENDENCY_INVENTORY_DIAGNOSTIC_COMPLETE series="+series)
