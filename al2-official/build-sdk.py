#!/usr/bin/env python3
"""Authenticate build-only AWS SDK headers. Never install an old SDK/runtime library."""
import hashlib,json,os,re,stat,subprocess,sys,time,selectors,urllib.request,urllib.parse
from pathlib import Path
MAX_ARCHIVE=64000000
def require(ok,why):
    if not ok:raise RuntimeError("Build SDK: "+why)
def run(argv,limit=1000000):
    p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    require(p.returncode==0 and not p.stderr,"command failed/stderr: "+repr(argv)+" "+p.stderr.decode("utf-8","replace")[-1500:])
    require(len(p.stdout)<=limit,"command output bound")
    return p.stdout
def bounded(argv,limit,timeout=60):
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    selector=selectors.DefaultSelector();output={"stdout":bytearray(),"stderr":bytearray()}
    for stream,name in ((process.stdout,"stdout"),(process.stderr,"stderr")):
        os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
    deadline=time.monotonic()+timeout
    try:
        while selector.get_map():
            remaining=deadline-time.monotonic()
            require(remaining>0,"payload command timeout")
            events=selector.select(remaining)
            require(events,"payload command timeout")
            for key,_ in events:
                chunk=os.read(key.fileobj.fileno(),65536)
                if not chunk:selector.unregister(key.fileobj);continue
                output[key.data]+=chunk
                require(len(output[key.data])<=(limit if key.data=="stdout" else 100000),"payload output bound")
        rc=process.wait(timeout=max(0.01,deadline-time.monotonic()))
        require(rc==0 and not output["stderr"],"payload command status/stderr")
        return bytes(output["stdout"])
    finally:
        selector.close()
        if process.poll() is None:process.kill()
        process.wait();process.stdout.close();process.stderr.close()
def members(raw):
    require(len(raw)<=MAX_ARCHIVE,"archive bound")
    pos=0;seen=set();result=[]
    while True:
        require(pos+110<=len(raw) and raw[pos:pos+6]==b"070701","newc header")
        head=raw[pos+6:pos+110];require(re.fullmatch(b"[0-9a-fA-F]{104}",head) is not None,"newc fields")
        values=[int(head[i:i+8],16) for i in range(0,104,8)]
        ino,mode,uid,gid,nlink,mtime,size,devmajor,devminor,rdevmajor,rdevminor,namesize,check=values
        require(1<namesize<=1000 and size<=16000000 and check==0,"member bounds/check")
        pos+=110;end=pos+namesize
        require(end<=len(raw) and raw[end-1]==0,"member name")
        name=raw[pos:end-1].decode("ascii");aligned=(end+3)&~3
        require(aligned<=len(raw) and not any(raw[end:aligned]),"name padding")
        pos=aligned
        require(pos+size<=len(raw),"member payload")
        data=raw[pos:pos+size];end=pos+size;aligned=(end+3)&~3
        require(aligned<=len(raw) and not any(raw[end:aligned]),"data padding")
        pos=aligned
        if name=="TRAILER!!!":
            require(size==0 and not any(raw[pos:]),"archive trailer/padding");break
        if name.startswith("./"):name=name[2:]
        require(name and not name.startswith("/") and all(part not in ("",".","..") for part in name.split("/")),"unsafe member path")
        require(name not in seen,"duplicate normalized member")
        seen.add(name);result.append((name,mode,nlink,data))
        require(len(result)<=30000,"member inventory bound")
    return result
def selected(name,kind):
    if not name.startswith("usr/include/") or not name.endswith(".h"):return False
    part=name[len("usr/include/"):]
    if kind=="libcurl-devel":return part.startswith("curl/")
    if kind=="postgresql-devel":return not part.startswith("pgsql/server/")
    raise RuntimeError("Unknown SDK kind")
