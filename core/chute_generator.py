"""
Generate deployable Chute Python modules from ChuteConfig (YAML).

Output is written under chute_packages/ (not ``chutes/``) to avoid shadowing
the installed ``chutes`` SDK when running tools from the repo root.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .config_manager import ChuteConfig, DockerImageConfig, HardwareConfig


def _safe_module_name(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "chute"


def _image_registry_fields(cfg: ChuteConfig) -> tuple[str, str, str]:
    d = cfg.docker
    img_name = d.image_name or _safe_module_name(cfg.name)
    tag = d.image_tag or "1.0.0"
    readme = d.image_readme or cfg.tagline
    return img_name, tag, readme


def _apt_line(packages: List[str]) -> str:
    pkgs = " ".join(packages) if packages else "git curl"
    return f"apt-get update && apt-get install -y {pkgs} && rm -rf /var/lib/apt/lists/*"


def _pip_torch_block(extra_index: str | None) -> str:
    if extra_index:
        return f'''
    .run_command("""
        pip install --no-cache-dir torch torchvision torchaudio \\
        --index-url {extra_index}
    """)'''
    return '''
    .run_command("""
        pip install --no-cache-dir torch torchvision torchaudio
    """)'''


def _pip_packages_block(packages: List[str]) -> str:
    if not packages:
        return ""
    joined = " \\\n        ".join(packages)
    return f'''
    .run_command("""
        pip install --no-cache-dir \\
        {joined}
    """)'''


def _env_block(env: dict[str, str]) -> str:
    lines: List[str] = []
    for k, v in env.items():
        lines.append(f'    .with_env({repr(k)}, {repr(v)})')
    return "\n".join(lines)


def build_image_python(cfg: ChuteConfig) -> str:
    d: DockerImageConfig = cfg.docker
    img_name, tag, readme = _image_registry_fields(cfg)
    apt = _apt_line(d.system_packages)
    pyver = d.python_version
    env_lines = _env_block(d.env_vars)
    torch_blk = _pip_torch_block(d.extra_pip_index)
    pip_blk = _pip_packages_block(d.python_packages)

    parts = [
        "from chutes.image import Image",
        "",
        "image = (",
        f"    Image(",
        f"        username={repr(cfg.username)},",
        f"        name={repr(img_name)},",
        f"        tag={repr(tag)},",
        f"        readme={repr(readme)},",
        f"    )",
        f"    .from_base({repr(d.base_image)})",
        '    .set_user("root")',
        f"    .run_command({repr(apt)})",
        f'    .with_python({repr(pyver)})',
    ]
    parts.append(torch_blk)
    if pip_blk.strip():
        parts.append(pip_blk)
    if env_lines:
        parts.append(env_lines)
    parts.extend(
        [
            '    .run_command("mkdir -p /app/models")',
            '    .set_workdir("/app")',
            '    .set_user("chutes")',
            ")",
        ]
    )
    return "\n".join(parts)


def build_node_selector_python(hw: HardwareConfig) -> str:
    d = hw.to_node_selector_dict()
    parts = [
        f"gpu_count={d['gpu_count']}",
        f"min_vram_gb_per_gpu={d['min_vram_gb_per_gpu']}",
    ]
    if d.get("include"):
        parts.append(f"include={repr(d['include'])}")
    if d.get("exclude"):
        parts.append(f"exclude={repr(d['exclude'])}")
    return "NodeSelector(" + ", ".join(parts) + ")"


def _chute_block(cfg: ChuteConfig) -> str:
    ns = build_node_selector_python(cfg.hardware)
    return f"""
from chutes.chute import Chute, NodeSelector

chute = Chute(
    username={repr(cfg.username)},
    name={repr(cfg.name)},
    tagline={repr(cfg.tagline)},
    readme={repr(cfg.description)},
    image=image,
    node_selector={ns},
    concurrency={cfg.concurrency},
    allow_external_egress={repr(cfg.allow_external_egress)},
    shutdown_after_seconds={cfg.shutdown_after_seconds},
)
"""


def generate_music_chute(cfg: ChuteConfig) -> str:
    model_id = cfg.model.name
    primary_path = "/generate"
    for ep in cfg.api:
        if ep.path not in ("/health",):
            primary_path = ep.path
            break

    header = f'''"""
