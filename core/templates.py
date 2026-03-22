"""
Template definitions for common AI chutes.

These templates provide starting points for different types of AI models.
"""

from typing import Dict, Any, List


def get_musicgen_template() -> Dict[str, Any]:
    """Template for MusicGen audio generation."""
    return {
        "name": "musicgen-template",
        "chute_type": "music",
        "tagline": "AI Music Generation with MusicGen",
        "description": """# MusicGen - AI Music Generation

Generate studio-quality music from text descriptions using Meta's MusicGen model.

## Features
- Text-to-music generation from style prompts
- Multiple model sizes (small, medium, large)
- High-quality 32kHz audio output
- Configurable generation parameters
""",
        "model": {
            "source": "huggingface",
            "name": "facebook/musicgen-medium",
            "revision": "main"
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": ["rtx4090", "rtx3090", "a100"]
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl", "ffmpeg", "libsndfile1"],
            "python_packages": [
                "torch",
                "torchaudio",
                "audiocraft",
                "transformers",
                "accelerate"
            ],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {
                "AUDIOCRAFT_CACHE": "/app/models",
                "HF_HOME": "/app/models"
            }
        },
        "api": [
            {
                "path": "/generate",
                "method": "POST",
                "input_schema": "MusicGenerationRequest",
                "output_content_type": "audio/wav",
                "description": "Generate music from text prompt"
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check endpoint"
            }
        ],
        "concurrency": 2,
        "allow_external_egress": True
    }


def get_stable_diffusion_template() -> Dict[str, Any]:
    """Template for Stable Diffusion image generation."""
    return {
        "name": "stable-diffusion-template",
        "chute_type": "image",
        "tagline": "AI Image Generation with Stable Diffusion",
        "description": """# Stable Diffusion - AI Image Generation

Generate high-quality images from text prompts using Stable Diffusion.

## Features
- Text-to-image generation
- Negative prompts support
- Multiple image sizes
- Various samplers (Euler, DPM++, etc.)
""",
        "model": {
            "source": "huggingface",
            "name": "stabilityai/stable-diffusion-xl-base-1.0",
            "revision": "main"
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": ["rtx4090", "rtx3090", "a100"]
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [
                "torch",
                "diffusers>=0.25.0",
                "transformers",
                "accelerate",
                "safetensors",
                "invisible_watermark"
            ],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {
                "HF_HOME": "/app/models"
            }
        },
        "api": [
            {
                "path": "/generate",
                "method": "POST",
                "input_schema": "ImageGenerationRequest",
                "output_content_type": "image/png",
                "description": "Generate image from text prompt"
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check endpoint"
            }
        ],
        "concurrency": 2,
        "allow_external_egress": True
    }


def get_llm_template() -> Dict[str, Any]:
    """Template for LLM text generation using vLLM."""
    return {
        "name": "llm-template",
        "chute_type": "llm",
        "tagline": "Large Language Model API",
        "description": """# LLM Text Generation

OpenAI-compatible text generation API using vLLM backend.

## Features
- OpenAI API compatible
- Streaming response support
- Multiple model options
- Efficient batching
""",
        "model": {
            "source": "huggingface",
            "name": "meta-llama/Llama-3.1-8B-Instruct",
            "revision": "main"
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 24,
            "include": ["rtx4090", "a100", "a10g"]
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [
                "vllm>=0.3.0",
                "transformers",
                "tiktoken"
            ],
            "extra_pip_index": None,
            "env_vars": {
                "HF_HOME": "/app/models"
            }
        },
        "api": [
            {
                "path": "/v1/chat/completions",
                "method": "POST",
                "input_schema": "ChatCompletionRequest",
                "output_content_type": "application/json",
                "stream": True,
                "description": "OpenAI-compatible chat completions"
            },
            {
                "path": "/v1/completions",
                "method": "POST",
                "input_schema": "CompletionRequest",
                "output_content_type": "application/json",
                "description": "OpenAI-compatible text completions"
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check endpoint"
            }
        ],
        "concurrency": 64,
        "allow_external_egress": True
    }