def stage(source,lockfile,series,dest):
    lock=json.load(open(lockfile));items=lock["series"][series]
    require(not dest.exists(),"private SDK destination already exists")
    dest.mkdir(mode=0o700);include=dest/"include";include.mkdir()
    output=[]
    for item in items:
        rpm=source/item["file"]
        require(rpm.is_file() and not rpm.is_symlink() and rpm.stat().st_size<=16000000,"RPM input")
        require(hashlib.sha256(rpm.read_bytes()).hexdigest()==item["sha256"],"RPM SHA256")
        signature=run(["rpm","--checksig","--verbose",str(rpm)]).decode()
        require(re.search(r"RSA.*[Ss]ignature.*key ID c87f5b1a: OK",signature,re.I) is not None and re.search(r"(^|[^A-Za-z0-9_])(NOKEY|NOT OK|BAD|NOTTRUSTED)([^A-Za-z0-9_]|$)",signature,re.I) is None,"AWS signature")
        identity=run(["rpm","-qp","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}|%{LICENSE}",str(rpm)]).decode()
        require(identity==item["identity"],"exact RPM identity")
        kind=identity.split("|")[0]
        raw=bounded(["rpm2cpio",str(rpm)],MAX_ARCHIVE)
        copied={}
        for name,mode,nlink,data in members(raw):
            if not selected(name,kind):continue
            require(stat.S_ISREG(mode) and nlink==1 and 0<len(data)<=1000000,"selected header must be unique regular nonempty file")
            relative=name[len("usr/include/"):]
            require(kind!="postgresql-devel" or not relative.startswith(("openssl/","curl/")),"unrelated SDK namespace")
            target=include/relative
            require(not target.exists(),"overlapping SDK header")
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as handle:handle.write(data)
            copied["/"+name]={"size":len(data),"sha256":hashlib.sha256(data).hexdigest()}
        require(3<=len(copied)<=1000,"header inventory")
        for path,expected in item["headers"].items():require(copied.get(path)==expected,"pinned header bytes "+path)
        required=["/usr/include/curl/curl.h","/usr/include/curl/curlver.h","/usr/include/curl/system.h"] if kind=="libcurl-devel" else ["/usr/include/libpq-fe.h","/usr/include/postgres_ext.h","/usr/include/libpq/libpq-fs.h","/usr/include/pg_config.h","/usr/include/pg_config_x86_64.h"]
        require(set(required)<=set(copied),"client header closure")
        output.append({"rpm":item["file"],"sha256":item["sha256"],"identity":identity,"signature":signature,"headers":copied})
    (dest/"manifest.json").write_text(json.dumps({"series":series,"packages":output},sort_keys=True,indent=2))
    print("AUTHENTICATED_BUILD_HEADER_SDK_STAGED series="+series+" packages="+str(len(output)))
def unit_recipe(command,index,pic_flags="-fPIC -DPIC"):
    prefix="$(LIBTOOL) --mode=compile "
    require(command.startswith("\t"+prefix+"$(CC) "),"unknown actual client compiler wrapper")
    raw=command[1+len(prefix):]
    require(raw.count("-prefer-pic")<=1 and "-prefer-non-pic" not in raw,"unsupported libtool PIC mode")
    raw=raw.replace("-prefer-pic",pic_flags)
    require(not any(token in raw for token in (";","&&","||",chr(96),"\n","--sysroot","-isysroot","-nostdinc")),"unexpected client compiler search/shell override")
    match=re.fullmatch(r"(.+) -c (/[A-Za-z0-9_./+-]+\.c) -o ([A-Za-z0-9_./+-]+\.lo)",raw)
    require(match is not None,"unknown actual client compile recipe")
    stem="sdk-unit-"+str(index)
    transformed=match[1]+" -E -H -dM "+match[2]+" > "+stem+"-macros.txt 2> "+stem+"-headers.txt"
    return stem,transformed,match[2]
