#!/usr/bin/env python3
"""Read only the exact glibc2.26 ldconfig auxiliary cache, not the loader cache."""
import hashlib,struct
PATH="/var/cache/ldconfig/aux-cache"
MAGIC=b"glibc-ld.so.auxcache-1.0"
def parse_aux(raw):
    if not 33<=len(raw)<=16000000 or raw[:24]!=MAGIC:raise RuntimeError("Unknown auxiliary cache format/size")
    count,strings=struct.unpack_from("<II",raw,24)
    if count>100000 or not strings or 32+48*count+strings!=len(raw):raise RuntimeError("Auxiliary cache length/count mismatch")
    table=raw[32+48*count:]
    if table[:1]!=b"\0":raise RuntimeError("Auxiliary cache string table")
    ids=set();records=[]
    for index in range(count):
        ino,ctime,size,dev,flags,offset,version,pad=struct.unpack_from("<QQQQiIIi",raw,32+48*index)
        identity=(ino,ctime,size,dev)
        if identity in ids or pad or offset>=strings:raise RuntimeError("Auxiliary cache identity/padding/offset")
        ids.add(identity)
        if offset==0:name=None
        else:
            end=table.find(b"\0",offset)
            if end<0:raise RuntimeError("Auxiliary cache unterminated string")
            name=table[offset:end].decode("ascii")
            if not name or "/" in name or len(name)>1000:raise RuntimeError("Auxiliary cache SONAME")
        records.append({"soname":name,"flags":flags,"osversion":version})
    records.sort(key=lambda x:(x["soname"] or "",x["flags"],x["osversion"]))
    return {"format":"glibc-ld.so.auxcache-1.0/le64","count":count,"semantic_records":records}
