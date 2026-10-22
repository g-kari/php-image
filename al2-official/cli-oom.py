#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
series,phase=sys.argv[1:]
result={}
for binary in ("php","zts-php"):
    code='$_GET=["series"=>$argv[1],"mode"=>"oom"];require "/work/al2-official/probe-entry.php";'
    process=subprocess.run(["timeout","15",binary,"-r",code,series],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output=process.stdout.decode(errors="replace")
    expected=1 if phase=="patched" else 255
    marker="CI-SHUTDOWN-MARKER" in output
    if process.returncode!=expected or marker!=(phase!="patched"):
        raise RuntimeError("CLI OOM profile mismatch "+binary+" rc="+str(process.returncode)+" "+output)
    result[binary]={"returncode":process.returncode,"shutdown_marker":marker,"output":output}
(Path("/out/qa")/phase/"cli-oom.json").write_text(json.dumps(result,indent=2,sort_keys=True))
print("CLI_OOM_EXIT_PROFILE_PASSED "+series+" "+phase)
