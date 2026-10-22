#!/usr/bin/env python3
"""Bounded parser cases. Does not download packages, change keys or run real rpm."""
import re,subprocess
from pathlib import Path
GOOD="""/out/vendor/pecl/php-pecl-mailparse-3.1.0-1.amzn2.0.2.x86_64.rpm:
    Header V4 RSA/SHA256 Signature, key ID c87f5b1a: OK
    Header SHA1 digest: OK (bab78c99c612eba07bbddd9c21c4b54c3ce0ec03)
    V4 RSA/SHA256 Signature, key ID c87f5b1a: OK
    MD5 digest: OK (c1a35faadbadd224c1f6c28f2c0e5c7c)
"""
def grep(pattern,text):
    p=subprocess.run(["grep","-Eiq",pattern],input=text.encode())
    if p.returncode not in (0,1):raise RuntimeError("Parser subprocess error")
    return p.returncode==0
def tests(sources):
    for name,text in sources.items():
        candidates=re.findall(r"grep -(?:Eiq|Eq) '([^']+)'",text)
        bad=[p for p in candidates if "NOKEY" in p]
        rsa=[p for p in candidates if "RSA" in p or "(RSA|DSA)" in p]
        if len(bad)!=1 or len(rsa)!=1:raise RuntimeError("Signature guards missing or ambiguous: "+name)
        if grep(bad[0],GOOD) or not grep(rsa[0],GOOD):raise RuntimeError("Good signed digest containing badd rejected")
        for status in ("BAD","NOT OK","NOKEY","NOTTRUSTED"):
            changed=GOOD.replace("key ID c87f5b1a: OK","key ID c87f5b1a: "+status,1)
            if not grep(bad[0],changed):raise RuntimeError("Bad signature status not caught: "+status)
        if grep(rsa[0],GOOD.replace("c87f5b1a","00000000")) and "acquire-vendor" in name:
            raise RuntimeError("Unexpected signing key accepted")
    acquire=sources["al2-official/acquire-vendor.sh"]
    match=re.search(r"(?ms)^verify_signature\(\) \{\n.*?^\}",acquire)
    if not match:raise RuntimeError("Signature function absent")
    script="set -euo pipefail\nrpm() { return 7; }\n"+match.group(0)+'\nverify_signature /test/official.rpm /dev/null\necho SHOULD_NOT_REACH\n'
    result=subprocess.run(["bash","-c",script],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode==0 or b"SHOULD_NOT_REACH" in result.stdout:raise RuntimeError("rpm nonzero was bypassed")
    pipeline="set -euo pipefail\nrpm() { return 7; }\nrpm --checksig --verbose /test/source.rpm | tee /dev/null\necho SHOULD_NOT_REACH\n"
    result=subprocess.run(["bash","-c",pipeline],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode==0 or b"SHOULD_NOT_REACH" in result.stdout:raise RuntimeError("Source-rpm pipeline failure masked")
    print("SIGNATURE_POLICY_UNIT_CASES_PASSED good_badd_digest=1 bad_statuses=4 wrong_key=1 nonzero_commands=2")
if __name__=="__main__":
    tests({p:Path(p).read_text() for p in ("al2-official/acquire-vendor.sh","al2-official/prepare.sh")})
