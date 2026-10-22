#!/usr/bin/env python3
"""Private prefork Apache and embedding smoke. No packaged handler configuration is changed."""
import json,os,shlex,subprocess,sys,time,urllib.request
from pathlib import Path
series,phase=sys.argv[1:];out=Path("/out/qa")/phase
def command(args,**kw):
    try:return subprocess.check_output(args,**kw)
    except subprocess.CalledProcessError as error:
        print("SAPI_COMMAND_FAILED "+repr(args)+"\n"+error.output.decode(errors="replace")[-8000:],flush=True)
        raise
def parse_response(data,label):
    try:return json.loads(data)
    except ValueError:
        print("SAPI_NON_JSON_RESPONSE "+label+"\n"+data.decode(errors="replace")[-8000:],flush=True)
        raise
includes=shlex.split(command(["php-config","--includes"]).decode())
libraries=[p for p in command(["rpm","-ql","php-embedded"]).decode().splitlines()
           if p in ("/usr/lib64/libphp7.so","/usr/lib64/libphp.so")]
if len(libraries)!=1:raise RuntimeError("Unrecognized embedded library")
command(["gcc",*includes,"/work/al2-official/embed-probe.c",libraries[0],"-o","/tmp/php-embed-ci"])
data=command(["timeout","20","/tmp/php-embed-ci",series])
parse_response(data,"embedded");(out/"embedded.json").write_bytes(data)
modules=Path("/usr/lib64/httpd/modules")
basename="libphp7" if series=="7.4" else "libphp"
identifier="php7_module" if series=="7.4" else "php_module"
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for label,suffix in (("normal",""),("named-zts","-zts")):
    library=modules/(basename+suffix+".so")
    if not library.is_file():raise RuntimeError("Packaged Apache SAPI missing")
    root=Path("/tmp")/("ci-httpd-"+phase+"-"+label);root.mkdir()
    runtime=root/"run";runtime.mkdir()
    config=root/"httpd.conf"
    text='ServerRoot "'+str(root)+'"\nDefaultRuntimeDir "'+str(runtime)+'"\nServerName localhost\nListen 127.0.0.1:19444\n'
    for name,file in (("mpm_prefork_module","mod_mpm_prefork.so"),("unixd_module","mod_unixd.so"),("authz_core_module","mod_authz_core.so")):
        path=modules/file
        if not path.is_file():raise RuntimeError("Expected official Apache module missing: "+file)
        text+='LoadModule '+name+' "'+str(path)+'"\n'
    text+='LoadModule '+identifier+' "'+str(library)+'"\n'
    text+='User apache\nGroup apache\nStartServers 1\nMinSpareServers 1\nMaxSpareServers 1\nMaxRequestWorkers 2\nServerLimit 2\n'
    text+='PidFile "'+str(root/"httpd.pid")+'"\nErrorLog "'+str(root/"error.log")+'"\n'
    text+='DocumentRoot "/work/al2-official"\n<Directory "/work/al2-official">\nRequire all granted\n</Directory>\n'
    text+='<Files "probe-entry.php">\nSetHandler application/x-httpd-php\n</Files>\n'
    config.write_text(text)
    command(["httpd","-t","-f",str(config)])
    log=(out/("apache-"+label+".log")).open("wb")
    process=subprocess.Popen(["httpd","-X","-f",str(config)],stdout=log,stderr=subprocess.STDOUT)
    try:
        response=None
        for attempt in range(50):
            if process.poll() is not None:raise RuntimeError("Private Apache process exited")
            try:
                with opener.open("http://127.0.0.1:19444/probe-entry.php?series="+series,timeout=3) as request:
                    response=request.read(1048576)
                break
            except OSError:time.sleep(0.1)
        if response is None:raise RuntimeError("Private Apache readiness failed")
        payload=parse_response(response,"apache-"+label)
        if payload["features"]["sapi"]!="apache2handler":raise RuntimeError("Wrong Apache handler")
        (out/("apache-"+label+".json")).write_bytes(response)
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
print("ADDITIONAL_SAPI_SMOKE_PASSED series="+series+" phase="+phase)
