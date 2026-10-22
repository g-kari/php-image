#!/usr/bin/env python3
"""Allowlist-only spec edit: one extra security patch and RPM Release suffix, no SAPI/path changes."""
import difflib,hashlib,json,pathlib,re,sys
if not __debug__: raise RuntimeError("Optimized verification forbidden")
original,destination,lockpath,series,patchpath=sys.argv[1:]
lock=json.load(open(lockpath))["series"][series]
source=pathlib.Path(original).read_text()
if source.count("# Prevent %%doc confusion over LICENSE files\n")!=1: raise RuntimeError("Ambiguous security-patch insertion")
if re.search(r"(?m)^Patch9999:",source): raise RuntimeError("Patch number already used")
if source.count("Release: 1%{?dist}%{?_trivial}%{?_buildid}")!=1: raise RuntimeError("Unknown Release structure")
# Preserve every existing vendor patch and macro; append a literal local suffix after vendor Release macros.
new=source.replace("Release: 1%{?dist}%{?_trivial}%{?_buildid}","Release: 1%{?dist}%{?_trivial}%{?_buildid}.cve2026_109618_109619.1",1)
grammar_files=sorted({line[6:] for line in pathlib.Path(patchpath).read_text().splitlines() if line.startswith("+++ b/") and line.endswith((".re",".y",".dasc"))})
if any(".." in p.split("/") or p.startswith("/") for p in grammar_files): raise RuntimeError("Unsafe grammar path")
regenerate=("touch "+" ".join(grammar_files)+"\n") if grammar_files else ""
if grammar_files:
    new=new.replace("\nBuildRequires: bzip2-devel", "\nBuildRequires: re2c bison\nBuildRequires: bzip2-devel",1)
application="# Complete upstream two-CVE security backport, after all existing vendor patches\npatch --batch --forward --fuzz=0 -p1 < %{PATCH9999}\npatch --dry-run --reverse --batch --fuzz=0 -p1 < %{PATCH9999}\n"+regenerate+"\n# Prevent %%doc confusion over LICENSE files\n"
new=new.replace("# Prevent %%doc confusion over LICENSE files\n",application,1)
print("SECURITY_GRAMMARS_REQUIRE_REGENERATION="+json.dumps(grammar_files))

marker="\n%description\n"
if new.count(marker)!=1: raise RuntimeError("Ambiguous main description")
new=new.replace(marker,"\nPatch9999: php-upstream-cve2026.patch\n"+marker,1)
pathlib.Path(destination).write_text(new)
diff="".join(difflib.unified_diff(source.splitlines(True),new.splitlines(True),fromfile="AWS/php.spec",tofile="local/php.spec"))
print("OFFICIAL_SPEC_MINIMAL_DIFF_BEGIN\n"+diff+"OFFICIAL_SPEC_MINIMAL_DIFF_END")
# The literal suffix remains after any vendor macro redefinition; parsed NEVR is independently checked.
