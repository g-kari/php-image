#!/usr/bin/env python3
"""Preserve package metadata and upstream legal texts without relicensing the payload."""
import hashlib,io,json,re,subprocess,sys,tarfile
from pathlib import Path
series=sys.argv[1];root=Path("/out");dest=root/"license-evidence";dest.mkdir()
def digest(data):return hashlib.sha256(data).hexdigest()
records=[]
for directory in ("vendor/main","vendor/pecl","rpms"):
    for rpm in sorted((root/directory).glob("*.rpm")):
        metadata=subprocess.check_output(["rpm","-qp","--qf","%{NAME}|%{VERSION}|%{RELEASE}|%{ARCH}|%{LICENSE}",str(rpm)]).decode()
        flags=subprocess.check_output(["rpm","-qp","--qf","[%{FILENAMES}|%{FILEFLAGS}|%{FILEDIGESTS}\n]",str(rpm)]).decode().splitlines()
        notices=[line for line in flags if re.search(r"(?i)(license|copying|copyright|notice|/doc/|/licenses/)",line)]
        records.append({"file":str(rpm.relative_to(root)),"sha256":digest(rpm.read_bytes()),"vendor_license_metadata":metadata,"legal_payload_inventory":notices})
texts=[]
with tarfile.open(root/"prepared-source.tar.gz","r:gz") as archive:
    for member in archive.getmembers():
        if not member.isfile():continue
        p=Path(member.name)
        name=p.name.lower()
        selected=(re.search(r"^(license|copying|copyright|notice)([._-]|$)",name) is not None
           or name=="readme.redist.bins" or name.endswith("_license") or str(p).endswith(("main/spprintf.c","main/snprintf.c","main/rfc1867.c")))
        if not selected:continue
        if p.is_absolute() or ".." in p.parts:raise RuntimeError("Unsafe legal-source path")
        data=archive.extractfile(member).read()
        target=dest/"upstream-source"/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        texts.append({"source_path":member.name,"sha256":digest(data),"size":len(data)})
required=("LICENSE","Zend/LICENSE","TSRM/LICENSE","sapi/fpm/LICENSE",
          "ext/bcmath/libbcmath/LICENSE","ext/mbstring/libmbfl/LICENSE","ext/date/lib/LICENSE.rst","ext/fileinfo/libmagic/LICENSE")
for name in required:
    if not any(t["source_path"].endswith("/"+name) for t in texts):raise RuntimeError("Upstream legal text missing: "+name)
# Confirm source material is actually in the rebuilt complete SRPM, not merely linked.
source_rpms=list(root.glob("php-*.src.rpm"))
if len(source_rpms)!=1:raise RuntimeError("Rebuilt complete SRPM absent")
originals=list(root.glob("original-php-*.src.rpm"))
if len(originals)!=1:raise RuntimeError("Original SRPM absent")
def srpm_files(path):
    return set(subprocess.check_output(["rpm","-qpl",str(path)]).decode().splitlines())
sdk=json.load(open("/work/al2-official/build-sdk-lock.json"))["series"][series]
sdk_extras={"build-sdk.py","build-sdk-lock.json",*(item["file"] for item in sdk)} if sdk else set()
if srpm_files(source_rpms[0])!=srpm_files(originals[0])|{"php-upstream-cve2026.patch"}|sdk_extras:
    raise RuntimeError("Source RPM original material/patch set changed")