def get_whisper_template() -> Dict[str, Any]:
    """Template for Whisper speech recognition."""
    return {
        "name": "whisper-template",
        "chute_type": "speech",
        "tagline": "Speech Recognition with Whisper",
        "description": """# Whisper - Speech Recognition

Transcribe audio to text using OpenAI's Whisper model.

## Features
- Multi-language support
- Timestamp-level transcription
- Various model sizes
- Word-level timestamps
""",
        "model": {
            "source": "huggingface",
            "name": "openai/whisper-large-v3",
            "revision": "main"
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": ["rtx4090", "rtx3090", "a100", "a10g"]
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl", "ffmpeg"],
            "python_packages": [
                "torch",
                "transformers",
                "accelerate",
                "librosa",
                "soundfile"
            ],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {
                "HF_HOME": "/app/models"
            }
        },
        "api": [
            {
                "path": "/transcribe",
                "method": "POST",
                "input_schema": "TranscriptionRequest",
                "output_content_type": "application/json",
                "description": "Transcribe audio to text"
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check endpoint"
            }
        ],
        "concurrency": 4,
        "allow_external_egress": True
    }


def get_vision_template() -> Dict[str, Any]:
    """Template for vision model (LLaVA)."""
    return {
        "name": "vision-template",
        "chute_type": "vision",
        "tagline": "Vision Language Model with LLaVA",
        "description": """# Vision Language Model

Analyze images and answer questions using vision-language AI.

## Features
- Image understanding
- Visual question answering
- Multiple image inputs
- Detailed descriptions
""",
        "model": {
            "source": "huggingface",
            "name": "llava-hf/llava-1.5-7b-hf",
            "revision": "main"
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": ["rtx4090", "rtx3090", "a100"]
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [
                "torch",
                "transformers",
                "accelerate",
                "Pillow"
            ],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {
                "HF_HOME": "/app/models"
            }
        },
        "api": [
            {
                "path": "/analyze",
                "method": "POST",
                "input_schema": "ImageAnalysisRequest",
                "output_content_type": "application/json",
                "description": "Analyze image and answer question"
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check endpoint"
            }
        ],
        "concurrency": 4,
        "allow_external_egress": True
    }


def get_tts_template() -> Dict[str, Any]:
    """Template for TTS (Text-to-Speech)."""
    return {
        "name": "tts-template",
        "chute_type": "tts",
        "tagline": "Text-to-Speech with Coqui XTTS",
        "description": """# Text-to-Speech

Convert text to natural-sounding speech.

## Features
- Multiple voice cloning
- Natural prosody
- Multiple languages
- Voice reference support
""",
        "model": {
            "source": "huggingface",
            "name": "coqui/XTTS-v2",
            "revision": "main"
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": ["rtx4090", "rtx3090", "a100"]
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl", "ffmpeg", "espeak-ng"],
            "python_packages": [
                "torch",
                "torchaudio",
                "TTS",
                "transformers"
            ],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {
                "HF_HOME": "/app/models",
                "TTS_HOME": "/app/models"
            }
        },
        "api": [
            {
                "path": "/synthesize",
                "method": "POST",
                "input_schema": "TTSSynthesizeRequest",
                "output_content_type": "audio/wav",
                "description": "Convert text to speech"
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check endpoint"
            }
        ],
        "concurrency": 2,
        "allow_external_egress": True
    }


def get_vllm_platform_template() -> Dict[str, Any]:
    """Chutes pre-built vLLM image (no custom Docker Image() in generated code)."""
    return {
        "name": "vllm-platform-template",
        "chute_type": "vllm",
        "tagline": "vLLM — OpenAI-compatible LLM serving",
        "description": """# vLLM on Chutes (pre-built image)

Uses `build_vllm_chute` and Chutes-managed images. Endpoints include `/v1/chat/completions`.
See https://chutes.ai/docs/guides/templates
""",
        "username": "your_username",
        "model": {
            "source": "huggingface",
            "name": "mistralai/Mistral-7B-Instruct-v0.3",
            "revision": "main",
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 24,
            "include": [],
            "exclude": [],
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [],
        },
        "api": [
            {
                "path": "/v1/chat/completions",
                "method": "POST",
                "input_schema": "ChatCompletion",
                "output_content_type": "application/json",
                "description": "OpenAI-compatible chat (provided by vLLM template)",
            }
        ],
        "concurrency": 64,
        "allow_external_egress": False,
        "shutdown_after_seconds": 300,
        "engine_args": {},
        "template_max_instances": 1,
        "template_scaling_threshold": 0.75,
    }


