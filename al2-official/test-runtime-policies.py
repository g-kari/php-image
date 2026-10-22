#!/usr/bin/env python3
"""Network-free, no-PHP-runtime unit cases for the exact installed-QA parsers."""
import ast,hashlib,io,json,re,struct
from pathlib import Path
from types import SimpleNamespace

def functions(path,names,namespace):
    tree=ast.parse(Path(path).read_text(),filename=path)
    selected=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if {node.name for node in selected}!=set(names):raise RuntimeError("Unit target absent")
    exec(compile(ast.Module(body=selected,type_ignores=[]),path,"exec"),namespace)
    return namespace

class Connection:
    def __init__(self,data=b"",finish="reset",send_fail=False):
        self.data=data;self.finish=finish;self.send_fail=send_fail
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def settimeout(self,value):pass
    def sendall(self,data):
        if self.send_fail:raise ConnectionResetError("Synthetic send reset")
    def recv(self,size):
        if self.data:
            part=self.data[:size];self.data=self.data[size:];return part
        if self.finish=="reset":raise ConnectionResetError("Synthetic recv reset")
        return b""

ns=functions("al2-official/fastcgi.py",["ensure","record","length","request"],
    {"socket":SimpleNamespace(),"struct":struct,"series":"7.4","patched":True})
def run(data=b"",mode="oom",patched=True,finish="reset",send_fail=False):
    ns["patched"]=patched
    ns["socket"].create_connection=lambda *a,**kw:Connection(data,finish,send_fail)
    return ns["request"](mode=mode)
def reject(call):
    try:call()
    except (ConnectionResetError,EOFError,RuntimeError):return
    raise RuntimeError("Unsafe transport was accepted")
if run()[2]["completion"]!="connection-reset":raise RuntimeError("Patched OOM reset not recorded")
reject(lambda:run(mode="request"));reject(lambda:run(patched=False))
reject(lambda:run(send_fail=True))
marker=b"CI-SHUTDOWN-MARKER"
# Interrupted payload retains the entire already-received fragment, including marker.
payload_header=struct.pack("!BBHHBB",1,6,1,len(marker)+10,0,0)
result=run(payload_header+marker)
if marker not in result[0] or marker not in result[2]["raw_received"]:raise RuntimeError("Partial payload lost marker")
result=run(payload_header+marker,finish="eof")
if marker not in result[0] or result[2]["completion"]!="truncated-eof":raise RuntimeError("Partial EOF lost marker")
# Interrupted padding must not discard the complete stdout payload.
padding_header=struct.pack("!BBHHBB",1,6,1,len(marker),4,0)
result=run(padding_header+marker+b"\0")
if marker not in result[0] or marker not in result[2]["raw_received"]:raise RuntimeError("Padding reset lost marker")
reject(lambda:run(padding_header+marker+b"\0",patched=False))
valid=ns["record"](6,b"fixture")+ns["record"](3,struct.pack("!IB3x",0,0))
result=run(valid,mode="request",patched=False)
if result[0]!=b"fixture" or result[2]["completion"]!="end-request":raise RuntimeError("Normal transport changed")
print("FASTCGI_TRANSPORT_POLICY_UNIT_PASSED")

ns=functions("al2-official/phpt-policy.py",["review_warnings","retained_diff_status","abnormal_actual_hunks"],{"re":re,"json":json,"hashlib":hashlib})
# The verbatim hrtime PHPT fixture below is PHP-src php-8.0.30 material,
# under PHP License 3.01, not the MIT license for our original test harness.
# Source: https://github.com/php/php-src/blob/php-8.0.30/ext/standard/tests/hrtime/hrtime.phpt
# Full upstream terms/credits: third-party-licenses/PHP-3.01.txt and LICENSE-NOTICE.md.
fixture=b"""--TEST--
Test hrtime() aligns with microtime()
--XFAIL--
This test frequently fails in CI
--FILE--
<?php

$m0 = microtime(true);
$h0 = hrtime(true);
for ($i = 0; $i < 1024*1024; $i++);
$h1 = hrtime(true);
$m1 = microtime(true);

$d0 = ($m1 - $m0)*1000000000.0;
$d1 = $h1 - $h0;

/* Relative uncertainty. */
$d = abs($d0 - $d1)/$d1;

if ($d > 0.05) {
    print "FAIL, $d";
} else {
    print "OK, $d";
}

?>
--EXPECTF--
OK, %f
"""
class Source:
    def extractfile(self,value):return io.BytesIO(value)