Auto-generated MusicGen chute ({cfg.name}).
Model: {model_id}
Edit configs/{cfg.name}.yaml and re-run generate.
"""
import io
import uuid
from typing import Optional

import torch
import torchaudio
from fastapi import HTTPException
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator

'''

    schemas = f'''
class MusicGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    duration: int = Field(default=10, ge=5, le=30)
    model: str = Field(default="medium")
    guidance_scale: float = Field(default=3.0, ge=1.0, le=10.0)
    seed: Optional[int] = None

    @field_validator("model")
    @classmethod
    def _m(cls, v: str) -> str:
        v = v.lower()
        if v not in ("small", "medium", "large"):
            raise ValueError("model must be small|medium|large")
        return v

    @field_validator("prompt")
    @classmethod
    def _p(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("empty prompt")
        return v


class HealthStatus(BaseModel):
    status: str
    model_loaded: bool
    gpu_available: bool
'''

    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)

    body = f'''
{image_py}

{chute_py}

MODEL_IDS = {{
    "small": "facebook/musicgen-small",
    "medium": "facebook/musicgen-medium",
    "large": "facebook/musicgen-large",
}}

DEFAULT_HF_ID = {repr(model_id)}


@chute.on_startup()
async def load_model(self):
    from audiocraft.models import MusicGen

    self.torch = torch
    self.models = {{}}
    # Preload: match YAML model.id to small/medium/large when possible, else warm up medium.
    loaded = False
    for k, mid in MODEL_IDS.items():
        if mid == DEFAULT_HF_ID:
            logger.info("Loading MusicGen %s (%s)", k, mid)
            self.models[k] = MusicGen.get_pretrained(mid)
            loaded = True
            break
    if not loaded:
        logger.info("Loading MusicGen medium (%s)", MODEL_IDS["medium"])
        self.models["medium"] = MusicGen.get_pretrained(MODEL_IDS["medium"])
    self.device = "cuda" if torch.cuda.is_available() else "cpu"


@chute.cord(
    public_api_path={repr(primary_path)},
    public_api_method="POST",
    stream=False,
    output_content_type="audio/wav",
)
async def generate_music(self, data: MusicGenerationRequest) -> Response:
    from audiocraft.models import MusicGen

    key = data.model
    if key not in self.models:
        mid = MODEL_IDS.get(key)
        if not mid:
            raise HTTPException(status_code=400, detail="Unknown model size")
        self.models[key] = MusicGen.get_pretrained(mid)
    model = self.models[key]
    model.set_generation_params(duration=data.duration, guidance_scale=data.guidance_scale)
    if data.seed is not None:
        torch.manual_seed(data.seed)
    try:
        with torch.no_grad():
            wav = model.generate(descriptions=[data.prompt], progress=False)
        buf = io.BytesIO()
        torchaudio.save(buf, wav[0].cpu(), sample_rate=32000, format="wav")
        buf.seek(0)
        aid = str(uuid.uuid4())[:8]
        return Response(
            content=buf.read(),
            media_type="audio/wav",
            headers={{"Content-Disposition": "attachment; filename=musicgen_" + aid + ".wav"}},
        )
    except Exception as exc:
        logger.exception("generate failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> HealthStatus:
    loaded = bool(getattr(self, "models", None))
    gpu = torch.cuda.is_available()
    st = "healthy" if loaded and gpu else "degraded"
    return HealthStatus(status=st, model_loaded=loaded, gpu_available=gpu)
'''
    return header + schemas + body


def generate_image_stub(cfg: ChuteConfig) -> str:
    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)
    return f'''"""
Auto-generated image chute stub ({cfg.name}).
HF model: {cfg.model.name}
Customize inference (diffusers) before production deploy.
"""
from pydantic import BaseModel, Field
from fastapi import HTTPException

{image_py}

{chute_py}


class ImageGenRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    width: int = Field(default=1024, ge=256, le=1024)
    height: int = Field(default=1024, ge=256, le=1024)


@chute.on_startup()
async def load_model(self):
    # TODO: load diffusers pipeline for {cfg.model.name}
    self.pipeline = None


@chute.cord(
    public_api_path="/generate",
    public_api_method="POST",
    output_content_type="application/json",
)
async def generate(self, data: ImageGenRequest) -> dict:
    if self.pipeline is None:
        raise HTTPException(
            status_code=501,
            detail="Stub: implement diffusers load in on_startup for this chute.",
        )
    return {{"status": "not_implemented"}}


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> dict:
    return {{"status": "ok", "stub": True}}
'''


def generate_llm_stub(cfg: ChuteConfig) -> str:
    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)
    return f'''"""
Auto-generated LLM chute stub ({cfg.name}).
HF model: {cfg.model.name}
For production, prefer official Chutes vLLM/sglang templates when possible.
"""
from pydantic import BaseModel, Field
from fastapi import HTTPException

{image_py}

{chute_py}


class ChatRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    max_tokens: int = Field(default=256, ge=1, le=4096)


@chute.on_startup()
async def load_model(self):
    # TODO: wire vLLM / transformers for {cfg.model.name}
    self.engine = None


@chute.cord(
    public_api_path="/v1/chat/completions",
    public_api_method="POST",
    output_content_type="application/json",
)
async def chat(self, data: ChatRequest) -> dict:
    raise HTTPException(
        status_code=501,
        detail="Stub: implement LLM inference (e.g. vLLM) for this chute.",
    )


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> dict:
    return {{"status": "ok", "stub": True}}
'''


def generate_speech_stub(cfg: ChuteConfig) -> str:
    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)
    return f'''"""
