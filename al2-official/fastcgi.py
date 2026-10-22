#!/usr/bin/env python3
"""Loopback-only bounded FPM source-profile, progress, upload, features and OOM checks."""
import hashlib,json,re,socket,struct,sys,time
from pathlib import Path
if not __debug__:raise RuntimeError("Optimized verification forbidden")
series,phase,destination=sys.argv[1:]
if series not in ("7.4","8.0","8.1") or phase not in ("vendor","patched","rollback"):raise RuntimeError("Invalid profile")
patched=phase=="patched"
def ensure(ok,why):
    if not ok:raise RuntimeError(why)
def record(kind,data):
    padding=(-len(data))%8
    return struct.pack("!BBHHBB",1,kind,1,len(data),padding,0)+data+b"\0"*padding
def length(size):
    return bytes([size]) if size<128 else struct.pack("!I",size|0x80000000)
def request(mode="request",body=b"",content_type="",cookie=""):
    values={"GATEWAY_INTERFACE":"CGI/1.1","REQUEST_METHOD":"POST" if body else "GET",
      "SCRIPT_FILENAME":"/work/al2-official/probe-entry.php","SCRIPT_NAME":"/probe-entry.php",
      "QUERY_STRING":"series="+series+"&mode="+mode,"SERVER_PROTOCOL":"HTTP/1.1",
      "SERVER_NAME":"localhost","SERVER_PORT":"80","REMOTE_ADDR":"127.0.0.1",
      "CONTENT_LENGTH":str(len(body)),"CONTENT_TYPE":content_type,"HTTP_COOKIE":cookie}
    params=b""
    for key,value in values.items():
        key,value=key.encode(),value.encode();params+=length(len(key))+length(len(value))+key+value
    stdout=stderr=b"";raw_received=bytearray();completion=None
    with socket.create_connection(("127.0.0.1",19000),timeout=5) as connection:
        connection.settimeout(10)
        connection.sendall(record(1,struct.pack("!HB5x",1,0))+record(4,params)+record(4,b"")+record(5,body)+record(5,b""))
        def receive(size):
            data=b""
            while len(data)<size:
                try:part=connection.recv(size-len(data))
                except ConnectionResetError as error:
                    error.fcgi_partial=data
                    raise
                if not part:
                    error=EOFError("FastCGI peer closed")
                    error.fcgi_partial=data
                    raise error
                raw_received.extend(part);data+=part
                ensure(len(raw_received)<1048576,"Unexpected raw response size")
            return data
        while True:
            stage="header";kind=None
            try:
                header=receive(8)
                version,kind,identifier,size,padding,_=struct.unpack("!BBHHBB",header)
                ensure(version==1 and identifier==1,"Unexpected FastCGI record")
                stage="payload";data=receive(size)
                if kind==6:stdout+=data
                elif kind==7:stderr+=data
                stage="padding";receive(padding)
                if kind==3:completion="end-request";break
                ensure(len(stdout)+len(stderr)<1048576,"Unexpected response size")
            except (EOFError,ConnectionResetError) as error:
                partial=getattr(error,"fcgi_partial",b"")
                if stage=="payload":
                    if kind==6:stdout+=partial
                    elif kind==7:stderr+=partial
                if isinstance(error,EOFError) and stage=="header" and not partial:
                    completion="eof";break
                # Only the source-mandated hard OOM exit may interrupt an active record.
                # create/send/normal-request/vendor resets are never accepted here.
                if not (patched and mode=="oom"):raise
                completion="connection-reset" if isinstance(error,ConnectionResetError) else "truncated-eof"
                break
    return stdout,stderr,{"completion":completion,"raw_received":bytes(raw_received)}
def parse(data):
    header,body=data.split(b"\r\n\r\n",1)
    return header.decode(),json.loads(body)
for attempt in range(30):
    try:headers,first=parse(request()[0]);break
    except (OSError,ValueError):time.sleep(0.2)
