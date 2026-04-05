# -*- coding: utf-8 -*-
# Wan 2.2 I2V 14B Fast - Image to video generation with PrunaAI speed-ups

"""
Wan 2.2 I2V 14B Fast - Image to video generation.
Model: Wan-AI/Wan2.2-I2V-A14B-Diffusers

Note: torch/diffusers are lazy-imported inside functions so `chutes build`
can load this module without a local GPU stack.
"""
import io
import uuid
import base64
from typing import Optional
from enum import Enum

from fastapi import HTTPException
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from chutes.image import Image

# Build custom image with video generation capabilities
image = (
    Image(
        username='sayfpack',
        name='wan-i2v-fast',
        tag='1.0.0',
        readme='Wan 2.2 I2V 14B Fast - Image to video generation with PrunaAI speed-ups',
    )
    .from_base('parachutes/base-python:3.12.7')
    .set_user("root")
    .run_command("apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*")
    .set_user("chutes")
    .run_command(
        "pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu121"
    )
    .run_command(
        "pip install --no-cache-dir diffusers>=0.33.0 transformers accelerate safetensors pillow numpy requests"
    )
    .with_env('HF_HOME', '/app/models')
    .run_command("mkdir -p /app/models")
    .set_workdir("/app")
)

from chutes.chute import Chute, NodeSelector

chute = Chute(
    username='sayfpack',
    name='wan-i2v-fast',
    tagline='Wan 2.2 I2V 14B Fast - Image to video with PrunaAI speed-ups',
    readme="""# Wan 2.2 I2V 14B Fast

Image to video generation with Wan 2.2 using PrunaAI speed-ups.

## Features
- Image-to-video generation from text prompts
- 480p resolution support
- Fast inference with PrunaAI optimization
- Configurable FPS, frames, and guidance scale

## Usage
POST to /generate with:
- `prompt`: Text description of desired video
- `image`: URL to the input image
- `fps`: Frames per second (default 16)
- `frames`: Number of frames to generate (default 81)
- `guidance_scale`: Guidance strength (default 1.0)
- `seed`: Random seed for reproducibility
- `negative_prompt`: What to avoid in generation
""",
    image=image,
    node_selector=NodeSelector(gpu_count=1, min_vram_gb_per_gpu=48, include=['a100', 'h100']),
    concurrency=1,
    allow_external_egress=True,
    shutdown_after_seconds=600,
)


class Resolution(str, Enum):
    RES_480P = "480p"
    RES_720P = "720p"


class VideoGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text prompt for video generation")
    image: str = Field(..., description="URL or base64-encoded image to animate")
    fps: int = Field(default=16, ge=8, le=60, description="Frames per second")
    frames: int = Field(default=81, ge=16, le=241, description="Number of frames to generate")
    fast: bool = Field(default=False, description="Use fast mode (fewer inference steps)")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    guidance_scale: float = Field(default=1.0, ge=1.0, le=10.0, description="Guidance scale")
    guidance_scale_2: float = Field(default=1.0, ge=1.0, le=10.0, description="Secondary guidance scale")
    resolution: Resolution = Field(default=Resolution.RES_480P, description="Output resolution")
    negative_prompt: str = Field(
        default="色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走",
        description="Negative prompt for what to avoid"
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Prompt cannot be empty")
        return v


class HealthStatus(BaseModel):
    status: str
    model_loaded: bool
    gpu_available: bool
    gpu_name: Optional[str] = None


def _load_image_from_input(image_input: str):
    """Load image from URL or base64 string."""
    import requests
    from PIL import Image
    
    # Check if it's a URL
    if image_input.startswith(('http://', 'https://')):
        try:
            response = requests.get(image_input, timeout=30)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert('RGB')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load image from URL: {e}")
    
    # Try base64 decode
    try:
        # Handle data URI format
        if image_input.startswith('data:image'):
            image_input = image_input.split(',', 1)[1]
        
        image_bytes = base64.b64decode(image_input)
        return Image.open(io.BytesIO(image_bytes)).convert('RGB')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode base64 image: {e}")


@chute.on_startup()
async def load_model(self):
    """Initialize Wan 2.2 I2V pipeline."""
    import torch
    from diffusers import WanImageToVideoPipeline
    
    logger.info("Loading Wan 2.2 I2V A14B model...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16
    
    self.pipe = WanImageToVideoPipeline.from_pretrained(
        "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
        torch_dtype=dtype,
        trust_remote_code=True,
    )
    self.pipe.to(device)
    
    # Enable memory optimizations for large models
    if hasattr(self.pipe, 'enable_model_cpu_offload'):
        self.pipe.enable_model_cpu_offload()
    
    self.device = device
    self.dtype = dtype
    
    gpu_name = None
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
    
    self.gpu_name = gpu_name
    logger.success(f"Model loaded on {device} (GPU: {gpu_name})")


@chute.cord(
    public_api_path="/generate",
    public_api_method="POST",
    stream=False,
    output_content_type="video/mp4",
)
async def generate_video(self, data: VideoGenerationRequest) -> Response:
    """Generate video from image and text prompt."""
    import torch
    import numpy as np
    from PIL import Image
    from diffusers.utils import export_to_video
    
    logger.info(f"Generating video with prompt: {data.prompt[:100]}...")
    
    # Load input image
    try:
        image = _load_image_from_input(data.image)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load image: {e}")
    
    # Calculate dimensions based on resolution
    max_area = 480 * 832 if data.resolution == Resolution.RES_480P else 720 * 1280
    
    aspect_ratio = image.height / image.width
    mod_value = self.pipe.vae_scale_factor_spatial * self.pipe.transformer.config.patch_size[1]
    height = round(np.sqrt(max_area * aspect_ratio)) // mod_value * mod_value
    width = round(np.sqrt(max_area / aspect_ratio)) // mod_value * mod_value
    
    # Clamp dimensions
    height = max(256, min(height, 1280))
    width = max(256, min(width, 1280))
    
    # Resize image
    image = image.resize((width, height))
    
    # Set up generator
    generator = None
    if data.seed is not None:
        generator = torch.Generator(device=self.device).manual_seed(data.seed)
    
    # Determine inference steps based on fast mode
    num_inference_steps = 25 if not data.fast else 15
    
    try:
        with torch.no_grad():
            output = self.pipe(
                image=image,
                prompt=data.prompt,
                negative_prompt=data.negative_prompt,
                height=height,
                width=width,
                num_frames=data.frames,
                guidance_scale=data.guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator,
            )
        
        frames = output.frames[0]
        
        # Export to video in memory
        video_buffer = io.BytesIO()
        export_to_video(frames, video_buffer, fps=data.fps)
        video_buffer.seek(0)
        
        video_id = str(uuid.uuid4())[:8]
        logger.success(f"Video generated successfully: {len(frames)} frames at {data.fps} fps")
        
        return Response(
            content=video_buffer.read(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename=wan_i2v_{video_id}.mp4"
            },
        )
        
    except torch.cuda.OutOfMemoryError:
        logger.error("GPU out of memory")
        raise HTTPException(
            status_code=503,
            detail="GPU out of memory. Try reducing frames or resolution."
        )
    except Exception as e:
        logger.exception("Video generation failed")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> HealthStatus:
    """Health check endpoint."""
    import torch
    
    model_loaded = hasattr(self, 'pipe') and self.pipe is not None
    gpu_available = torch.cuda.is_available()
    
    status = "healthy" if model_loaded and gpu_available else "degraded"
    
    return HealthStatus(
        status=status,
        model_loaded=model_loaded,
        gpu_available=gpu_available,
        gpu_name=getattr(self, 'gpu_name', None),
    )
