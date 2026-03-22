# Chutes.ai — configs, dashboard, and MusicGen example

This repo helps you **manage many Chutes** with **YAML configs**, a small **web dashboard**, and a **CLI** that generates Python chute modules and wraps `chutes build` / `chutes deploy`.

> **Note:** Generated modules live in [`chute_packages/`](chute_packages/) (not a top-level `chutes/` folder) so a local `chutes/` directory does not shadow the **`chutes` PyPI package** (`from chutes.chute import Chute`).

## Layout

| Path | Purpose |
|------|---------|
| [`configs/*.yaml`](configs/) | Your chute definitions (one file per chute) |
| [`configs/templates/*.yaml`](configs/templates/) | Starter templates (music, image, LLM, …) |
| [`config.example.yaml`](config.example.yaml) | Annotated example schema |
| [`core/`](core/) | Config models, YAML I/O, codegen, deploy helpers |
| [`dashboard/`](dashboard/) | FastAPI + Jinja UI |
| [`cli.py`](cli.py) | Command-line workflow |
| [`chute_packages/`](chute_packages/) | **Generated** `*_chute.py` files for `chutes build` |
| [`music_gen_chute.py`](music_gen_chute.py) | Hand-written richer MusicGen example (optional) |

## Install

**Dashboard + local manager (recommended first):**

```powershell
cd chutes.ai
pip install -r requirements.txt
```

**Chutes CLI** (for `chutes build` / `chutes deploy` from the UI or `cli.py`) is **not** in `requirements.txt` because on Windows it can pull **`netifaces`**, which needs a C compiler if PyPI has no wheel for your Python version.

```powershell
pip install -r requirements-chutes.txt
chutes auth login
```

If that fails with **Microsoft Visual C++ 14.0 or greater is required**, either:

1. Install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Desktop development with C++), then retry, or  
2. Use **Python 3.11** (often has a pre-built `netifaces` wheel):  
   `py -3.11 -m pip install chutes`

### Windows only? (no Mac / no separate Linux PC)

The Chutes CLI **does not run in normal Windows Python** — you’ll see **`No module named 'pwd'`** because that module exists only on Unix. You still have a good option **on the same Windows machine**:

