#!/usr/bin/env python3
import struct
from aux_cache import parse_aux,MAGIC
def fixture(ino=1):
    return MAGIC+struct.pack("<II",1,8)+struct.pack("<QQQQiIIi",ino,2,3,4,1,1,0,0)+b"\0lib.so\0"
a=fixture()
if parse_aux(a)!=parse_aux(fixture(9)):raise RuntimeError("Inode should not alter semantic cache inventory")
for raw in (b"",a+b"\0",b"x"+a[1:],a[:24]+struct.pack("<II",2,8)+a[32:],a[:32]+struct.pack("<QQQQiIIi",1,2,3,4,1,9,0,0)+a[80:],a[:32]+struct.pack("<QQQQiIIi",1,2,3,4,1,1,0,1)+a[80:],a[:-1]+b"x"):
    try:parse_aux(raw)
    except (RuntimeError,UnicodeError):pass
    else:raise RuntimeError("Malformed auxiliary cache accepted")
def cache(rows):
    table=b"\0";entries=[]
    for identity,flags,name,version in rows:
        offset=len(table) if name else 0
        if name:table+=name.encode()+b"\0"
        entries.append(struct.pack("<QQQQiIIi",*identity,flags,offset,version,0))
    return MAGIC+struct.pack("<II",len(rows),len(table))+b"".join(entries)+table
one=((1,2,3,4),1,"liba.so",0);two=((5,6,7,8),1,"libb.so",1)
if parse_aux(cache([one,two]))!=parse_aux(cache([two,one])):raise RuntimeError("Cache row order affected semantics")
for identity in ((9,2,3,4),(1,9,3,4),(1,2,9,4),(1,2,3,9)):
    if parse_aux(cache([(identity,1,"liba.so",0)]))!=parse_aux(cache([one])):raise RuntimeError("Cache inode/stat identity not separated")
for changed in (((1,2,3,4),2,"liba.so",0),((1,2,3,4),1,"other.so",0),((1,2,3,4),1,"liba.so",1)):
    if parse_aux(cache([changed]))==parse_aux(cache([one])):raise RuntimeError("Cache semantic difference hidden")
if parse_aux(cache([one,((5,6,7,8),1,"liba.so",0)]))==parse_aux(cache([one])):raise RuntimeError("Cache multiplicity hidden")
try:parse_aux(cache([one,one]))
except RuntimeError:pass
else:raise RuntimeError("Duplicate auxiliary identity accepted")
print("EXACT_GENERATED_AUXILIARY_CACHE_POLICY_UNIT_PASSED")
