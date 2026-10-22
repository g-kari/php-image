#!/usr/bin/env python3
"""Inventory installed ELF providers and versions. No module code is executed here."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
series,destination=sys.argv[1:]
names=json.load(open("/work/al2-official/packages.json"))["main"][series]
paths=subprocess.check_output(["rpm","-ql",*names]).decode().splitlines()
items={}
for name in sorted(set(paths)):
    path=Path(name)
    if not path.is_file():continue
    with path.open("rb") as f:magic=f.read(4)
    if magic!=b"\x7fELF":continue
    symbols=subprocess.check_output(["readelf","--dyn-syms","--wide",name]).decode()
    dynamic=subprocess.check_output(["readelf","--dynamic","--wide",name]).decode()
    versions=subprocess.check_output(["readelf","--version-info","--wide",name]).decode()
    exports={}
    for line in symbols.splitlines():
        parts=line.split()
        if len(parts)<8 or parts[4] not in ("GLOBAL","WEAK") or parts[6]=="UND":continue
        symbol=parts[7].split("@")[0]
        if parts[3] in ("FUNC","OBJECT"):exports[symbol]={"kind":parts[3],"size":int(parts[2]) if parts[3]=="OBJECT" else None}
    links=[line.strip() for line in dynamic.splitlines() if any(x in line for x in ("(NEEDED)","(RPATH)","(RUNPATH)","(SONAME)"))]
    if any(("/home/builder" in line or "/work/" in line or "/tmp/" in line) for line in links):
        raise RuntimeError("Build-path runtime dependency: "+name)
    requirements=[];provider=None
    for line in versions.splitlines():
        match=re.search(r"File:\s+(\S+)",line)
        if match:provider=match.group(1)
        match=re.search(r"Name:\s+(\S+)",line)
        if match and provider:requirements.append([provider,match.group(1)])
    items[name]={"version_requirements":sorted(requirements),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"realpath":str(path.resolve()),
      "exports":exports,"dynamic_links":links,"symbol_versions":versions}
Path(destination).write_text(json.dumps(items,indent=2,sort_keys=True))
print("NATIVE_ELF_INVENTORY_RECORDED files="+str(len(items)))
