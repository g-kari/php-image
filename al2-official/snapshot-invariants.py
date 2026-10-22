#!/usr/bin/env python3
import hashlib,json,subprocess,sys
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
if result.returncode not in (0,1):raise RuntimeError("RPM verification command failed")
(out/"rpm-verify.txt").write_bytes(result.stdout)
if result.stderr:raise RuntimeError("Unexpected RPM verification error: "+result.stderr.decode())
