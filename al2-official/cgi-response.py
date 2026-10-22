#!/usr/bin/env python3
"""Validate exact CGI framing, then retain the complete JSON body separately."""
import json,re,sys
from pathlib import Path

def validate(raw):
    if not raw or len(raw)>2*1024*1024:raise RuntimeError("CGI response size")
    if b"\r\n\r\n" not in raw:raise RuntimeError("CGI header/body framing missing")
    head,body=raw.split(b"\r\n\r\n",1)
    if len(head)>4096:raise RuntimeError("CGI headers too large")
    headers={}
    for line in head.split(b"\r\n"):
        if b":" not in line:raise RuntimeError("Malformed CGI header")
        key,value=line.split(b":",1)
        if not re.fullmatch(rb"[A-Za-z][A-Za-z-]*",key):raise RuntimeError("Invalid CGI header name")
        name=key.decode("ascii").lower();value=value.strip(b" \t")
        if name not in ("content-type","x-powered-by","status") or name in headers:
            raise RuntimeError("Unexpected or duplicate CGI header")
        if any(c<32 or c>126 for c in value):raise RuntimeError("Invalid CGI header value")
        headers[name]=value.decode("ascii")
    if headers.get("content-type","").lower()!="application/json":raise RuntimeError("CGI content type")
    if "status" in headers and headers["status"]!="200 OK":raise RuntimeError("CGI non-success status")
    if "x-powered-by" in headers and not re.fullmatch(r"PHP/[0-9]+\.[0-9]+\.[0-9]+(?:[-a-zA-Z0-9.]*)",headers["x-powered-by"]):
        raise RuntimeError("CGI X-Powered-By")
    payload=json.loads(body)
    if not isinstance(payload,dict) or payload.get("features",{}).get("local_features")!="passed" or payload.get("pecl",{}).get("bounded_local_checks")!="passed":
        raise RuntimeError("CGI feature probe incomplete")
    return body,headers

def selftest():
    body=b'{"features":{"local_features":"passed"},"pecl":{"bounded_local_checks":"passed"}}\n'
    good=b"X-Powered-By: PHP/8.1.34\r\nContent-type: application/json\r\n\r\n"+body
    if validate(good)[0]!=body:raise RuntimeError("CGI parser changed body")
    bad=[b"Warning: hidden\n"+good,good.replace(b"application/json",b"text/html"),
         good.replace(b"X-Powered-By:",b"Status: 500 Error\r\nX-Powered-By:"),
         good.replace(b"Content-type:",b"Content-type: application/json\r\nContent-type:"),
         good.replace(b"\r\n\r\n",b"\n\n"),
         good+b"warning",good.replace(b'"passed"',b'"failed"',1),
         good.replace(b"X-Powered-By:",b"Unrecognized: value\r\nX-Powered-By:")]
    for sample in bad:
        try:validate(sample)
        except (RuntimeError,ValueError,UnicodeError):continue
        raise RuntimeError("CGI parser accepted invalid response")
    print("CGI_RESPONSE_POLICY_UNIT_PASSED")

if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:selftest()
    else:
        raw=Path(sys.argv[1]).read_bytes()
        try:body,headers=validate(raw)
        except Exception:
            print("CGI_RESPONSE_PREFIX "+repr(raw[:2000]),file=sys.stderr)
            raise
        Path(sys.argv[2]).write_bytes(body)
        Path(sys.argv[3]).write_text(json.dumps(headers,sort_keys=True)+"\n")
        print("CGI_RESPONSE_FRAMING_AND_PROBE_PASSED")
