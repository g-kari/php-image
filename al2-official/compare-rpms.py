#!/usr/bin/env python3
"""Fail-closed official/rebuild RPM metadata and payload-map comparison. Does not install."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
if not __debug__: raise RuntimeError("Optimized verification forbidden")
before,after,series,report=map(str,sys.argv[1:])
suffix=".cve2026_109618_109619.1"
def rpm(path,*args):
    return subprocess.check_output(["rpm","-qp",*args,str(path)],stderr=subprocess.PIPE).decode()
def collect(root):
    result={}
    for path in sorted(Path(root).glob("*.rpm")):
        meta=rpm(path,"--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}").split("|")
        name=meta[0]
        if name in result: raise RuntimeError("Duplicate package "+name)
        fields={"license":rpm(path,"--qf","%{LICENSE}")}
        for option in ["--provides","--requires","--conflicts","--obsoletes","--scripts","--triggers"]:
            fields[option]=rpm(path,option)
        raw=rpm(path,"--qf","[%{FILENAMES}\t%{FILEMODES}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\t%{FILEFLAGS}\t%{FILELINKTOS}\t%{FILEDIGESTS}\n]")
        payload={}
        for line in raw.splitlines():
            item=line.split("\t")
            if len(item)!=7 or not item[0].startswith("/") or ".." in Path(item[0]).parts:
                raise RuntimeError("Unrecognized payload map")
            if item[0] in payload: raise RuntimeError("Duplicate payload path")
            payload[item[0]]=item[1:]
        result[name]={"path":path.name,"identity":meta,"fields":fields,"payload":payload,
                      "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    return result
a,b=collect(before),collect(after)
main={"php","php-cli","php-dbg","php-fpm","php-common","php-devel","php-opcache","php-ldap",
      "php-pdo","php-mysqlnd","php-pgsql","php-process","php-odbc","php-soap","php-snmp",
      "php-xml","php-mbstring","php-gd","php-bcmath","php-gmp","php-dba","php-embedded",
      "php-pspell","php-intl","php-enchant","php-sodium"}
if series=="7.4":main.update(["php-json","php-xmlrpc"])
if set(a)!=main or set(b)-{"php-debuginfo","php-debugsource"}!=main:
    raise RuntimeError("Main-source package split differs from the official baseline")
differences=[];changed=[]
for name in sorted(main):
    old,new=a[name],b[name]; x,y=old["identity"],new["identity"]
    if x[:3]!=y[:3] or x[4]!=y[4] or y[3]!=x[3]+suffix or x[4]!="x86_64":
        raise RuntimeError("Unexpected package identity "+name)
    if y[5]!=x[5].replace(".src.rpm",suffix+".src.rpm"):
        raise RuntimeError("Unbound source RPM "+name)
    for field in old["fields"]:
        oldtext=old["fields"][field]
        newtext=new["fields"][field].replace(y[3],x[3])
        if oldtext!=newtext:
            differences.append({"package":name,"field":field,"old":oldtext,"new":newtext})
    if set(old["payload"])!=set(new["payload"]):
        differences.append({"package":name,"field":"payload_paths",
          "removed":sorted(set(old["payload"])-set(new["payload"])),
          "added":sorted(set(new["payload"])-set(old["payload"]))})
        continue
    for path,olditem in old["payload"].items():
        newitem=new["payload"][path]
        if olditem[:-1]!=newitem[:-1]:
            differences.append({"package":name,"field":"file_attributes","path":path,"old":olditem,"new":newitem})
        if olditem[-1]!=newitem[-1]:
            changed.append({"package":name,"path":path,"old_digest":olditem[-1],"new_digest":newitem[-1]})
            # Config, unit, tmpfiles, helper activation and log rotation bytes must be unchanged.
            if (int(olditem[3])&1 or path.startswith(("/etc/","/usr/lib/systemd/","/usr/lib/tmpfiles.d/"))):
                differences.append({"package":name,"field":"configuration_bytes","path":path})
result={"schema":1,"series":series,"status":"passed" if not differences else "blocked",
        "main_package_names":sorted(main),"separate_debug_packages":sorted(set(b)-main),
        "before":a,"after":b,"nonmetadata_payload_changes":changed,"unapproved_differences":differences,
        "limitations":["Native bytes and installed header edits are inventoried, not claimed identical.",
          "Compiler/dependency snapshot, build metadata and signatures differ from AWS.",
          "Separate runtime/ELF/upgrade/rollback gates are required."]}
Path(report).write_text(json.dumps(result,indent=2,sort_keys=True))
if differences:raise RuntimeError("Unreviewed metadata/configuration differences; inspect "+report)
print("OFFICIAL_RPM_METADATA_COMPARISON_PASSED packages="+str(len(main)))