members={"php-8.0.30/ext/standard/tests/hrtime/hrtime.phpt":fixture}
line="Test hrtime() aligns with microtime() [ext/standard/tests/hrtime/hrtime.phpt] (warn: XFAIL section but test passes)"
text="WARNED TEST SUMMARY\n---------------------------------------------------------------------\n"+line+"\n=====================================================================\n"
result=ns["review_warnings"](text,"8.0",members,Source())
if len(result)!=1 or result[0]["actual_status"]!="WARN":raise RuntimeError("Original WARN lost")
reject(lambda:ns["review_warnings"](text,"7.4",members,Source()))
reject(lambda:ns["review_warnings"](text.replace("hrtime()","unknown()"),"8.0",members,Source()))
reject(lambda:ns["review_warnings"](text+text,"8.0",members,Source()))
reject(lambda:ns["review_warnings"](text,"8.0",{next(iter(members)):fixture+b"changed"},Source()))
print("STRICT_PHPT_WARN_POLICY_UNIT_PASSED")

# Only new actual diff lines carrying exact harness-generated sentinels block.
for text,kind in [
 ("001+  ** ERROR: process timed out **\n","timeout"),
 ("019+ Termsig=11\r\n","signal"),
 ("1001+ Termsig=0\n","signal"),
 ("001+ ** ERROR: process timed out **\n","timeout"),
 ("002+ \t** ERROR: process timed out **\t\n","timeout"),
 ("003+ Termsig=-11\n","signal"),
 ("004+  Termsig=11\n","signal")]:
    result=ns["abnormal_actual_hunks"](text)
    if len(result)!=1 or result[0]["kind"]!=kind:raise RuntimeError("Abnormal PHPT actual hunk accepted")
for text in [
 "001- ** ERROR: process timed out **\n",
 "001- Termsig=11\n",
 "     Termsig=11\n",
 " ** ERROR: process timed out **\n",
 "001+ Message mentions Termsig=11 but is not a harness sentinel\n",
 "001+ ** ERROR: process timed out ** followed by unrelated text\n",
 "001+ Termsig=not-a-number\n",
 "001+ ordinary expected-failure output\n",
 "1+ Termsig=11\n",
 "001+Termsig=11\n",
 "001+\tTermsig=11\n",
 "001+ Termsig=-not-a-number\n"]:
    if ns["abnormal_actual_hunks"](text):raise RuntimeError("Expected/context/ordinary text misclassified")
for source,status in [("--XFAIL--\nKnown upstream bug\n","XFAIL"),("--XFAIL_EXTERNAL--\nreason.txt\n","XFAIL"),("--EXPECT--\nfixture\n","FAIL")]:
    if ns["retained_diff_status"](source)!=status:raise RuntimeError("Original upstream status relabeled")
print("STRICT_PHPT_XFAIL_ABNORMAL_POLICY_UNIT_PASSED")

normalizers=functions("al2-official/phpt_support.py",["normalize_diff"],{"re":re})
oracles=json.loads(Path("al2-official/known-phpt-diffs.json").read_text())["series"]
versions={"7.4":"7.4.33","8.0":"8.0.30","8.1":"8.1.34"}
for series,mapping in oracles.items():
    for test,expected in mapping.items():
        for prefix in ("/home/builder/rpmbuild/BUILD/","/tmp/php-vendor-phpt-reference/"):
            raw=expected.replace("<SOURCE>/",prefix+"php-"+versions[series]+"/").replace("/tmp/php<FIXTURE>","/tmp/phpAb1Zx9")
            raw=raw.replace("<PORT>","43210")
            if normalizers["normalize_diff"](raw,series,test)!=expected:
                raise RuntimeError("Exact oracle normalization changed: "+series+" "+test)
test="ext/openssl/tests/sni_server.diff";sample=oracles["8.1"][test]
for port in ("1","65535"):
    if normalizers["normalize_diff"](sample.replace("<PORT>",port),"8.1",test)!=sample:
        raise RuntimeError("Valid ephemeral port normalization changed")
for port in ("0","65536","999999"):
    reject(lambda:normalizers["normalize_diff"](sample.replace("<PORT>",port),"8.1",test))
if normalizers["normalize_diff"](sample.replace("<PORT>","43210"),"8.1","unrelated.diff")==sample:
    raise RuntimeError("Port normalization escaped the exact historical SNI test scope")
print("STRICT_SERIES_PHPT_NORMALIZATION_UNIT_PASSED")
