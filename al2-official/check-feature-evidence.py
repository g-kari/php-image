#!/usr/bin/env python3
"""Validate real raw pointer evidence before spending time compiling PHP."""
import json,sys
from pathlib import Path
from feature_equivalence import canonical_payload
root=Path(sys.argv[1])
for tool in ("php","zts-php","phpdbg","zts-phpdbg","php-cgi","embedded","apache-normal","apache-named-zts"):
    canonical_payload(json.load(open(root/(tool+".json"))))
canonical_payload(json.load(open(root/"fpm.json"))["features"])
print("REAL_BASELINE_FEATURE_EVIDENCE_POLICY_PASSED")