def get_sglang_platform_template() -> Dict[str, Any]:
    """Chutes pre-built SGLang image."""
    return {
        "name": "sglang-platform-template",
        "chute_type": "sglang",
        "tagline": "SGLang — structured LLM serving",
        "description": """# SGLang on Chutes (pre-built image)

Uses `build_sglang_chute`. See https://chutes.ai/docs/guides/templates
""",
        "username": "your_username",
        "model": {
            "source": "huggingface",
            "name": "Qwen/Qwen2.5-7B-Instruct",
            "revision": "main",
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": [],
            "exclude": [],
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [],
        },
        "api": [
            {
                "path": "/v1/chat/completions",
                "method": "POST",
                "input_schema": "ChatCompletion",
                "output_content_type": "application/json",
                "description": "Chat (SGLang template)",
            }
        ],
        "concurrency": 32,
        "allow_external_egress": False,
        "shutdown_after_seconds": 300,
        "engine_args": {},
        "template_max_instances": 1,
        "template_scaling_threshold": 0.75,
    }


def get_diffusion_platform_template() -> Dict[str, Any]:
    """Chutes pre-built diffusion image."""
    return {
        "name": "diffusion-platform-template",
        "chute_type": "diffusion",
        "tagline": "Diffusion — image generation",
        "description": """# Diffusion on Chutes (pre-built image)

Uses `build_diffusion_chute`. Typical endpoint: `POST /generate`.
See https://chutes.ai/docs/guides/templates
""",
        "username": "your_username",
        "model": {
            "source": "huggingface",
            "name": "stabilityai/stable-diffusion-xl-base-1.0",
            "revision": "main",
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 24,
            "include": [],
            "exclude": [],
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [],
        },
        "api": [
            {
                "path": "/generate",
                "method": "POST",
                "input_schema": "GenerationInput",
                "output_content_type": "image/png",
                "description": "Text-to-image",
            }
        ],
        "concurrency": 1,
        "allow_external_egress": False,
        "shutdown_after_seconds": 300,
        "engine_args": {},
        "template_max_instances": 1,
        "template_scaling_threshold": 0.75,
    }


def get_embedding_platform_template() -> Dict[str, Any]:
    """Chutes pre-built embedding image (OpenAI-style /v1/embeddings)."""
    return {
        "name": "embedding-platform-template",
        "chute_type": "embedding",
        "tagline": "Embeddings — text vectors",
        "description": """# Embeddings on Chutes (pre-built image)

Uses `build_embedding_chute`. Endpoint: `POST /v1/embeddings`.
See https://chutes.ai/docs/sdk-reference/templates
""",
        "username": "your_username",
        "model": {
            "source": "huggingface",
            "name": "BAAI/bge-small-en-v1.5",
            "revision": "main",
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": [],
            "exclude": [],
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": [],
        },
        "api": [
            {
                "path": "/v1/embeddings",
                "method": "POST",
                "input_schema": "Embeddings",
                "output_content_type": "application/json",
                "description": "OpenAI-compatible embeddings",
            }
        ],
        "concurrency": 32,
        "allow_external_egress": False,
        "shutdown_after_seconds": 300,
        "engine_args": {},
        "template_max_instances": 1,
        "template_scaling_threshold": 0.75,
        "embedding_pooling_type": "auto",
        "embedding_max_embed_len": 3072000,
        "embedding_enable_chunked_processing": True,
    }


def get_video_template() -> Dict[str, Any]:
    """Scaffold for text-to-video / image-to-video (custom Image() build)."""
    return {
        "name": "video-template",
        "chute_type": "video",
        "tagline": "Video generation",
        "description": """# Video generation

Scaffold for hosted video models (text-to-video, image-to-video). Wire your inference stack and dependencies in the generated module.

See the Chutes example: https://chutes.ai/docs/examples/video-generation
""",
        "username": "your_username",
        "model": {
            "source": "huggingface",
            "name": "Wan-AI/Wan2.1-T2V-14B",
            "revision": "main",
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 24,
            "include": ["rtx4090", "a100"],
            "exclude": [],
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl", "ffmpeg"],
            "python_packages": ["torch", "transformers", "accelerate"],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {"HF_HOME": "/app/models"},
        },
        "api": [
            {
                "path": "/generate",
                "method": "POST",
                "input_schema": "VideoGenerationRequest",
                "output_content_type": "video/mp4",
                "description": "Generate video from prompt or conditioning input",
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check",
            },
        ],
        "concurrency": 1,
        "allow_external_egress": True,
        "shutdown_after_seconds": 300,
    }