Auto-generated speech (ASR) stub ({cfg.name}).
HF model: {cfg.model.name}
"""
from pydantic import BaseModel, Field
from fastapi import HTTPException

{image_py}

{chute_py}


class TranscribeRequest(BaseModel):
    audio_b64: str = Field(..., min_length=10)


@chute.on_startup()
async def load_model(self):
    # TODO: load whisper / ASR for {cfg.model.name}
    self.processor = None


@chute.cord(
    public_api_path="/transcribe",
    public_api_method="POST",
    output_content_type="application/json",
)
async def transcribe(self, data: TranscribeRequest) -> dict:
    raise HTTPException(
        status_code=501,
        detail="Stub: implement Whisper (or your ASR) in on_startup.",
    )


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> dict:
    return {{"status": "ok", "stub": True}}
'''


def generate_vision_stub(cfg: ChuteConfig) -> str:
    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)
    return f'''"""
Auto-generated vision-language stub ({cfg.name}).
HF model: {cfg.model.name}
"""
from pydantic import BaseModel, Field
from fastapi import HTTPException

{image_py}

{chute_py}


class VisionRequest(BaseModel):
    image_b64: str = Field(..., min_length=10)
    prompt: str = Field(default="Describe the image.")


@chute.on_startup()
async def load_model(self):
    # TODO: load VLM for {cfg.model.name}
    self.model = None


@chute.cord(
    public_api_path="/analyze",
    public_api_method="POST",
    output_content_type="application/json",
)
async def analyze(self, data: VisionRequest) -> dict:
    raise HTTPException(
        status_code=501,
        detail="Stub: implement VLM inference in on_startup.",
    )


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> dict:
    return {{"status": "ok", "stub": True}}
'''


def generate_tts_stub(cfg: ChuteConfig) -> str:
    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)
    return f'''"""
Auto-generated TTS stub ({cfg.name}).
HF model: {cfg.model.name}
"""
from pydantic import BaseModel, Field
from fastapi import HTTPException

{image_py}

{chute_py}


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


@chute.on_startup()
async def load_model(self):
    # TODO: load TTS for {cfg.model.name}
    self.tts = None


@chute.cord(
    public_api_path="/synthesize",
    public_api_method="POST",
    output_content_type="application/json",
)
async def synthesize(self, data: TTSRequest) -> dict:
    raise HTTPException(
        status_code=501,
        detail="Stub: implement TTS in on_startup.",
    )


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> dict:
    return {{"status": "ok", "stub": True}}
'''


def generate_custom_stub(cfg: ChuteConfig) -> str:
    image_py = build_image_python(cfg)
    chute_py = _chute_block(cfg)
    return f'''"""
Auto-generated custom stub ({cfg.name}).
HF model config present but chute_type is custom — implement your cords.
"""
from pydantic import BaseModel, Field

{image_py}

{chute_py}


class EchoBody(BaseModel):
    message: str = Field(default="hello")


@chute.cord(
    public_api_path="/echo",
    public_api_method="POST",
    output_content_type="application/json",
)
async def echo(self, data: EchoBody) -> dict:
    return {{"echo": data.message}}


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> dict:
    return {{"status": "ok", "custom": True}}
'''


def generate_python_source(cfg: ChuteConfig) -> str:
    t = cfg.chute_type
    if t == "music":
        return generate_music_chute(cfg)
    if t == "image":
        return generate_image_stub(cfg)
    if t == "llm":
        return generate_llm_stub(cfg)
    if t == "speech":
        return generate_speech_stub(cfg)
    if t == "vision":
        return generate_vision_stub(cfg)
    if t == "tts":
        return generate_tts_stub(cfg)
    return generate_custom_stub(cfg)


def write_chute_module(
    cfg: ChuteConfig,
    repo_root: Path | str,
    out_subdir: str = "chute_packages",
) -> Path:
    root = Path(repo_root)
    out_dir = root / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    mod = _safe_module_name(cfg.name) + "_chute"
    path = out_dir / f"{mod}.py"
    src = generate_python_source(cfg)
    banner = (
        "# -*- coding: utf-8 -*-\n"
        "# Generated by chutes-ai-manager. Re-run `python cli.py generate ...` after YAML edits.\n\n"
    )
    path.write_text(banner + src, encoding="utf-8")
    return path


def module_ref(cfg: ChuteConfig, out_subdir: str = "chute_packages") -> str:
    mod = _safe_module_name(cfg.name) + "_chute"
    return f"{mod}:chute"
