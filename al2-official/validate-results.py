#!/usr/bin/env python3
"""Verify observed vendor -> patched -> rollback results without converting PHPT FAIL to PASS."""
import json,sys
from feature_equivalence import canonical_payload
from pathlib import Path
series=sys.argv[1];root=Path("/out/qa")
if not __debug__:raise RuntimeError("Optimized verification forbidden")
def ensure(ok,why):
    if not ok:raise RuntimeError(why)
def read(phase,name):return json.loads((root/phase/name).read_text())
def differences(old,new,path=""):
    if old==new:return []
    if isinstance(old,dict) and isinstance(new,dict):
        result=[]
        for key in sorted(set(old)|set(new)):
            result+=differences(old.get(key,"<ABSENT>"),new.get(key,"<ABSENT>"),path+"/"+key)
            if len(result)>200:break
        return result
    if isinstance(old,list) and isinstance(new,list) and path.split("/")[-1] in ("modules","internal_function_names","resource_constant_names"):
        return [{"path":path,"removed":sorted(set(old)-set(new)),"added":sorted(set(new)-set(old))}]
    return [{"path":path,"before":old,"after":new}]
def equal_features(old,new,label):
    old,new=canonical_payload(old),canonical_payload(new)
    if old!=new:
        print("FEATURE_DIFFERENCES "+json.dumps({"context":label,"differences":differences(old,new)[:200]},sort_keys=True),flush=True)
        raise RuntimeError("SAPI/module/features differ: "+label)
phases=("vendor","patched","rollback")
for tool in ("php","zts-php","phpdbg","zts-phpdbg","php-cgi","embedded","apache-normal","apache-named-zts"):
    data={phase:read(phase,tool+".json") for phase in phases}
    reference=data["vendor"]
    for phase in phases[1:]:
        equal_features(reference,data[phase],phase+" "+tool)
    for file in ("abi-php-config.txt","abi-zts-php-config.txt","api-php-config.txt","api-zts-php-config.txt"):
        for phase in phases[1:]:
            ensure((root/"vendor"/file).read_bytes()==(root/phase/file).read_bytes(),"Header API/layout changed: "+file)
for phase in phases:
    data=read(phase,"fpm.json")
    ensure(data["fpm_runtime"]=="passed","FPM phase failed")
    if phase!="vendor":
        equal_features(read("vendor","fpm.json")["features"],data["features"],phase+" FPM")
    ensure((root/"vendor"/"core-dependencies.txt").read_bytes()==(root/phase/"core-dependencies.txt").read_bytes(),"System TLS/glibc/tzdata changed")
vendor=read("vendor","native.json");patched=read("patched","native.json");rollback=read("rollback","native.json")
ensure(set(vendor)==set(patched)==set(rollback),"Native payload path changed")
changes=[]
for path,old in vendor.items():
    new=patched[path]
    ensure(old==rollback[path],"Rollback native bytes/metadata differ: "+path)
    ensure(old["dynamic_links"]==new["dynamic_links"],"Native library dependency changed: "+path+" "+json.dumps([old["dynamic_links"],new["dynamic_links"]]))
    ensure(old["version_requirements"]==new["version_requirements"],"ELF symbol-version requirement changed: "+path+" "+json.dumps([old["version_requirements"],new["version_requirements"]]))
    before,after=old["exports"],new["exports"]
    ensure(not (set(before)-set(after)),"Public native symbol removed: "+path)
    core=(path.startswith(("/usr/bin/","/usr/sbin/","/usr/lib64/libphp","/usr/lib64/httpd/modules/libphp")))
    extra=set(after)-set(before)
    allowed={"zend_mm_safe_error_ex","zend_new_array_singleton"} if core else set()
    if series=="8.1" and path.endswith("/opcache.so"):
        allowed.update(["zend_accel_pending_ce_cache_begin","zend_accel_pending_ce_cache_commit","zend_accel_pending_ce_cache_discard"])
    ensure(extra<=allowed,"Unclassified new native exports: "+path+" "+",".join(sorted(extra)))
    if core:
        ensure({"zend_mm_safe_error_ex","zend_new_array_singleton"}<=set(after),"Patched core exports missing: "+path)
    for symbol in before:
        if before[symbol]!=after[symbol]:
            permitted=(series=="8.1" and path.endswith("/opcache.so") and symbol=="accel_globals"
              and before[symbol]["kind"]==after[symbol]["kind"]=="OBJECT"
              and after[symbol]["size"]==before[symbol]["size"]+8)
            ensure(permitted,"Unclassified exported object/API shape change: "+path+" "+symbol)
    changes.append({"path":path,"original_sha256":old["sha256"],"patched_sha256":new["sha256"],"new_exports":sorted(extra)})
a=read("vendor","date-and-defaults.json");b=read("patched","date-and-defaults.json");c=read("rollback","date-and-defaults.json")
ensure(a==c,"Rollback date/defaults differ")
for key in ("timezone","tehran","next_tuesday"):ensure(a[key]==b[key],"System timezone behavior changed")
if series=="7.4":ensure(a["default_multipart"] is False and str(b["default_multipart"])=="-1","7.4 multipart addition profile")
else:ensure(a["default_multipart"]==b["default_multipart"],"Existing multipart default changed")
for file in ("config-local.sha256","system-libraries.sha256","nonphp-rpms.txt","pecl-rpms.txt","pecl-modules.sha256","rpm-verify.txt"):
    for phase in ("patched","rollback"):
        ensure((root/"vendor"/file).read_bytes()==(root/phase/file).read_bytes(),"Cohort/config/system invariant failed: "+file+" "+phase)
result={"series":series,"architecture":"x86_64","status":"passed","native_comparison":changes,
 "gates":["Metadata/config/scriptlets and dependency comparison","Real NTS/named-ZTS CLI/CGI/phpdbg/FPM functions",
 "Vendor update and original-cohort rollback with modified configs retained","ELF providers/versions/API/layout",
 "Module/PECL functions, cache/serialization, upload/progress, session reuse, OOM exit/recovery"],
 "limits":["Packaged systemd unit activation and real applications are not tested.",
 "Apache uses a private prefork configuration, not production handler/default MPM activation.",
 "Official PHP mitigation is not renewed EOL/AL2 support or an all-extension CVE certificate.",
 "Rebuilt RPMs are not Amazon-signed; build environment and bytes differ."]}
(root/"FINAL-RESULT.json").write_text(json.dumps(result,indent=2,sort_keys=True))
print("OFFICIAL_AL2_RUNTIME_GATES_PASSED series="+series)
