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
code=r"""$names=["CURLINFO_LASTONE","CURLVERSION_NOW","CURL_MAX_READ_SIZE","PGSQL_LIBPQ_VERSION_STR"];
$result=[];foreach($names as $name){if(defined($name)){$value=constant($name);$result[$name]=["type"=>gettype($value),"value"=>$value];}}
$all=get_defined_constants();foreach($all as $name=>$value){if(strpos($name,"apc_register_serializer")!==false){$result[$name]=["type"=>gettype($value),"value"=>$value];}}
$maps=@file("/proc/self/maps",FILE_IGNORE_NEW_LINES);if($maps!==false){$result["apcu_maps"]=array_values(array_filter($maps,function($line){return strpos($line,"/apcu.so")!==false;}));}
$curl=curl_version();$result["curl_runtime"]=["version"=>$curl["version"],"ssl_version"=>$curl["ssl_version"],"libz_version"=>$curl["libz_version"]];
echo json_encode($result,JSON_THROW_ON_ERROR);"""
observations=[json.loads(command(["php","-d","apc.enable_cli=1","-r",code])["output"]) for _ in range(2)]
emit("original-php-constants",observations)
if series=="7.4":
    offsets=[]
    for observed in observations:
        hook=observed.get("\x00apc_register_serializer-0")
        if not isinstance(hook,dict) or hook.get("type")!="integer" or type(hook.get("value")) is not int or hook["value"]<=0:
            raise RuntimeError("Exact APCu integer pointer observation missing")
        matches=[]
        for line in observed.get("apcu_maps",[]):
            match=re.fullmatch(r"([0-9a-f]+)-([0-9a-f]+) ([rwxps-]+) ([0-9a-f]+) ([0-9a-f]+):([0-9a-f]+)\s+([0-9]+)\s+(.+)",line)
            if match and int(match[1],16)<=hook["value"]<int(match[2],16):
                if match[3]!="r-xp" or match[8]!="/usr/lib64/php/modules/apcu.so":raise RuntimeError("Unexpected APCu pointer mapping")
                matches.append(int(match[4],16)+hook["value"]-int(match[1],16))
        if len(matches)!=1:raise RuntimeError("APCu executable mapping missing/ambiguous")
        offsets.append(matches[0])
    emit("apcu-fresh-process-offsets",offsets)
    if offsets[0]!=offsets[1]:raise RuntimeError("APCu offsets differ between fresh processes")
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
def package_inventory():
    return sorted(command(["rpm","-qa","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}\n"])["output"].splitlines())
def php_native_inventory():
    names=json.load(open("/work/al2-official/packages.json"))["main"][series]
    paths=command(["rpm","-ql",*names])["output"].splitlines()
    result={}
    for name in sorted(set(paths)):
        path=Path(name)
        if not path.is_file():continue
        with path.open("rb") as stream:
            if stream.read(4)!=b"\x7fELF":continue
        stat=path.stat()
        result[name]={"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"realpath":str(path.resolve()),
          "device":stat.st_dev,"inode":stat.st_ino,"size":stat.st_size,"mtime_ns":stat.st_mtime_ns,"ctime_ns":stat.st_ctime_ns}
    if len(result)<50:raise RuntimeError("PHP ELF inventory incomplete")
    return result
before=digest()
emit("system-files-before-ldconfig",before)
command(["/sbin/ldconfig"])
after=digest()
changed={name:{"before":before.get(name),"after":after.get(name)} for name in sorted(set(before)|set(after)) if before.get(name)!=after.get(name)}
emit("system-files-after-ldconfig-differences",changed)
for name in changed:emit("changed-owner-"+str(len(name))+"-"+hashlib.sha256(name.encode()).hexdigest()[:8],command(["rpm","-qf",name]))
# Reinstall only the exact already-verified, unchanged original main cohort.
# This changes inode/cache bookkeeping without introducing a custom binary.
originals=sorted(str(path) for path in Path("/out/vendor/main").glob("*.rpm"))
if len(originals)!={"7.4":28,"8.0":26,"8.1":26}[series]:raise RuntimeError("Original cohort inventory changed")
packages_before=package_inventory();native_before=php_native_inventory()
emit("reinstall-before-rpm-inventory",packages_before)
emit("reinstall-before-php-elf",native_before)
emit("original-cohort-reinstall",command(["yum","reinstall","-y",*originals],timeout=180))
packages_after=package_inventory();native_after=php_native_inventory()
emit("reinstall-after-rpm-inventory",packages_after)
emit("reinstall-php-elf-differences",{name:{"before":native_before.get(name),"after":native_after.get(name)} for name in sorted(set(native_before)|set(native_after)) if native_before.get(name)!=native_after.get(name)})
if packages_before!=packages_after:raise RuntimeError("Package identity changed during original-cohort reinstall")
if set(native_before)!=set(native_after) or any(native_before[name]["sha256"]!=native_after[name]["sha256"] or native_before[name]["realpath"]!=native_after[name]["realpath"] for name in native_before):
    raise RuntimeError("Native bytes/path changed during original-cohort reinstall")
