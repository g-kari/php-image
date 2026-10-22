#!/usr/bin/env python3
"""Canonicalize one proven process-local APCu hook; all real API values stay exact."""
import copy,os,re
HOOK="\x00apc_register_serializer-0"
MODULE="/usr/lib64/php/modules/apcu.so"
ELF_SHA256="28ee69e768a5c70a36e06f2305ff69eae4e3bc8f6747bdfa8518f610b7096efb"
FILE_OFFSET=27792  # _apc_register_serializer, signed vendor ELF symbol/PT_LOAD evidence.
def require(ok,why):
    if not ok:raise RuntimeError("APCu process-local pointer evidence: "+why)
def canonical_payload(payload):
    if not __debug__:raise RuntimeError("Optimized verification forbidden")
    data=copy.deepcopy(payload)
    feature=data.get("features")
    require(isinstance(feature,dict),"feature object missing")
    require("process_local_hook" in feature,"hook observation field missing")
    raw=feature.pop("process_local_hook")
    constants=feature.get("defined_constants")
    require(isinstance(constants,dict),"constant inventory missing")
    if raw is None:
        require(HOOK not in constants,"hook lacks process mapping")
        return data
    require(feature.get("series")=="7.4","unexpected series")
    require(isinstance(raw,dict) and set(raw)=={"constant_name","pointer","module_path","module_sha256","stat_before","stat_after","maps","apcu_version"},"hook observation schema")
    require(raw["constant_name"]==HOOK and raw["module_path"]==MODULE and raw["apcu_version"]=="5.1.18","identity")
    require(raw["module_sha256"]==ELF_SHA256,"signed vendor ELF bytes changed")
    value=constants.get(HOOK)
    require(isinstance(value,dict) and set(value)=={"type","value"} and value["type"]=="integer","constant type")
    pointer=raw["pointer"]
    require(type(pointer) is int and pointer>0 and value["value"]==pointer,"pointer value")
    keys={"dev","ino","size","mode","mtime","ctime"}
    before,after=raw["stat_before"],raw["stat_after"]
    require(isinstance(before,dict) and isinstance(after,dict) and set(before)==set(after)==keys and before==after,"file changed while hashing")
    require(all(type(before[key]) is int and before[key]>=0 for key in keys),"stat representation")
    require(before["ino"]>0 and before["size"]>FILE_OFFSET and (before["mode"]&0o170000)==0o100000,"regular ELF file")
    rows=raw["maps"]
    require(isinstance(rows,list) and 1<=len(rows)<=32,"mapping inventory")
    matches=[]
    for row in rows:
        require(isinstance(row,str) and len(row)<1000,"mapping line bound")
        match=re.fullmatch(r"([0-9a-f]+)-([0-9a-f]+) ([rwxps-]+) ([0-9a-f]+) ([0-9a-f]+):([0-9a-f]+)\s+([0-9]+)\s+(.+)",row)
        require(match is not None,"mapping syntax")
        start,end=int(match[1],16),int(match[2],16)
        require(start<end and match[8]==MODULE,"mapping path/range")
        require((int(match[5],16),int(match[6],16),int(match[7]))==(os.major(before["dev"]),os.minor(before["dev"]),before["ino"]),"mapping device/inode")
        if start<=pointer<end:
            require(match[3]=="r-xp","pointer is not in an executable private mapping")
            matches.append(int(match[4],16)+pointer-start)
    require(matches==[FILE_OFFSET],"pointer is not the exact observed serializer function")
    constants[HOOK]["value"]={"representation":"apcu-5.1.18-vendor-serializer-hook-abi0","module":MODULE,
      "elf_sha256":ELF_SHA256,"symbol":"_apc_register_serializer","file_offset":FILE_OFFSET}
    return data
