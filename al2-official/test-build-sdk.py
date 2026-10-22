#!/usr/bin/env python3
import runpy,stat,sys
from pathlib import Path
ns=runpy.run_path(str(Path(__file__).with_name("build-sdk.py")));members=ns["members"]
def record(name,data=b"",mode=0o100644,nlink=1):
    name=name.encode()+b"\0"
    fields=[1,mode,0,0,nlink,0,len(data),0,0,0,0,len(name),0]
    raw=b"070701"+b"".join(("%08x"%n).encode() for n in fields)+name
    raw+=b"\0"*((-len(raw))%4);raw+=data;raw+=b"\0"*((-len(raw))%4)
    return raw
trailer=record("TRAILER!!!",mode=0,nlink=1)
good=record("./usr/include/curl/a.h",b"header")+trailer
if members(good)!=[("usr/include/curl/a.h",0o100644,1,b"header")]:raise RuntimeError("Valid member decode")
for bad in (good[:-1],good+b"x",record("../outside",b"x")+trailer,record("/outside",b"x")+trailer,
    record("./usr/include/a.h",b"x")+record("usr/include/a.h",b"x")+trailer,b"bad"+good[3:],
    record("usr//include/a.h",b"x")+trailer):
    try:members(bad)
    except RuntimeError:pass
    else:raise RuntimeError("Invalid SDK archive accepted")
if ns["selected"]("usr/include/openssl/ssl.h","libcurl-devel"):raise RuntimeError("OpenSSL copied")
if ns["selected"]("usr/include/pgsql/server/a.h","postgresql-devel"):raise RuntimeError("Server header copied")
if ns["selected"]("usr/lib64/libcurl.so","libcurl-devel"):raise RuntimeError("Library copied")
if not ns["selected"]("usr/include/libpq/libpq-fs.h","postgresql-devel"):raise RuntimeError("Client header omitted")
if ns["bounded"]([sys.executable,"-c","import sys;sys.stdout.write('abc')"],3)!=b"abc":raise RuntimeError("Bounded pipe altered bytes")
for command,limit in (([sys.executable,"-c","print('abcdef')"],3),([sys.executable,"-c","import sys;sys.stderr.write('warning')"],100),([sys.executable,"-c","raise SystemExit(2)"],100)):
    try:ns["bounded"](command,limit)
    except RuntimeError:pass
    else:raise RuntimeError("Bounded payload failure accepted")
recipe="\t$(LIBTOOL) --mode=compile $(CC) -Iext/curl/ -I/source/ext/curl/ $(COMMON_FLAGS) $(CFLAGS_CLEAN) $(EXTRA_CFLAGS) -DFIXTURE=1 -c /source/ext/curl/interface.c -o ext/curl/interface.lo"
stem,transformed,source=ns["unit_recipe"](recipe,0)
if transformed!="$(CC) -Iext/curl/ -I/source/ext/curl/ $(COMMON_FLAGS) $(CFLAGS_CLEAN) $(EXTRA_CFLAGS) -DFIXTURE=1 -E -H -dM /source/ext/curl/interface.c > sdk-unit-0-macros.txt 2> sdk-unit-0-headers.txt":raise RuntimeError("Actual client recipe flag order changed")
for suffix in (" ","\t"," \t "):
    if ns["unit_recipe"](recipe+suffix,0)!=(stem,transformed,source):raise RuntimeError("Actual recipe trailing horizontal whitespace")
pic_recipe=recipe.replace(" -c "," -prefer-pic -c ")
if " -fPIC -DPIC -E " not in ns["unit_recipe"](pic_recipe,0)[1]:raise RuntimeError("Libtool PIC adaptation")
for command in (recipe.replace(" -c "," --sysroot=/wrong -c "),recipe+" && true",recipe.replace("$(LIBTOOL) --mode=compile ",""),recipe.replace(" -o "," -unknown ")):
    try:ns["unit_recipe"](command,0)
    except RuntimeError:pass
    else:raise RuntimeError("Unknown client recipe accepted")
root=Path("/fixed/php-source")
names={"datetime.h","curl.h","libpq-fe.h"}
if ns["external_client_header"](root/"ext/standard/datetime.h",names,"7.4",root):raise RuntimeError("Fixed PHP-owned header mislabeled as external SDK")
for wrong in (Path("/usr/include/datetime.h"),Path("/usr/include/curl/curl.h"),Path("/other-sdk/libpq-fe.h")):
    if not ns["external_client_header"](wrong,names,"7.4",root):raise RuntimeError("External mixed client header accepted")
if not ns["external_client_header"](Path("/usr/include/curl/curl.h"),names,"8.0",root):raise RuntimeError("8.0 external curl header accepted")
print("PINNED_HEADER_SDK_ARCHIVE_POLICY_UNIT_PASSED")
