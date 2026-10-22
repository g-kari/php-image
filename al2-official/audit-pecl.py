#!/usr/bin/env python3
"""Vendor source/header/ELF evidence only: no compilation or source/module execution."""
import hashlib,json,re,subprocess,sys,tarfile
from pathlib import Path
series,destination=sys.argv[1:]
if not __debug__:raise RuntimeError("Optimized verification forbidden")
changed=("zend_safe_address_guarded","zend_safe_addmult","HT_HASH_RESET")
pattern=re.compile(r"\b(?:"+"|".join(changed)+r")\b")
extensions=json.load(open("/work/al2-official/packages.json"))["pecl"][series]
scratch=Path("/tmp/vendor-pecl-audit");scratch.mkdir(exist_ok=False)
report={"series":series,"sources":[],"headers":[],"binaries":[],"unresolved":[],
 "limits":["Direct token/include-closure inventory and offline dynamic symbols, not an exploit certificate.",
           "Generic zend_error_noreturn references do not identify an affected inline.",
           "Runtime module and serialization/cache checks are separate gates."]}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def collect(root,source=False):
    records=[];hits=[];includes=[]
    for path in sorted(root.rglob("*")):
        if path.is_symlink():raise RuntimeError("Unexpected source/header symlink: "+str(path))
        if not path.is_file() or path.suffix.lower() not in (".c",".h",".cc",".cpp",".re",".y",".inc"):continue
        rel=str(path.relative_to(root))
        if source and any(p.lower() in ("test","tests") for p in path.relative_to(root).parts[:-1]):continue
        if not source and path.name in ("zend_vm_execute.h","zend_vm_def.h","zend_vm_opcodes.h"):continue
        text=path.read_text(errors="replace")
        records.append({"path":rel,"sha256":sha(path)})
        for number,line in enumerate(text.splitlines(),1):
            if re.match(r"\s*#\s*include",line):includes.append({"path":rel,"line":number,"text":line})
            tokens=pattern.findall(line)
            for token in tokens:
                definition=(not source and path.name=="zend_multiply.h" and
                  re.search(r"static\s+zend_always_inline\s+size_t\s+"+token+r"\(",line))
                definition=definition or (not source and path.name=="zend_types.h" and
                  re.match(r"\s*#\s*define\s+HT_HASH_RESET\b",line))
                hits.append({"path":rel,"line":number,"token":token,"definition_only":bool(definition),"text":line})
                if not definition:report["unresolved"].append({"path":str(path),"line":number,"token":token})
            if source and re.search(r'#\s*include.*zend_vm_(execute|def|opcodes)\.h',line):
                report["unresolved"].append({"path":str(path),"line":number,"reason":"Generated VM implementation included"})
    return {"files":records,"changed_token_hits":hits,"includes":includes}
for item in extensions:
    rpm=Path("/out/vendor/sources")/(item["name"]+"-"+item["version"]+"-"+item["release"]+".src.rpm")
    if sha(rpm)!=item["sha256"]:raise RuntimeError("Vendor SRPM hash changed")
    root=scratch/item["name"];root.mkdir()
    payload=subprocess.check_output(["rpm2cpio",str(rpm)])
    listing=subprocess.run(["cpio","-it","--quiet"],input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout.decode().splitlines()
    if any(not re.fullmatch(r"[A-Za-z0-9_.+-]+",name) or name in (".","..") for name in listing):
        raise RuntimeError("Unexpected source RPM payload path")
    subprocess.run(["cpio","-id","--quiet","--no-absolute-filenames","--no-preserve-owner"],input=payload,cwd=str(root),check=True)
    specs=list(root.glob("*.spec"))
    if len(specs)!=1:raise RuntimeError("Ambiguous vendor spec")
    spec=specs[0].read_text()
    if re.search(r"(?m)^\s*Patch\d*\s*:",spec):raise RuntimeError("Vendor patches require explicit source audit")
    prep=spec.split("%prep",1)[1].split("%build",1)[0] if "%prep" in spec else ""
    reviewed=json.load(open("/work/al2-official/reviewed-pecl-prep.json"))["series"][series].get(rpm.name)
    if prep!=reviewed:raise RuntimeError("Vendor %prep differs from the exact reviewed non-C-source transformations")
    archives=list(root.glob("*.tgz"))
    if len(archives)!=1:raise RuntimeError("Ambiguous PECL source archive")
    extracted=root/"source";extracted.mkdir()
    with tarfile.open(str(archives[0]),"r:gz") as archive:
        members=archive.getmembers()
        if len(members)>10000 or sum(m.size for m in members)>134217728:raise RuntimeError("Unexpected source archive size")
        for member in members:
            path=Path(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError("Unsafe tar member")
        archive.extractall(str(extracted))
    result=collect(extracted,True)
    result.update({"name":item["name"],"srpm":rpm.name,"srpm_sha256":sha(rpm),
      "archive_sha256":sha(archives[0]),"spec_sha256":sha(specs[0]),
      "vendor_prep":spec.split("%prep",1)[1].split("%build",1)[0] if "%prep" in spec else ""})
    report["sources"].append(result)
    paths=subprocess.check_output(["rpm","-ql",item["name"]]).decode().splitlines()
    for name in paths:
        if not name.endswith(".so"):continue
        path=Path(name)
        dynamic=subprocess.check_output(["readelf","--dyn-syms","--wide",name]).decode()
        notable=[line for line in dynamic.splitlines() if re.search(r"\b(zend_mm_safe_error_ex|zend_new_array_singleton|zend_error_noreturn|_safe_emalloc|_safe_malloc)\b",line)]
        report["binaries"].append({"owner":item["name"],"path":name,"sha256":sha(path),"notable_symbols":notable})
for path in (Path("/usr/include/php"),Path("/usr/include/php-zts")):
    report["headers"].append({"root":str(path),"inventory":collect(path)})
report["status"]="blocked" if report["unresolved"] else "no_affected_vendor_callsite_identified"
Path(destination).write_text(json.dumps(report,indent=2,sort_keys=True))
if report["unresolved"]:raise RuntimeError("Unresolved PECL/header callsite; review required")
print("VENDOR_PECL_SOURCE_AUDIT_RECORDED packages="+str(len(extensions)))
