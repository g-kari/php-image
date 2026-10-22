#!/usr/bin/env python3
import hashlib,json,re,subprocess,sys
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
(out/"system-libraries.sha256").write_text(digest(paths))
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
