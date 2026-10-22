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
print("EXACT_GENERATED_AUXILIARY_CACHE_POLICY_UNIT_PASSED")
