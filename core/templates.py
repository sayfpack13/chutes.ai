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
            "min_vram_gb_per_gpu": 10,
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
            "min_vram_gb_per_gpu": 12,
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


# Template registry
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "music": get_musicgen_template,
    "image": get_stable_diffusion_template,
    "llm": get_llm_template,
    "speech": get_whisper_template,
    "vision": get_vision_template,
    "tts": get_tts_template,
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
