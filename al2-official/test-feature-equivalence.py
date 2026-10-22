#!/usr/bin/env python3
import copy,os
from feature_equivalence import canonical_payload,HOOK,MODULE,ELF_SHA256,FILE_OFFSET
def fixture(base):
    stat={"dev":os.makedev(0,48),"ino":9225599,"size":82720,"mode":0o100755,"mtime":1,"ctime":1}
    pointer=base+FILE_OFFSET
    return {"features":{"series":"7.4","defined_constants":{HOOK:{"type":"integer","value":pointer},"ordinary":{"type":"integer","value":42}},
      "process_local_hook":{"constant_name":HOOK,"pointer":pointer,"module_path":MODULE,"module_sha256":ELF_SHA256,
      "stat_before":stat,"stat_after":copy.deepcopy(stat),"apcu_version":"5.1.18",
      "maps":[f"{base:x}-{base+0x11000:x} r-xp 00000000 00:30 9225599                    {MODULE}"]}},"pecl":{"bounded_local_checks":"passed"}}
a,b=fixture(0x7f0000000000),fixture(0x7f1000000000)
if canonical_payload(a)!=canonical_payload(b):raise RuntimeError("ASLR normalization differs")
if a["features"]["defined_constants"][HOOK]["value"]!=0x7f0000000000+FILE_OFFSET:raise RuntimeError("Raw evidence was mutated")
bad=[]
x=copy.deepcopy(a);x["features"]["process_local_hook"]["pointer"]+=1;x["features"]["defined_constants"][HOOK]["value"]+=1;bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]["module_sha256"]="0"*64;bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]["stat_after"]["ino"]+=1;bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]["maps"][0]=x["features"]["process_local_hook"]["maps"][0].replace("r-xp","rw-p");bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]["maps"][0]=x["features"]["process_local_hook"]["maps"][0].replace("9225599","9225600");bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]["maps"]*=2;bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]["module_path"]="/tmp/apcu.so";bad.append(x)
x=copy.deepcopy(a);x["features"]["defined_constants"][HOOK]["type"]="string";bad.append(x)
x=copy.deepcopy(a);x["features"]["process_local_hook"]=None;bad.append(x)
x=copy.deepcopy(a);x["features"]["series"]="8.0";bad.append(x)
for value in bad:
    try:canonical_payload(value)
    except RuntimeError:pass
    else:raise RuntimeError("Invalid pointer evidence accepted")
x=copy.deepcopy(a);x["features"]["defined_constants"]["ordinary"]["value"]=43
if canonical_payload(a)==canonical_payload(x):raise RuntimeError("Ordinary constant difference hidden")
plain={"features":{"series":"8.1","defined_constants":{"CURLINFO_LASTONE":{"type":"integer","value":64}},"process_local_hook":None}}
if canonical_payload(plain)!={"features":{"series":"8.1","defined_constants":{"CURLINFO_LASTONE":{"type":"integer","value":64}}}}:raise RuntimeError("Non-APCu payload changed")
print("EXACT_APCU_PROCESS_POINTER_POLICY_UNIT_PASSED")