def get_moderation_template() -> Dict[str, Any]:
    """Scaffold for text/image moderation or safety classifiers (custom build)."""
    return {
        "name": "moderation-template",
        "chute_type": "moderation",
        "tagline": "Content moderation",
        "description": """# Content moderation

Classifier or safety-model scaffold — implement scoring and policy in your cords.

See Chutes templates overview: https://chutes.ai/docs/templates
""",
        "username": "your_username",
        "model": {
            "source": "huggingface",
            "name": "unitary/toxic-bert",
            "revision": "main",
        },
        "hardware": {
            "gpu_count": 1,
            "min_vram_gb_per_gpu": 16,
            "include": ["rtx4090", "a10g", "a100"],
            "exclude": [],
        },
        "docker": {
            "base_image": "nvidia/cuda:12.1-runtime-ubuntu22.04",
            "python_version": "3.11",
            "system_packages": ["git", "curl"],
            "python_packages": ["torch", "transformers", "accelerate"],
            "extra_pip_index": "https://download.pytorch.org/whl/cu121",
            "env_vars": {"HF_HOME": "/app/models"},
        },
        "api": [
            {
                "path": "/classify",
                "method": "POST",
                "input_schema": "ModerationRequest",
                "output_content_type": "application/json",
                "description": "Classify content for policy / safety",
            },
            {
                "path": "/health",
                "method": "GET",
                "input_schema": "None",
                "output_content_type": "application/json",
                "description": "Health check",
            },
        ],
        "concurrency": 8,
        "allow_external_egress": True,
        "shutdown_after_seconds": 300,
    }


# Template registry
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "music": get_musicgen_template,
    "image": get_stable_diffusion_template,
    "llm": get_llm_template,
    "speech": get_whisper_template,
    "vision": get_vision_template,
    "tts": get_tts_template,
    "vllm": get_vllm_platform_template,
    "sglang": get_sglang_platform_template,
    "diffusion": get_diffusion_platform_template,
    "embedding": get_embedding_platform_template,
    "video": get_video_template,
    "moderation": get_moderation_template,
}


def get_template_names() -> List[str]:
    """Get list of available template names."""
    return list(TEMPLATES.keys())


