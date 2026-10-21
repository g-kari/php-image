#!/usr/bin/env python3
import json,os,pathlib,shutil,subprocess,tempfile
lines=pathlib.Path("out/IMAGE.txt").read_text().splitlines()
ref=next(x for x in lines if x.startswith("ghcr.io/g-kari/php-image@sha256:"))
expected=json.load(open("out/image-inspect.json"))[0]["Id"]
config=tempfile.mkdtemp(prefix="empty-docker-config-")
env=dict(os.environ,DOCKER_CONFIG=config)
env.pop("GH_TOKEN",None)
try:
    p=subprocess.run(["docker","pull",ref],env=env,text=True,capture_output=True,timeout=180)
    if p.returncode:
        print("ANONYMOUS_PULL_RESULT="+json.dumps({"public":False,"digest":ref,"state":"visibility or anonymous access pending"}))
        print(p.stderr)
    else:
        actual=subprocess.check_output(["docker","image","inspect","-f","{{.Id}}",ref],env=env,text=True).strip()
        if actual!=expected:raise RuntimeError("Anonymous image differs from exact tested image")
        expected_source=json.load(open("out/source.json"))["sha"]
        got=subprocess.check_output(["docker","run","--rm","--network","none",ref,"php","-r",'echo file_get_contents("/usr/local/share/php-mitigation/source.json");'],env=env,text=True)
        if json.loads(got)["sha"]!=expected_source:raise RuntimeError("Wrong source in public runtime image")
        subprocess.run(["docker","run","--rm","--network","none",ref,"sh","-c","cd / && sha256sum -c /usr/local/share/php-mitigation/binaries.sha256"],env=env,check=True)
        print("ANONYMOUS_PULL_RESULT="+json.dumps({"public":True,"digest":ref,"tested_image_id":actual,"source_sha":expected_source}))
finally:shutil.rmtree(config)
