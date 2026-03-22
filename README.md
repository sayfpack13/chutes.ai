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

```powershell
cd chutes.ai
pip install -r requirements.txt
pip install chutes
chutes auth login
```

## Web dashboard

From the repo root:

```powershell
uvicorn dashboard.main:app --reload --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). On first run, built-in template YAML files are written under `configs/templates/` if that folder is empty.

You can **list configs**, **create** from a template, **edit raw YAML**, and trigger **Generate / Build / Deploy** (Build/Deploy call your local `chutes` CLI).

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

- **`chutes` not found:** install with `pip install chutes` and ensure it is on `PATH`.
- **402 on deploy:** pass `--accept-fee` (dashboard deploy already does).
- **Wrong CLI subcommands:** this project assumes patterns like `chutes chutes list` per [Chutes docs](https://chutes.ai/docs/cli/deploy). If your CLI version differs, adjust [`core/deployer.py`](core/deployer.py).

## Resources

- [Chutes documentation](https://chutes.ai/docs)
- [MusicGen / AudioCraft](https://github.com/facebookresearch/audiocraft)