reinstalled=digest()
changed_reinstall={name:{"before":after.get(name),"after":reinstalled.get(name)} for name in sorted(set(after)|set(reinstalled)) if after.get(name)!=reinstalled.get(name)}
emit("system-files-after-original-reinstall-differences",changed_reinstall)
for name in changed_reinstall:emit("reinstall-changed-owner-"+hashlib.sha256(name.encode()).hexdigest()[:8],command(["rpm","-qf",name]))
query=command(["repoquery","--disablerepo=*","--enablerepo=amzn2-core","--show-duplicates","--qf","%{name}|%{version}|%{release}|%{arch}","libcurl-devel","postgresql-devel"])
emit("available-sdk-nevras",query)
records=[]
for line in query["output"].splitlines():
    fields=line.split("|")
    if len(fields)==4 and fields[0] in ("libcurl-devel","postgresql-devel") and fields[3]=="x86_64":
        if any(not re.fullmatch(r"[A-Za-z0-9_.+~-]+",field) for field in fields):raise RuntimeError("Malformed SDK identity")
        records.append(fields)
emit("available-sdk-records",records)
if series!="7.4":
    reference=Path("/sdk-evidence")
    previous=json.load(open(reference/"available-sdk-records.json"))
    if sorted(records)!=sorted(previous):raise RuntimeError("Core SDK inventory changed between series")
    emit("reused-exact-signed-sdk-evidence",{"series":"7.4","same_core_sdk_records":True,"selected":json.load(open(reference/"selected-sdk-records.json"))})
    print("DEPENDENCY_INVENTORY_DIAGNOSTIC_COMPLETE series="+series)
    sys.exit(0)
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
    fields=identity.split("|")
    if len(fields)!=6 or [fields[0],fields[2],fields[3],fields[4]] not in selected:
        raise RuntimeError("Downloaded SDK identity differs from selected repository record")
    files=command(["rpm","-qpl",str(package)])["output"].splitlines()
    headers={}
    for path in files:
        if not re.search(r"/(curl|curlver|pg_config|pg_config_ext|pg_config_manual)\.h$",path):continue
        if not path.startswith("/usr/include/") or ".." in Path(path).parts:raise RuntimeError("Unexpected header path")
        result=subprocess.run(["bash","-o","pipefail","-c",'rpm2cpio "$1" | cpio -i --quiet --to-stdout "$2"',"_",str(package),"."+path],
          stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
        raw=result.stdout
        if result.returncode or result.stderr:raise RuntimeError("Header extraction failed: "+result.stderr.decode("utf-8","replace")[-4000:])
        if not raw or len(raw)>300000:raise RuntimeError("Missing/oversized header")
        text=raw.decode("utf-8","replace")
        if path.endswith("/curl.h") and "CURLINFO_LASTONE" not in text:raise RuntimeError("curl header extraction incomplete")
        target=out/(package.name+"-"+Path(path).name);target.write_bytes(raw)
        lines=text.splitlines();contexts=[]
        for index,line in enumerate(lines):
            if re.search(r"CURLINFO_LASTONE|CURLVERSION_NOW|CURLVERSION_(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH)|CURL_MAX_READ_SIZE|LIBCURL_VERSION|PG_VERSION_STR|PG_VERSION_NUM",line):
                contexts.append({"line":index+1,"text":line})
        headers[path]={"sha256":hashlib.sha256(raw).hexdigest(),"raw_size":len(raw),"relevant_lines":contexts}
    emit("sdk-"+package.name,{"rpm_sha256":hashlib.sha256(package.read_bytes()).hexdigest(),"identity":identity,"signature":sig,"headers":headers})
print("DEPENDENCY_INVENTORY_DIAGNOSTIC_COMPLETE series="+series)
