"""Narrow, deterministic PHPT diff normalization; never hide changed values."""
import re
def normalize_diff(value,series,test):
    value=value.replace("\r","")
    value=re.sub(r"/home/builder/rpmbuild/BUILD/php-[0-9.]+/","<SOURCE>/",value)
    value=re.sub(r"/tmp/php-vendor-phpt-reference/php-[0-9.]+/","<SOURCE>/",value)
    value=re.sub(r"/tmp/php[A-Za-z0-9]{6}\b","/tmp/php<FIXTURE>",value)
    if series=="8.1" and test in ("ext/openssl/tests/sni_server.diff","ext/openssl/tests/sni_server_key_cert.diff"):
        pattern=r"(Warning: stream_socket_client\(\): Unable to connect to tls://127\.0\.0\.1:)([0-9]+)( \(Unknown error\) in <SOURCE>/ext/openssl/tests/ServerClientTestCase\.inc\(161\) : eval\(\)'d code on line 9)"
        def replace(match):
            if not 1<=int(match.group(2))<=65535:raise RuntimeError("Invalid ephemeral loopback SNI port")
            return match.group(1)+"<PORT>"+match.group(3)
        value,count=re.subn(pattern,replace,value)
        if count!=1:raise RuntimeError("Missing/ambiguous exact historical SNI loopback-port line")
    return value.rstrip()+"\n"