else:raise RuntimeError("FPM readiness failed")
ensure(first["ok"],"FPM application response")
cookie=next((line.split(":",1)[1].strip().split(";")[0] for line in headers.split("\r\n") if line.lower().startswith("set-cookie:")),None)
ensure(cookie,"Missing session cookie")
for _ in range(10):
    _,last=parse(request(cookie=cookie)[0])
    ensure(last["pid"]==first["pid"],"Worker reuse changed")
ensure(last["counter"]==11,"Session counter")
ensure(last["opcache_loaded"] and last["opcache_cached"],"OPcache actual compilation/cache reuse")
body=(b'--ci\r\nContent-Disposition: form-data; name="PHP_SESSION_UPLOAD_PROGRESS"\r\n\r\nci\r\n'
      b'--ci\r\nContent-Disposition: form-data; name="upload"; filename="fixture.txt"\r\n'
      b'Content-Type: text/plain\r\n\r\nhello\r\n--ci--\r\n')
_,upload=parse(request(body=body,content_type="multipart/form-data; boundary=ci",cookie=cookie)[0])
ensure(upload["files"]=={"upload":{"error":0,"size":5,"uploaded":True}},"Ordinary upload regression")
ensure((upload["progress"] is None)==patched,"Upload-progress callback profile mismatch")
if not patched:ensure(upload["progress"]["done"] is True,"Vendor progress completion missing")
parts=b""
for number in range(4):
    parts+=b'--limit\r\nContent-Disposition: form-data; name="p'+str(number).encode()+b'"\r\n\r\nv\r\n'
parts+=b"--limit--\r\n"
_,limited=parse(request(body=parts,content_type="multipart/form-data; boundary=limit",cookie=cookie)[0])
expected_parts=4 if (series=="7.4" and not patched) else 3
ensure(len(limited["post"])==expected_parts,"Multipart part-count limit profile")
_,features=parse(request(mode="features")[0])
data,error,oom_transport=request(mode="oom")
raw_oom=oom_transport.pop("raw_received")
(Path(destination).parent/"oom-fastcgi-response.bin").write_bytes(raw_oom)
ensure((b"CI-SHUTDOWN-MARKER" in data+error+raw_oom)==(not patched),"OOM shutdown profile mismatch")
for attempt in range(30):
    try:
        _,recovered=parse(request()[0])
        if not patched or recovered["pid"]!=first["pid"]:break
    except (OSError,ValueError):pass
    time.sleep(0.2)
else:raise RuntimeError("OOM worker did not recover")
ensure(recovered["ok"],"FPM OOM recovery")
ensure((recovered["pid"]!=first["pid"])==patched,"Unexpected worker replacement profile")
log_path=Path(destination).parent/"fpm.log"
for attempt in range(30):
    worker_log=log_path.read_text(errors="replace")
    if not patched or ("child "+str(first["pid"])+" exited with code 1") in worker_log:break
    time.sleep(0.1)
ensure(not re.search(r"exited on signal|SIGSEGV|SIGABRT|segmentation fault|core dumped",worker_log,re.I),"FPM crash/signal observed")
if patched:
    ensure(re.search(r"child "+str(first["pid"])+r" exited with code 1(?:\D|$)",worker_log),"Patched worker did not exit with expected code 1")
result={"series":series,"phase":phase,"features":features,"ordinary_upload":"passed",
 "builtin_progress_present":upload["progress"] is not None,"multipart_parts_returned":len(limited["post"]),"session_worker_reuse":10,
 "oom_shutdown_marker":not patched,"oom_worker_replaced":patched,
 "oom_fastcgi_transport":oom_transport,"oom_raw_bytes":len(raw_oom),"oom_raw_sha256":hashlib.sha256(raw_oom).hexdigest(),
 "worker_before":first["pid"],"worker_after":recovered["pid"],"fpm_runtime":"passed"}
Path(destination).write_text(json.dumps(result,indent=2,sort_keys=True))
print("OFFICIAL_FPM_RUNTIME_PASSED "+series+" "+phase)
