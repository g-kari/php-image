#!/usr/bin/env python3
"""Bounded local FastCGI checks, including worker reuse and intentional OOM replacement."""
import json, socket, struct, sys, time
if not __debug__: raise RuntimeError("Optimized Python would disable verification; refusing")
host, port = "127.0.0.1", int(sys.argv[1])
def record(t, content):
    pad = (-len(content)) % 8
    return struct.pack("!BBHHBB", 1,t,1,len(content),pad,0)+content+b"\0"*pad
def length(n):
    return bytes([n]) if n < 128 else struct.pack("!I", n | 0x80000000)
def request(query="", body=b"", content_type="", cookie=""):
    params={"GATEWAY_INTERFACE":"CGI/1.1","REQUEST_METHOD":"POST" if body else "GET",
            "SCRIPT_FILENAME":"/tests/request.php","SCRIPT_NAME":"/request.php",
            "QUERY_STRING":query,"SERVER_PROTOCOL":"HTTP/1.1","SERVER_NAME":"localhost",
            "SERVER_PORT":"80","REMOTE_ADDR":"127.0.0.1","CONTENT_LENGTH":str(len(body)),
            "CONTENT_TYPE":content_type, "HTTP_COOKIE":cookie}
    enc=b""
    for k,v in params.items():
        k,v=k.encode(),v.encode();enc+=length(len(k))+length(len(v))+k+v
    data=b""; errors=b""
    with socket.create_connection((host,port),timeout=5) as s:
        s.settimeout(10)
        s.sendall(record(1,struct.pack("!HB5x",1,0))+record(4,enc)+record(4,b"")+record(5,body)+record(5,b""))
        def recv(n):
            b=b""
            while len(b)<n:
                p=s.recv(n-len(b))
                if not p: raise EOFError("FastCGI worker closed")
                b+=p
            return b
        while True:
            try: h=recv(8)
            except EOFError: break
            _,t,_,n,pad,_=struct.unpack("!BBHHBB",h)
            v=recv(n); recv(pad)
            if t==6:data+=v
            elif t==7:errors+=v
            elif t==3:break
    return data,errors
def parse(data):
    headers,body=data.split(b"\r\n\r\n",1)
    return headers.decode(),json.loads(body)
for _ in range(30):
    try: h,first=parse(request()[0]);break
    except (OSError,ValueError):time.sleep(1)
else: raise AssertionError("FPM did not become ready")
assert first["ok"] and first["opcache"],first
cookie=next((s.split(":",1)[1].strip().split(";")[0] for s in h.split("\r\n") if s.lower().startswith("set-cookie:")),None)
assert cookie
for _ in range(10):
    _,got=parse(request(cookie=cookie)[0])
    assert got["pid"]==first["pid"] and got["opcache_cached"],got
assert got["counter"]==11,got
body=(b"--testbound\r\nContent-Disposition: form-data; name=\"PHP_SESSION_UPLOAD_PROGRESS\"\r\n\r\nprogress\r\n"
      b"--testbound\r\nContent-Disposition: form-data; name=\"upload\"; filename=\"tiny.txt\"\r\nContent-Type: text/plain\r\n\r\nhello\r\n--testbound--\r\n")
_,upload=parse(request(body=body,content_type="multipart/form-data; boundary=testbound",cookie=cookie)[0])
assert upload["files"]==["upload"],upload
data,err=request(query="oom=1")
assert b"SHUTDOWN-MUST-NOT-RUN" not in data+err,(data,err)
for _ in range(20):
    try:
        _,after=parse(request()[0])
        if after["pid"]!=first["pid"]:break
    except (OSError,ValueError):pass
    time.sleep(0.5)
else:raise AssertionError("OOM worker was not replaced")
assert after["ok"] and after["opcache"]
print(json.dumps({"fpm_reuse_requests":10,"multipart_upload":"passed","oom_worker_replaced":True,
                  "opcache_loaded":True,"before_pid":first["pid"],"after_pid":after["pid"]}))