def probe(dest,build):
    manifest=json.load(open(dest/"manifest.json"));items=manifest["packages"]
    if not items:return
    include=(dest/"include").resolve()
    require(os.environ.get("C_INCLUDE_PATH")==str(include),"exact private include environment")
    for name in ("CPATH","CPLUS_INCLUDE_PATH","OBJC_INCLUDE_PATH"):require(not os.environ.get(name),"unexpected include environment "+name)
    headers=["curl/curl.h","openssl/ssl.h"]
    if any(x["identity"].startswith("postgresql-devel|") for x in items):headers+=["libpq-fe.h","libpq/libpq-fs.h","pg_config.h"]
    (dest/"probe.c").write_text("".join("#include <"+h+">\n" for h in headers))
    makefile=dest/"probe.mk"
    makefile.write_text(".PHONY: sdk-header-probe\nsdk-header-probe:\n\t$(CC) $(COMMON_FLAGS) $(CFLAGS_CLEAN) $(EXTRA_CFLAGS) -E -H -dM "+str(dest/"probe.c")+" > sdk-macros.txt 2> sdk-headers.txt\n")
    run(["make","--no-print-directory","-f","Makefile","-f",str(makefile),"sdk-header-probe"])
    trace=(build/"sdk-headers.txt").read_text()
    macros=(build/"sdk-macros.txt").read_text()
    all_paths=[]
    for line in trace.splitlines():
        m=re.match(r"^\.+ (/.+)$",line)
        if m:all_paths.append(Path(m[1]))
    require(all_paths,"compiler include trace missing")
    # Complete copied inventory, not only the small pinned subset.
    inventory_all={path[len("/usr/include/"):]:record for item in items for path,record in item["headers"].items()}
    seen=set()
    for path in all_paths:
        resolved=path.resolve()
        if include in resolved.parents:
            relative=str(resolved.relative_to(include))
            require(relative in inventory_all,"unmanifested private header")
            require(hashlib.sha256(resolved.read_bytes()).hexdigest()==inventory_all[relative]["sha256"],"compiler used changed SDK header")
            seen.add(relative)
        elif "/curl/" in str(path) or str(path).endswith(("/libpq-fe.h","/libpq-fs.h","/postgres_ext.h","/pg_config.h","/pg_config_x86_64.h","/pg_config_ext.h")):
            raise RuntimeError("Build SDK: compiler mixed system client header "+str(path))
        if "/openssl/" in str(path):require(str(resolved).startswith("/usr/include/openssl/"),"OpenSSL SDK changed")
    require({"curl/curl.h","curl/curlver.h","curl/system.h"}<=seen,"curl header trace incomplete")
    if len(headers)>2:require({"libpq-fe.h","libpq/libpq-fs.h","postgres_ext.h","pg_config.h","pg_config_x86_64.h"}<=seen,"PostgreSQL header trace incomplete")
    require(any(str(p.resolve())=="/usr/include/openssl/ssl.h" for p in all_paths),"original OpenSSL header not observed")
    rules=(build/"Makefile.objects").read_text()
    relevant=[line for line in rules.splitlines() if line.startswith("\t") and re.search(r"/ext/(curl|pgsql|pdo_pgsql)/",line)]
    require(relevant or build.name not in ("build-cgi","build-ztscli"),"actual client compile rules missing")
    (build/"sdk-extension-compile-rules.txt").write_text("\n".join(relevant)+"\n")
    # Reuse each actual object recipe's exact flags/order/source, removing only libtool and -c/-o.
    # This includes source/build -I and extension-specific flags absent from COMMON_FLAGS.
    unit_probes=[]
    config=run(["/bin/sh",str(build/"libtool"),"--config"]).decode()
    pic=re.findall(r"(?m)^pic_flag=['\"]([^'\"]*)['\"]$",config)
    require(len(pic)==1 and re.fullmatch(r"\s*-fPIC(?:\s+-DPIC)?\s*",pic[0]) is not None,"unknown actual libtool PIC expansion")
    for index,command in enumerate(relevant):
        stem,recipe,source=unit_recipe(command,index,pic[0])
        unit_probes.append({"stem":stem,"recipe":recipe,"source":source})
    if unit_probes:
        mk=dest/"unit-probes.mk"
        mk.write_text(".PHONY: sdk-actual-units\nsdk-actual-units:\n"+"".join("\t"+item["recipe"]+"\n" for item in unit_probes))
        run(["make","--no-print-directory","-f","Makefile","-f",str(mk),"sdk-actual-units"])
    all_copied={relative for relative in inventory_all}
    client_basenames={Path(relative).name for relative in all_copied}
    for item in unit_probes:
        trace_path=build/(item["stem"]+"-headers.txt")
        unit_trace=trace_path.read_text()
        seen_unit=set()
        for line in unit_trace.splitlines():
            match=re.match(r"^\.+ (/.+)$",line)
            if not match:continue
            actual=Path(match[1]).resolve()
            if include in actual.parents:
                relative=str(actual.relative_to(include))
                require(relative in inventory_all and hashlib.sha256(actual.read_bytes()).hexdigest()==inventory_all[relative]["sha256"],"actual unit SDK bytes changed")
                seen_unit.add(relative)
            elif actual.name in client_basenames and ("/curl/" in str(actual) or manifest["series"]=="7.4"):
                raise RuntimeError("Build SDK: actual client unit mixed system header "+str(actual))
            if "/openssl/" in str(actual) and "/ext/openssl/" not in str(actual):
                require(str(actual).startswith("/usr/include/openssl/"),"actual unit OpenSSL header changed")
        if "/ext/curl/" in item["source"]:
            require({"curl/curl.h","curl/curlver.h","curl/system.h"}<=seen_unit,"actual curl unit missing SDK closure")
        elif manifest["series"]=="7.4":
            require({"libpq-fe.h","postgres_ext.h"}<=seen_unit,"actual PostgreSQL unit missing SDK closure")
        item["actual_sdk_headers"]=sorted(seen_unit)
        item["trace_sha256"]=hashlib.sha256(trace_path.read_bytes()).hexdigest()
    (build/"sdk-actual-unit-probes.json").write_text(json.dumps(unit_probes,sort_keys=True,indent=2))
    expected="7.79.1" if manifest["series"]=="7.4" else "7.88.1"
    require('#define LIBCURL_VERSION "'+expected+'"' in macros,"compiler curl version")
    (build/"sdk-probe-result.json").write_text(json.dumps({"status":"passed","series":manifest["series"],"sdk_headers":sorted(seen),"compiler_trace":trace,"macro_sha256":hashlib.sha256(macros.encode()).hexdigest()},indent=2))
    print("ACTUAL_MAKE_COMPILER_HEADER_PROBE_PASSED tree="+build.name)