**[WSL2](https://learn.microsoft.com/en-us/windows/wsl/install)** = Linux **inside** Windows (free, from Microsoft). You are not buying another computer.

1. In **PowerShell (Admin)**: `wsl --install` (or follow the [manual install](https://learn.microsoft.com/en-us/windows/wsl/install-manual) if needed). Reboot if prompted.
2. Open **Ubuntu** from the Start menu, create a user, then update: `sudo apt update && sudo apt upgrade -y`
3. Install Python and your project inside WSL, e.g.:
   ```bash
   cd /mnt/c/Users/YOUR_USER/OneDrive/Desktop/chutes.ai   # path to this repo from Windows drives
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt -r requirements-chutes.txt
   chutes auth login
   ```
4. Run **Build / Publish** from that Ubuntu terminal (`chutes build …`, `chutes deploy …`), or start the dashboard from WSL and open `http://127.0.0.1:8765` in **Windows** Edge/Chrome (it still works).

**On plain Windows without WSL:** you can use this repo’s dashboard for **Prepare** (codegen), **Account**, and **“what’s live”** — but **not** the `chutes` build/deploy steps until WSL or another Linux environment is available.

## Web dashboard

From the repo root (reload **only** `dashboard/` and `core/` so edits under `chute_packages/` do not restart the server in a loop):

```powershell
.\run_dashboard.ps1
```

or:

```powershell
python -m uvicorn dashboard.main:app --reload --port 8765 --reload-dir dashboard --reload-dir core
```

Avoid `uvicorn ... --reload` with **no** `--reload-dir` while working in the repo root, or **Prepare** (codegen) will touch `chute_packages/` and trigger endless reloads.

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). On first run, built-in template YAML files are written under `configs/templates/` if that folder is empty.

### Simple flow (recommended)

1. **Account** (`/settings/account`): paste your Chutes API secret and **Save**. Use **Test connection** if unsure. Advanced users can set API URL / `config.ini` path in the collapsed section.
2. **Home** (`/`): see connection status, **your chutes**, and **what’s live** on Chutes (from the HTTP API). Use **Deploy this chute** for the guided steps.
3. **Deploy** (`/chute/<name>`): **Prepare** → **Build** → **Publish** → **Check status** (plain-language copy; same backend as generate/build/deploy APIs).
4. **New chute** (`/config/new`): pick a template and name; you’re sent to the **Deploy** page for that chute (YAML is still on disk under `configs/`).

**Security:** the dashboard has **no login** — use it on **localhost** only. Secrets live in **`.local/credentials.json`** (gitignored); the app passes **`CHUTES_API_URL`**, **`CHUTES_CONFIG_PATH`**, and **`CHUTES_API_KEY`** to the `chutes` CLI when you build/publish.

### Advanced (YAML, diagnostics, full API browser)

- **Edit YAML** (`/config/<name>/edit`): raw config; banner links back to **Deploy**. Developer shortcuts (generate/build/deploy) are in a collapsed block.
- **Diagnostics** (`/diagnostics`): human-readable CLI list + connection info (replaces opening raw JSON for most users).
- **Advanced platform tools** (`/platform/advanced`): list chutes/images, inspector, share/delete, pricing, etc. The old URL **`/platform`** redirects here.

API reference: [overview](https://chutes.ai/docs/api-reference/overview), [General](https://chutes.ai/docs/api-reference/general), [Chutes](https://chutes.ai/docs/api-reference/chutes), [Images](https://chutes.ai/docs/api-reference/images), [Users](https://chutes.ai/docs/api-reference/users).

### Having trouble

- Expand **Having trouble? (logs)** on Home to fetch **`chutes` logs** via `GET /api/cli/logs`.
- **Diagnostics** for PATH / `chutes chutes list` output.

## CLI

```powershell
# Write all built-in templates (music, image, llm, speech, vision, tts) to configs/templates/
python cli.py seed-templates

# New config from a built-in template key: music | image | llm | speech | vision | tts
python cli.py new music my-song --username your_username

# Generate Python into chute_packages/
python cli.py generate music-gen
python cli.py generate --all

# Build / deploy (run inside chute_packages; module name is <slug>_chute)
cd chute_packages
chutes build music_gen_chute:chute --wait
chutes deploy music_gen_chute:chute --accept-fee
```

Or from repo root:

```powershell
python cli.py build music-gen
python cli.py deploy music-gen
```

```powershell
python cli.py status
python cli.py logs <chute-name-on-platform> --tail 50
python cli.py get <chute-name-on-platform>
```

## YAML config

Each file describes **username**, **chute_type** (`music`, `image`, `llm`, `speech`, `vision`, `tts`, `custom`), **model**, **hardware** (`NodeSelector`), **docker** (base image, pip packages, env), and **api** endpoints (used for documentation; codegen uses **chute_type**).

See [`config.example.yaml`](config.example.yaml) and [`configs/music-gen.yaml`](configs/music-gen.yaml).

### Code generation behavior

- **`music`**: MusicGen-style chute with `/generate` (WAV) and `/health`.
- **Other types**: **stubs** with TODOs — implement `on_startup` and cords before production.
- **`custom`**: minimal `/echo` + `/health`.

After editing YAML, run **`python cli.py generate <name>`** again.

## Hand-written MusicGen example

[`music_gen_chute.py`](music_gen_chute.py) is a fuller example (extra endpoints, melody hook, etc.). You can keep using it directly, or drive a simpler flow via **`configs/music-gen.yaml`** + codegen.

Example request against a deployed music chute:

```bash
curl -X POST "https://your_username-music-gen.chutes.ai/generate" ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"upbeat electronic music\", \"duration\": 10, \"model\": \"medium\"}" ^
  --output out.wav
```

## Troubleshooting

- **Stopping uvicorn (Ctrl+C)** can print `KeyboardInterrupt` / `CancelledError` in the log; that is normal when using `--reload`.

- **`chutes` not found:** install with `pip install -r requirements-chutes.txt` (see **Install** above) and ensure `chutes` is on `PATH`.
- **402 on deploy:** pass `--accept-fee` (dashboard deploy already does).
- **Wrong CLI subcommands:** this project assumes patterns like `chutes chutes list` per [Chutes docs](https://chutes.ai/docs/cli/deploy). If your CLI version differs, adjust [`core/deployer.py`](core/deployer.py).

## Resources

- [Chutes documentation](https://chutes.ai/docs)
- [MusicGen / AudioCraft](https://github.com/facebookresearch/audiocraft)
