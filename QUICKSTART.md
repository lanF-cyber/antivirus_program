# ScanBox Quickstart

This quickstart is for the unpacked ScanBox zip artifact. It does not require a repository checkout.

## Minimal first run

Use any local Python 3.11+ interpreter for the initial virtual environment creation.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Create a temporary local override for a YARA-only first run:

```toml
[engines.clamav]
enabled = false

[engines.capa]
enabled = false
```

Write that content to:

```text
config/scanbox.local.toml
```

Then verify the unpacked artifact and run the minimal scan path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run_scanbox.ps1 -PythonExe .\.venv\Scripts\python.exe scan .\README.md
```

## Support Boundary

The supported operator path assumes a working `venv`, a working `pip`, and access to the runtime dependency source used by `requirements.txt`.

The `config/scanbox.local.toml` file in this quickstart is a temporary first-run override only. Maintainer-side validation fallbacks are not part of the operator contract.

## What this first run proves

- the unpacked artifact layout is internally usable
- runtime Python dependencies are installed
- the bundled YARA rules are available
- the operator-facing launcher can run `scanbox` without a repository checkout

## What this first run does not do

- it does not install ClamAV
- it does not install capa
- it does not download the ClamAV database
- it does not create workstation-local external dependency wiring for you

## Full external engine setup

For pinned ClamAV, capa, database, and local override guidance, continue with:

- [docs/dependencies.md](docs/dependencies.md)

The temporary `config/scanbox.local.toml` used here is for first-run validation only. It is not part of the static artifact contents.
