# Source and package contents

The source tree contains application code, build scripts, pinned dependency
locks, maintained tests, documentation and desktop assets. Local runtime,
models, user data, logs and build outputs are not source inputs.

Ignore rules in this clone are local configuration in `.git/info/exclude`.
They are not supplied to other clones and do not filter Flatpak contents or
remove files from Git history.

## Package policy

`flatpak/publication-files.json` lists build inputs, application files,
desktop targets and component SHA-256 hashes. Review the relevant lists when
adding or removing files.

`scripts/fresh-inputs.py` rejects unexpected files, missing inputs and symlinks
before creating the source snapshot. Generated files and local-only materials
listed under `excluded_source` are not copied. Build and cache directories are
excluded separately.

`scripts/install-fresh.py` validates inputs before writing application output.
Only listed application files and verified components are installed. Tests,
project documentation and local reports do not belong in `/app`. Dependency
license and notice files are retained.

After the builder finishes, `scripts/build-fresh.sh` replaces host work-directory
paths in `/app/manifest.json` with `@WORK@`. The expanded manifest stays in the
local work directory.

Check the complete payload, including dependencies and symlinks, then compare
it with an independently imported Flatpak bundle. An inventory of staging
alone does not verify an exported bundle.