def get_template(name: str) -> Dict[str, Any]:
    """Get a template by name."""
    if name not in TEMPLATES:
        raise ValueError(f"Template not found: {name}. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[name]()


def get_all_templates() -> Dict[str, Dict[str, Any]]:
    """Get all templates."""
    return {name: getter() for name, getter in TEMPLATES.items()}


def get_template_catalog() -> List[Dict[str, Any]]:
    """
    Grouped template metadata for the dashboard "New chute" UI.

    Groups align with the main **Type** categories on chutes.ai (LLM, image, video, TTS, STT,
    music, embeddings, moderation), plus vision under LLM.

    Each group has: id, label, blurb, options[{key, title, subtitle, stack}].
    Use key ``options`` (not ``items``) so Jinja does not resolve dict ``.items``.
    ``stack`` is ``platform`` (Chutes pre-built image) or ``custom`` (generated Docker Image()).
    """
    catalog: List[Dict[str, Any]] = [
        {
            "id": "llm",
            "label": "LLM",
            "blurb": "Large language models — platform images or your own stack.",
            "options": [
                {
                    "key": "vllm",
                    "title": "vLLM",
                    "subtitle": "Pre-built image — OpenAI-style /v1/chat/completions.",
                    "stack": "platform",
                },
                {
                    "key": "sglang",
                    "title": "SGLang",
                    "subtitle": "Pre-built image — structured generation and batching.",
                    "stack": "platform",
                },
                {
                    "key": "llm",
                    "title": "Custom LLM stack",
                    "subtitle": "Your CUDA image, vLLM/transformers, etc. (custom image build).",
                    "stack": "custom",
                },
                {
                    "key": "vision",
                    "title": "Vision / multimodal",
                    "subtitle": "Image+text API stub — wire LLaVA-style models (custom image build).",
                    "stack": "custom",
                },
            ],
        },
        {
            "id": "image",
            "label": "Image generation",
            "blurb": "Text-to-image and hosted diffusion.",
            "options": [
                {
                    "key": "diffusion",
                    "title": "Diffusion (platform)",
                    "subtitle": "Pre-built diffusion image — typical POST /generate.",
                    "stack": "platform",
                },
                {
                    "key": "image",
                    "title": "Stable Diffusion (custom)",
                    "subtitle": "Diffusers-style stub — you extend inference (custom image build).",
                    "stack": "custom",
                },
            ],
        },
        {
            "id": "video",
            "label": "Video",
            "blurb": "Text-to-video and related pipelines (custom image build).",
            "options": [
                {
                    "key": "video",
                    "title": "Video generation",
                    "subtitle": "Scaffold for T2V / I2V — see Chutes video example in docs.",
                    "stack": "custom",
                },
            ],
        },
        {
            "id": "tts",
            "label": "Text to speech",
            "blurb": "Speech synthesis from text.",
            "options": [
                {
                    "key": "tts",
                    "title": "Text-to-speech",
                    "subtitle": "TTS scaffold e.g. XTTS (custom image build).",
                    "stack": "custom",
                },
            ],
        },
        {
            "id": "speech",
            "label": "Speech to text",
            "blurb": "Transcription and audio understanding.",
            "options": [
                {
                    "key": "speech",
                    "title": "Whisper / speech",
                    "subtitle": "Speech-to-text scaffold (custom image build).",
                    "stack": "custom",
                },
            ],
        },
        {
            "id": "music",
            "label": "Music generation",
            "blurb": "Text-to-music and audio generation.",
            "options": [
                {
                    "key": "music",
                    "title": "MusicGen",
                    "subtitle": "Text-to-music with AudioCraft (custom image build).",
                    "stack": "custom",
                },
            ],
        },
        {
            "id": "embeddings",
            "label": "Embeddings",
            "blurb": "Text vectors for search, RAG, and similarity.",
            "options": [
                {
                    "key": "embedding",
                    "title": "Embeddings",
                    "subtitle": "Pre-built image — OpenAI-style POST /v1/embeddings.",
                    "stack": "platform",
                },
            ],
        },
        {
            "id": "moderation",
            "label": "Content moderation",
            "blurb": "Classifiers and safety models.",
            "options": [
                {
                    "key": "moderation",
                    "title": "Content moderation",
                    "subtitle": "Policy / toxicity scaffold — implement cords (custom image build).",
                    "stack": "custom",
                },
            ],
        },
    ]
    flat = [opt["key"] for group in catalog for opt in group["options"]]
    registered = set(TEMPLATES.keys())
    keys = set(flat)
    if keys != registered:
        missing = sorted(registered - keys)
        extra = sorted(keys - registered)
        raise RuntimeError(
            "Template catalog out of sync with TEMPLATES: "
            f"missing={missing!r} extra={extra!r}"
        )
    return catalog


# Home page: group saved configs by stack (matches chute_type).
_HOME_SECTION_DEFS: List[tuple[str, str, str, frozenset[str]]] = [
    (
        "prebuilt-llm",
        "Pre-built · Text & chat",
        "vLLM and SGLang — Chutes platform images (no custom Dockerfile in code).",
        frozenset({"vllm", "sglang"}),
    ),
    (
        "prebuilt-image",
        "Pre-built · Image generation",
        "Chutes diffusion template — typical POST /generate.",
        frozenset({"diffusion"}),
    ),
    (
        "prebuilt-embed",
        "Pre-built · Embeddings",
        "OpenAI-style POST /v1/embeddings.",
        frozenset({"embedding"}),
    ),
    (
        "custom-stack",
        "Custom Docker stacks",
        "Generated Image() recipes — custom image build on Chutes.",
        frozenset(
            {
                "music",
                "image",
                "llm",
                "speech",
                "vision",
                "tts",
                "custom",
                "video",
                "moderation",
            }
        ),
    ),
]


def group_local_configs_for_home(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Split dashboard home rows into ordered sections for clearer scanning.
    Each section: id, title, blurb, rows.
    """
    errors = [r for r in rows if r.get("error")]
    ok = [r for r in rows if not r.get("error")]
    out: List[Dict[str, Any]] = []
    if errors:
        out.append(
            {
                "id": "errors",
                "title": "Needs attention",
                "blurb": "These config files failed to load — open YAML or remove them.",
                "rows": errors,
            }
        )
    used: set[str] = set()
    for sid, title, blurb, types in _HOME_SECTION_DEFS:
        chunk = [r for r in ok if r.get("type") in types]
        for r in chunk:
            used.add(r["name"])
        if chunk:
            out.append({"id": sid, "title": title, "blurb": blurb, "rows": chunk})
    leftover = [r for r in ok if r["name"] not in used]
    if leftover:
        out.append(
            {
                "id": "other",
                "title": "Other",
                "blurb": "Configs that did not match a known group.",
                "rows": leftover,
            }
        )
    return out