# Preserve authenticated SDK RPM inputs with their existing header/legal payload and source identities.
sdk_inputs=[]
if sdk:
    import runpy
    archive_members=runpy.run_path("/work/al2-official/build-sdk.py")["members"]
    srpm_data={name:data for name,mode,nlink,data in archive_members(subprocess.check_output(["rpm2cpio",str(source_rpms[0])]))}
    sdkdest=dest/"build-sdk-inputs";sdkdest.mkdir()
    for item in sdk:
        data=srpm_data.get(item["file"])
        if data is None or digest(data)!=item["sha256"]:raise RuntimeError("SRPM SDK source input changed")
        target=sdkdest/item["file"];target.write_bytes(data)
        actual=subprocess.check_output(["rpm","-qp","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}|%{SOURCERPM}|%{LICENSE}",str(target)]).decode()
        if actual!=item["identity"]:raise RuntimeError("SRPM SDK legal/source metadata changed")
        sdk_inputs.append({"file":item["file"],"sha256":item["sha256"],"identity_and_license":actual,
          "source_obtaining":"Use the named AWS source RPM from amzn2-core-source; these build-only headers are not installed as runtime packages.",
          "delivery":"The exact original SDK RPM with its headers/notices is embedded in the complete SRPM and this companion bundle."})
# Vendor notice names are copied during prep; validate actual installed baseline bytes against prepared source.
required_payload={"php-common":{"LICENSE":"LICENSE","TSRM_LICENSE":"TSRM/LICENSE",
 "libmagic_LICENSE":"ext/fileinfo/libmagic/LICENSE","timelib_LICENSE":"ext/date/lib/LICENSE.rst",
 "README.REDIST.BINS":"README.REDIST.BINS"},"php-fpm":{"fpm_LICENSE":"sapi/fpm/LICENSE"},
 "php-mbstring":{"libmbfl_LICENSE":"ext/mbstring/libmbfl/LICENSE"}}
payload_status=[]
for package,mapping in required_payload.items():
    paths=subprocess.check_output(["rpm","-ql",package]).decode().splitlines()
    for installed_name,source_name in mapping.items():
        matches=[Path(p) for p in paths if Path(p).name==installed_name and Path(p).is_file()]
        if len(matches)!=1:raise RuntimeError("Actual packaged notice absent/ambiguous: "+package+" "+installed_name)
        source_matches=[r for r in texts if r["source_path"].endswith("/"+source_name)
            and (source_name!="LICENSE" or len(Path(r["source_path"]).parts)==2)]
        if len(source_matches)!=1:raise RuntimeError("Prepared legal source absent/ambiguous: "+source_name)
        actual=digest(matches[0].read_bytes())
        if actual!=source_matches[0]["sha256"]:raise RuntimeError("Packaged notice differs from prepared source")
        # Rebuilt metadata comparison enforces all path/digest identities, and exact notice digest here also binds the new RPM header.
        rebuilt=[r for r in records if r["file"].startswith("rpms/") and r["vendor_license_metadata"].split("|")[0]==package]
        if len(rebuilt)!=1 or not any(line.startswith(str(matches[0])+"|") and line.endswith("|"+actual) for line in rebuilt[0]["legal_payload_inventory"]):
            raise RuntimeError("Rebuilt notice bytes not bound to the source")
        payload_status.append({"package":package,"path":str(matches[0]),"sha256":actual,"status":"source_and_vendor_and_rebuild_match"})
report={"build_only_sdk_inputs":sdk_inputs,"actual_notice_payload_checks":payload_status,"series":series,"rpm_metadata_and_legal_files":records,"preserved_source_legal_files":texts,
 "source_delivery":"The rebuilt complete SRPM, original vendor spec, modified spec and exact security patch accompany the binary set.",
 "scope":"Repository MIT covers original scripts only. Original PHP/Zend and bundled/PECL/OS notices remain applicable.",
 "limits":["RPM License strings are preserved vendor metadata, not an exhaustive legal conclusion.",
 "External runtime dependencies are identified by SBOM/RPM and ELF inventories; their own packages/sources carry separate terms.",
 "No Amazon/PHP endorsement, AWS signature, legal warranty or extended maintenance is provided."]}
(dest/"LICENSE-INVENTORY.json").write_text(json.dumps(report,indent=2,sort_keys=True))
print("ARTIFACT_LICENSE_SOURCE_INVENTORY_RECORDED packages="+str(len(records))+" texts="+str(len(texts)))
