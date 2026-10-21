#!/usr/bin/env python3
"""Inspect actual ELF bindings. Never accept ambiguous/unversioned mixed OpenSSL references."""
import hashlib,json,pathlib,re,subprocess,sys
cid,prefix=sys.argv[1:]
out=pathlib.Path("out")
def execute(*args):
    return subprocess.check_output(["docker","exec",cid,*args],text=True,timeout=120)
old=execute("rpm","-q","glibc","openssl-libs")
tools=subprocess.run(["docker","exec",cid,"yum","install","-y","binutils"],check=True,capture_output=True,text=True,timeout=180)
(out/"tls-inspection-tools.log").write_text(tools.stdout+tools.stderr)
objects={"cli":prefix+"/bin/php","fpm":prefix+"/sbin/php-fpm"}
linkage=execute("ldd",objects["cli"])
(out/"php82-tls-ldd.txt").write_text(linkage)
if "not found" in linkage: raise RuntimeError("Unresolved runtime library")
required={"curl":"libcurl.so.4","ssl11":"libssl.so.1.1","crypto11":"libcrypto.so.1.1","ssl10":"libssl.so.10","crypto10":"libcrypto.so.10"}
for key,name in required.items():
    matches=re.findall(r"^\s*"+re.escape(name)+r"\s+=>\s+(/\S+)\s+\(",linkage,re.M)
    if len(matches)!=1: raise RuntimeError("Missing/ambiguous actual link target: "+name)
    objects[key]=matches[0]
symbol_tables={}
def symbols(raw):
    result=[]
    for line in raw.splitlines():
        fields=line.split()
        if len(fields)<8 or not re.fullmatch(r"[0-9]+:",fields[0]): continue
        if fields[4] not in ("GLOBAL","WEAK") or fields[5] not in ("DEFAULT","PROTECTED"): continue
        name=fields[7]
        parts=re.split(r"@+",name,maxsplit=1)
        result.append((fields[6],parts[0],parts[1] if len(parts)>1 else None))
    return result
hashes={}
for key,path in objects.items():
    raw=execute("readelf","--dyn-syms","--wide",path)
    (out/("tls-"+key+"-dynsym.txt")).write_text(raw)
    symbol_tables[key]=symbols(raw)
    (out/("tls-"+key+"-versions.txt")).write_text(execute("readelf","--version-info",path))
    (out/("tls-"+key+"-dynamic.txt")).write_text(execute("readelf","--dynamic","--wide",path))
    digest=execute("sha256sum",path).split()[0]
    if not re.fullmatch("[0-9a-f]{64}",digest): raise RuntimeError("Bad object digest")
    hashes[key]={"path":path,"sha256":digest}
def exports(keys):
    return {(name,version) for key in keys for ndx,name,version in symbol_tables[key] if ndx!="UND"}
v11=exports(("ssl11","crypto11")); v10=exports(("ssl10","crypto10"))
openssl_names={name for name,_ in v11|v10}
counts={}
for key,wanted,other in [("cli",v11,v10),("fpm",v11,v10),("curl",v10,v11),("ssl11",v11,v10),("ssl10",v10,v11)]:
    refs=[(name,version) for ndx,name,version in symbol_tables[key] if ndx=="UND" and name in openssl_names]
    if not refs: raise RuntimeError("No OpenSSL references inspected: "+key)
    for name,version in refs:
        if version is None or (name,version) not in wanted or (name,version) in other:
            raise RuntimeError("Unsafe/ambiguous OpenSSL symbol binding: "+key+" "+name+"@"+str(version))
    counts[key]=len(refs)
after=execute("rpm","-q","glibc","openssl-libs")
if after!=old: raise RuntimeError("Inspection changed core runtime packages")
system=execute("sh","-c",'rpm -q openssl-libs; if [ -f /usr/bin/openssl ]; then sha256sum /usr/bin/openssl; else echo "openssl-command-absent"; fi')
if system!=(out/"system-openssl-before.txt").read_text():
    raise RuntimeError("System OpenSSL changed after inspection")
(out/"tls-system-openssl-after.txt").write_text(system)
record={"checks":"passed","objects":hashes,"versioned_openssl_reference_counts":counts,
    "binding":"PHP CLI/FPM to OpenSSL 1.1; libcurl to old OpenSSL; explicit disjoint symbol versions",
    "limits":["ELF linkage validation, not full ABI/TLS/application equivalence","no FIPS certification claim"]}
(out/"tls-linkage.json").write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(record))
