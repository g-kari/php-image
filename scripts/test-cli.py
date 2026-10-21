#!/usr/bin/env python3
"""Functional smoke and deliberate OOM semantics. This is not an exploit/security proof."""
import json, subprocess, sys
if not __debug__: raise RuntimeError("Optimized Python would disable verification; refusing")
php = sys.argv[1]
series = sys.argv[2] if len(sys.argv) > 2 else "legacy"
def run(code, extra=()):
    return subprocess.run([php, "-n", *extra, "-r", code], text=True, capture_output=True, timeout=20)
p = run("""$s=['x'=>[1,2,3]]; if (unserialize(serialize($s))!==$s) exit(2);
parse_str('a[b][c]=hello',$q); if($q['a']['b']['c']!=='hello')exit(3);
if(json_decode(json_encode($s),true)!==$s)exit(4); echo "functional-ok";""")
assert p.returncode == 0 and p.stdout == "functional-ok", p
p = run("""register_shutdown_function(function(){echo "SHUTDOWN-MUST-NOT-RUN";});
$x=[];while(true){$x[]=str_repeat('A',1048576);}""", ("-d", "memory_limit=16M"))
assert p.returncode == (255 if series == "8.2" else 1), p
assert "Allowed memory size" in p.stderr + p.stdout, p
if series == "8.2":
    assert "SHUTDOWN-MUST-NOT-RUN" in p.stderr + p.stdout, p
else:
    assert "SHUTDOWN-MUST-NOT-RUN" not in p.stderr + p.stdout, p
print(json.dumps({"functional": "passed", "oom_exit":p.returncode, "shutdown_handler_not_run":series != "8.2"}))
