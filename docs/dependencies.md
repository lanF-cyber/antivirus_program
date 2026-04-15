# External Dependencies

ScanBox v1 intentionally separates Python package dependencies from external security tooling. No dependency should be fetched implicitly during runtime.

## Python packages

- `pydantic==2.12.5`
  - Source: official GitHub release page
  - URL: <https://github.com/pydantic/pydantic/releases/tag/v2.12.5>
- `yara-python==4.5.2`
  - Source: official GitHub release page
  - URL: <https://github.com/VirusTotal/yara-python/releases/tag/v4.5.2>
- `pytest==9.0.2`
  - Source: official GitHub release page
  - URL: <https://github.com/pytest-dev/pytest/releases/tag/v9.0.2>
- `pytest-mock==3.15.1`
  - Source: official GitHub release page
  - URL: <https://github.com/pytest-dev/pytest-mock/releases/tag/v3.15.1>
- `pytest-timeout==2.3.1`
  - Source: official GitHub repository tags
  - URL: <https://github.com/pytest-dev/pytest-timeout/tags>

## External engines and rules

- ClamAV
  - Pinned version: `1.4.3`
  - Source: official GitHub release page
  - URL: <https://github.com/Cisco-Talos/clamav/releases/tag/clamav-1.4.3>
  - Preferred Windows artifact for this repo: `clamav-1.4.3.win.x64.zip`
  - Companion signature artifact: `clamav-1.4.3.win.x64.zip.sig`
  - Official SHA256 for `clamav-1.4.3.win.x64.zip`: `5c86a6ed17e45e5c14c9c7c7b58cfaabcdee55a195991439bb6b6c6618827e6c`
  - Current integration facts:
    - official release metadata is reachable through the GitHub API
    - the small `.sig` asset is downloadable through the GitHub assets API
    - the large Windows zip asset was not reliably downloadable from this environment over the release asset/CDN download path
    - the official Windows zip was therefore acquired manually and validated against the pinned SHA256 before local use
    - the current validated local wiring on this workstation uses:
      - repository default config: `config/scanbox.toml`
      - workstation override config: `config/scanbox.local.toml`
      - executable override: `C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\clamscan.exe`
      - freshclam local config: `config/clamav/freshclam.local.conf`
      - database_dir: `C:\Users\Lancelot\Desktop\antivirus_program\.local-tools\clamav\db`
  - Current download blocker:
    - this environment can reach `api.github.com`, but the final GitHub release asset download path for the Windows zip is not consistently usable
    - if you need to retry, first switch to a proxy/node rule that handles GitHub release assets well before attempting the large zip again
- capa
  - Pinned version: `9.3.1`
  - Source: official GitHub release page
  - URL: <https://github.com/mandiant/capa/releases/tag/v9.3.1>
  - Preferred Windows artifact for this repo: `capa-v9.3.1-windows.zip`
  - Official SHA256 for `capa-v9.3.1-windows.zip`: `d6e05a7c0c2171c4e476032d205267c03787db2ecedb7717e45a64b9f5895023`
  - Current integration facts:
    - the official release metadata is reachable through the GitHub API when the dead local proxy variables are cleared
    - the browser download path was unstable from this environment, but the GitHub assets API succeeded for the pinned Windows artifact
    - the current validated local wiring on this workstation uses:
      - workstation override config: `config/scanbox.local.toml`
      - executable override: `.local-tools\capa\capa-v9.3.1\capa.exe`
- capa-rules
  - Pinned reference: `v9.3.0`
  - Source: official GitHub release page
  - URL: <https://github.com/mandiant/capa-rules/releases/tag/v9.3.0>
  - Intended repository path: `rules/capa/bundled/`
  - Current repository status: `vendored`
  - Vendored into this repository on: `2026-04-15T01:11:12Z`
  - Current rule count: `1016`

## Bundled rules

- `rules/yara/bundled/`
  - Project-maintained starter rules for harmless local testing
- `rules/capa/bundled/`
  - Pinned official `capa-rules v9.3.0` snapshot vendored into the repository
  - `rule_count` is tracked against `.yml` / `.yaml` rule files only and excludes hidden directories such as `.github/`

## Update policy

- Downloads and updates must be explicit user actions
- Prefer official release artifacts or official repository clones at pinned refs
- Do not track `main` or `master`
- For ClamAV on Windows, prefer manually downloading the pinned official zip, verifying the SHA256 above, extracting it locally, keeping `config/scanbox.toml` generic, and storing workstation-specific paths in `config/scanbox.local.toml`
- For this repository, the official `freshclam.exe` should be driven with `config/clamav/freshclam.local.conf`; `config/clamav/freshclam.conf` is the committed template
