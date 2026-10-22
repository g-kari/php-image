#!/usr/bin/env python3
import hashlib,json,os,re,stat,subprocess,sys
from aux_cache import PATH as AUX_PATH,parse_aux
from pathlib import Path
series,phase=sys.argv[1:];out=Path("/out/qa")/phase;out.mkdir(exist_ok=True)
def digest(paths):
    lines=[]
    for name in sorted(set(paths)):
        p=Path(name)
        if p.is_file():lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+name)
    return "\n".join(lines)+"\n"
configs=json.load(open("/out/qa/local-config-fixtures.json"))
(out/"config-local.sha256").write_text(digest(configs))
paths=subprocess.check_output(["rpm","-ql","glibc","openssl-libs"]).decode().splitlines()+["/usr/bin/openssl"]
if paths.count(AUX_PATH)!=1:raise RuntimeError("Exact glibc auxiliary cache owner path missing/ambiguous")
aux=Path(AUX_PATH)
if aux.is_symlink() or not aux.is_file():raise RuntimeError("Auxiliary cache must be a regular non-symlink")
with aux.open("rb") as handle:
    before=os.fstat(handle.fileno());raw=handle.read(16000001);after=os.fstat(handle.fileno())
if any(getattr(before,key)!=getattr(after,key) for key in ("st_dev","st_ino","st_mode","st_size","st_mtime_ns","st_ctime_ns")) or not stat.S_ISREG(before.st_mode):raise RuntimeError("Auxiliary cache changed during observation")
owner=subprocess.check_output(["rpm","-qf","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}",AUX_PATH]).decode()
glibc=subprocess.check_output(["rpm","-q","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}","glibc"]).decode()
if owner!=glibc or not owner.startswith("glibc|0|2.26|"):raise RuntimeError("Unexpected auxiliary cache owner")
record={"path":AUX_PATH,"realpath":str(aux.resolve()),"owner":owner,"sha256":hashlib.sha256(raw).hexdigest(),
 "stat":{"dev":before.st_dev,"ino":before.st_ino,"mode":before.st_mode,"size":before.st_size,"mtime_ns":before.st_mtime_ns,"ctime_ns":before.st_ctime_ns},
 "parsed":parse_aux(raw)}
if record["realpath"]!=AUX_PATH:raise RuntimeError("Auxiliary cache path redirect")
(out/"generated-aux-cache.bin").write_bytes(raw)
(out/"generated-aux-cache.json").write_text(json.dumps(record,sort_keys=True,indent=2))
# Only this proven generated cache is separated; loader cache and every other owned file stay byte-immutable.
(out/"system-libraries.sha256").write_text(digest(p for p in paths if p!=AUX_PATH))
packages=subprocess.check_output(["rpm","-qa","--qf","%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}|%{ARCH}\n"]).decode().splitlines()
(out/"nonphp-rpms.txt").write_text("\n".join(sorted(p for p in packages if not p.startswith("php")))+"\n")
(out/"pecl-rpms.txt").write_text("\n".join(sorted(p for p in packages if p.startswith("php-pecl-")))+"\n")
pecl=json.load(open("/work/al2-official/packages.json"))["pecl"][series]
modulepaths=[]
for item in pecl:
    modulepaths+=subprocess.check_output(["rpm","-ql",item["name"]]).decode().splitlines()
(out/"pecl-modules.sha256").write_text(digest(p for p in modulepaths if p.endswith(".so")))
names=json.load(open("/work/al2-official/packages.json"))["main"][series]
result=subprocess.run(["rpm","-V",*names],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
(out/"rpm-verify.txt").write_bytes(result.stdout)
(out/"rpm-verify-command.json").write_text(json.dumps({"returncode":result.returncode,"stdout":result.stdout.decode(),"stderr":result.stderr.decode()},indent=2))
if result.stderr:raise RuntimeError("Unexpected RPM verification error: "+result.stderr.decode())
lines=result.stdout.decode().splitlines()
observed=[]
for line in lines:
    match=re.fullmatch(r"([.SM5DLUGTP?]{9})\s+c\s+(.+)",line)
    if not match or match.group(2) not in configs or not set(match.group(1))<=set(".S5T"):
        raise RuntimeError("Unexpected RPM verification difference: "+line)
    observed.append(match.group(2))
if set(observed)!=set(configs) or not (0<result.returncode<=len(lines)):
    raise RuntimeError("Expected local-config-only verification status mismatch: "+str(result.returncode)+" "+result.stdout.decode())
print("RPM_VERIFY_EXPECTED_LOCAL_CONFIG_ONLY returncode="+str(result.returncode)+" records="+str(len(lines)))
