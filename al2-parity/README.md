# AL2 full-feature variant under development

This is a **new independent-prefix variant**, not an overwrite or upgrade of the already-published minimal RPMs. No parity artifact is published until its own source, build, functional, SAPI, dependency and review gates pass.

The baseline is the actual official per-series AL2 Extra metadata and source specs recorded in baseline.json. Main-source runtime modules are distinguished from CLI-only facilities, other SAPIs/tooling and separate PECL source packages. A module compiled statically can fulfill capability coverage without manufacturing an empty RPM just to match a package count.

Initial implementation builds the CLI/CGI/phpdbg tree separately from FPM/embedded. PCNTL and libedit are CLI-tree-only, not silently added to FPM. All paths, configuration and services are private; installation never switches a handler or starts FPM.

Coverage remains **incomplete** until the reports pass. Apache modules, ZTS, separate PECL packages and PEAR workflow are tracked gaps at this stage, not silently claimed available. Vendor-specific system timezone/OpenSSL compatibility patches, global RPM ABI and application behavior are not automatically inherited. The security source pins and the EOL minimal-mitigation versus 8.2 normal-release distinction remain unchanged.