def download(lockfile,series,destination):
    root=Path(destination);root.mkdir(parents=True,exist_ok=True)
    for item in json.load(open(lockfile))["series"][series]:
        url=urllib.parse.urlsplit(item["url"])
        require(url.scheme=="https" and url.hostname=="cdn.amazonlinux.com" and not url.query and not url.fragment and url.path=="/blobstore/"+item["sha256"]+"/"+item["file"],"SDK URL pin")
        target=root/item["file"]
        require(not target.exists(),"SDK download destination exists")
        with urllib.request.urlopen(item["url"],timeout=60) as response:
            require(response.geturl()==item["url"],"SDK redirect")
            raw=response.read(16000001)
        require(len(raw)<=16000000 and hashlib.sha256(raw).hexdigest()==item["sha256"],"download SHA/size")
        with target.open("xb") as handle:handle.write(raw)
        print("PINNED_SDK_RPM_DOWNLOADED "+item["file"]+" sha256="+item["sha256"])
if __name__=="__main__":
    require(__debug__,"optimized verification forbidden")
    mode=sys.argv[1]
    if mode=="stage":stage(Path(sys.argv[2]),sys.argv[3],sys.argv[4],Path(sys.argv[5]))
    elif mode=="probe":probe(Path(sys.argv[2]).resolve(),Path.cwd())
    elif mode=="download":download(sys.argv[2],sys.argv[3],sys.argv[4])
    else:raise RuntimeError("Unknown build SDK mode")
