# External Dependencies

ScanBox keeps Python runtime dependencies separate from external security tooling. No dependency should be fetched implicitly at runtime.

## Operator-facing dependency path

For the unpacked zip artifact, use this order:

1. Create a local virtual environment.
2. Install runtime Python packages from `requirements.txt`.
3. Use the bundled YARA rules for the first run.
4. If you need full engine coverage, add ClamAV and capa explicitly.
5. Store workstation-specific overrides in `config/scanbox.local.toml`.
6. Re-run `scripts/verify_env.ps1`.

Important boundary:

- `requirements.txt` is runtime-only
- it does not include pytest, lint, or editable-install semantics
- ClamAV, capa, and the ClamAV database remain explicit operator-provided dependencies

## Runtime Python packages

These are the runtime Python dependencies used by the unpacked artifact:

- `pydantic==2.12.5`
- `yara-python==4.5.2`

## Bundled rules

The artifact already includes:

- `rules/yara/bundled/`
  - project-maintained starter YARA rules
- `rules/capa/bundled/`
  - vendored pinned `capa-rules v9.3.0` snapshot

That means a YARA-only first run does not require any additional rule download.

## ClamAV operator setup

- Pinned version: `1.4.3`
- Source: [official release](https://github.com/Cisco-Talos/clamav/releases/tag/clamav-1.4.3)
- Preferred Windows artifact: `clamav-1.4.3.win.x64.zip`
- Companion signature artifact: `clamav-1.4.3.win.x64.zip.sig`
- Official SHA256:
  - `5c86a6ed17e45e5c14c9c7c7b58cfaabcdee55a195991439bb6b6c6618827e6c`

Operator steps:

1. Download the pinned official Windows zip explicitly.
2. Verify the SHA256.
3. Extract it to a workstation-local directory.
4. Update `config/scanbox.local.toml` with the real `clamscan.exe` path.
5. Copy `config/clamav/freshclam.conf` to `config/clamav/freshclam.local.conf`.
6. Update `DatabaseDirectory` in `freshclam.local.conf`.
7. Run `freshclam.exe` explicitly to initialize the database.
8. Re-run `scripts/verify_env.ps1`.

## capa operator setup

- Pinned version: `9.3.1`
- Source: [official release](https://github.com/mandiant/capa/releases/tag/v9.3.1)
- Preferred Windows artifact: `capa-v9.3.1-windows.zip`
- Official SHA256:
  - `d6e05a7c0c2171c4e476032d205267c03787db2ecedb7717e45a64b9f5895023`

Operator steps:

1. Download the pinned official Windows zip explicitly.
2. Verify the SHA256.
3. Extract it to a workstation-local directory.
4. Update `config/scanbox.local.toml` with the real `capa.exe` path.
5. Re-run `scripts/verify_env.ps1`.

## Local override expectation

Use `config/scanbox.local.toml` for workstation-specific paths such as:

- `engines.clamav.executable`
- `engines.clamav.database_dir`
- `engines.capa.executable`

Use `config/clamav/freshclam.local.conf` for workstation-specific `freshclam` settings.

These local override files are not part of the static artifact contents.

## Maintainer and workstation-specific notes

### Python packages

- `pytest==9.0.2`
  - Source: official GitHub release page
  - URL: <https://github.com/pytest-dev/pytest/releases/tag/v9.0.2>
- `pytest-mock==3.15.1`
  - Source: official GitHub release page
  - URL: <https://github.com/pytest-dev/pytest-mock/releases/tag/v3.15.1>
- `pytest-timeout==2.3.1`
  - Source: official GitHub repository tags
  - URL: <https://github.com/pytest-dev/pytest-timeout/tags>

### ClamAV integration notes

- Current integration facts:
  - official release metadata is reachable through the GitHub API
  - the small `.sig` asset is downloadable through the GitHub assets API
  - the large Windows zip asset was not reliably downloadable from this environment over the release asset/CDN download path
  - the official Windows zip was therefore acquired manually and validated against the pinned SHA256 before local use
- Current validated local wiring on this workstation uses:
  - repository default config: `config/scanbox.toml`
  - workstation override config: `config/scanbox.local.toml`
  - executable override: `C:\Users\Lancelot\Desktop\瀹夎鍖匼clamav-1.4.3.win.x64\clamscan.exe`
  - freshclam local config: `config/clamav/freshclam.local.conf`
  - database_dir: `C:\Users\Lancelot\Desktop\antivirus_program\.local-tools\clamav\db`
- Current download blocker:
  - this environment can reach `api.github.com`, but the final GitHub release asset download path for the Windows zip is not consistently usable
  - if you need to retry, first switch to a proxy/node rule that handles GitHub release assets well before attempting the large zip again

### capa integration notes

- Current integration facts:
  - the official release metadata is reachable through the GitHub API when the dead local proxy variables are cleared
  - the browser download path was unstable from this environment, but the GitHub assets API succeeded for the pinned Windows artifact
- Current validated local wiring on this workstation uses:
  - workstation override config: `config/scanbox.local.toml`
  - executable override: `.local-tools\capa\capa-v9.3.1\capa.exe`

### capa-rules notes

- Pinned reference: `v9.3.0`
- Source: [official release](https://github.com/mandiant/capa-rules/releases/tag/v9.3.0)
- Intended repository path: `rules/capa/bundled/`
- Current repository status: `vendored`
- Vendored into this repository on: `2026-04-15T01:11:12Z`
- Current rule count: `1016`

## Update policy

- Downloads and updates must be explicit user actions
- Prefer official release artifacts or official repository clones at pinned refs
- Do not track `main` or `master`
- For ClamAV on Windows, prefer manually downloading the pinned official zip, verifying the SHA256 above, extracting it locally, keeping `config/scanbox.toml` generic, and storing workstation-specific paths in `config/scanbox.local.toml`
- For this repository, the official `freshclam.exe` should be driven with `config/clamav/freshclam.local.conf`; `config/clamav/freshclam.conf` is the committed template
