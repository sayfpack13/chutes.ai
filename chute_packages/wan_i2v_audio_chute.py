# -*- coding: utf-8 -*-
# Wan 2.2 I2V + MusicGen - Video with AI soundtrack

"""
Video generation with AI-generated soundtrack.
Combines Wan 2.2 I2V (image-to-video) with MusicGen (text-to-music).

Note: torch/diffusers/audiocraft are lazy-imported inside functions so `chutes build`
can load this module without a local GPU stack.
"""
import io
import uuid
import base64
import subprocess
import tempfile
import os
from typing import Optional
from enum import Enum

from fastapi import HTTPException
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from chutes.image import Image

# Build custom image with video + audio generation capabilities
image = (
    Image(
        username='sayfpack',
        name='wan-i2v-audio',
        tag='1.0.0',
        readme='Wan 2.2 I2V + MusicGen - Video with AI soundtrack',
    )
    .from_base('parachutes/base-python:3.12.7')
    .set_user("root")
    .run_command("apt-get update && apt-get install -y ffmpeg git libsndfile1 && rm -rf /var/lib/apt/lists/*")
    .set_user("chutes")
    .run_command(
        "pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
    )
    .run_command(
        "pip install --no-cache-dir diffusers>=0.33.0 transformers accelerate safetensors pillow numpy requests audiocraft"
    )
    .with_env('HF_HOME', '/app/models')
    .with_env('AUDIOCRAFT_CACHE', '/app/models')
    .run_command("mkdir -p /app/models")
    .set_workdir("/app")
)

from chutes.chute import Chute, NodeSelector

chute = Chute(
    username='sayfpack',
    name='wan-i2v-audio',
    tagline='Wan 2.2 I2V + MusicGen - Video with AI soundtrack',
    readme="""# Video Generation with AI Soundtrack

Combines Wan 2.2 I2V for video generation with MusicGen for AI-generated soundtrack.

## Features
- Image-to-video generation
- AI-generated music soundtrack matching the video mood
- Automatic audio-video synchronization
- Configurable video duration, FPS, and music style

## Usage
POST to /generate with:
- `prompt`: Description of the video content
- `music_prompt`: Description of desired music style (optional, auto-generated if omitted)
- `image`: URL or base64-encoded input image
- `duration`: Video duration in seconds (default 5)
- `fps`: Frames per second (default 16)
- `guidance_scale`: Video guidance strength
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


class VideoWithAudioRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text prompt for video generation")
    image: str = Field(..., description="URL or base64-encoded image to animate")
    music_prompt: Optional[str] = Field(default=None, max_length=500, description="Music style prompt (auto-generated if omitted)")
    duration: int = Field(default=5, ge=1, le=15, description="Video duration in seconds")
    fps: int = Field(default=16, ge=8, le=60, description="Frames per second")
    fast: bool = Field(default=False, description="Use fast mode (fewer inference steps)")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    guidance_scale: float = Field(default=1.0, ge=1.0, le=10.0, description="Video guidance scale")
    music_guidance_scale: float = Field(default=3.0, ge=1.0, le=10.0, description="Music guidance scale")
    resolution: Resolution = Field(default=Resolution.RES_480P, description="Output resolution")
    negative_prompt: str = Field(
        default="色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走",
        description="Negative prompt for video"
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
    video_model_loaded: bool
    music_model_loaded: bool
    gpu_available: bool
    gpu_name: Optional[str] = None


def _load_image_from_input(image_input: str):
    """Load image from URL or base64 string."""
    import requests
    from PIL import Image
    
    if image_input.startswith(('http://', 'https://')):
        try:
            response = requests.get(image_input, timeout=30)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert('RGB')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load image from URL: {e}")
    
    try:
        if image_input.startswith('data:image'):
            image_input = image_input.split(',', 1)[1]
        image_bytes = base64.b64decode(image_input)
        return Image.open(io.BytesIO(image_bytes)).convert('RGB')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode base64 image: {e}")


def _generate_music_prompt(video_prompt: str) -> str:
    """Generate a music prompt based on the video prompt."""
    # Simple heuristic to create music style from video description
    keywords = {
        'beach': 'tropical upbeat ukulele',
        'ocean': 'ambient waves peaceful',
        'forest': 'nature ambient birds peaceful',
        'city': 'urban electronic beat',
        'night': 'ambient dark atmospheric',
        'sunset': 'peaceful acoustic guitar',
        'mountain': 'epic orchestral cinematic',
        'snow': 'peaceful ambient winter',
        'rain': 'melancholic piano ambient',
        'sunny': 'upbeat happy pop',
        'dark': 'dark ambient atmospheric',
        'action': 'energetic electronic beat',
        'calm': 'peaceful ambient meditation',
        'love': 'romantic piano soft',
        'horror': 'dark horror atmospheric',
        'sci-fi': 'electronic futuristic synth',
        'nature': 'ambient nature peaceful',
        'dance': 'upbeat electronic dance',
        'party': 'energetic pop dance',
        'wedding': 'romantic classical piano',
    }
    
    prompt_lower = video_prompt.lower()
    for key, style in keywords.items():
        if key in prompt_lower:
            return f"{style}, {video_prompt[:50]}"
    
    # Default fallback
    return f"ambient background music, {video_prompt[:50]}"


@chute.on_startup()
async def load_models(self):
    """Initialize Wan I2V and MusicGen pipelines."""
    import torch
    from diffusers import WanImageToVideoPipeline
    from audiocraft.models import MusicGen
    
    logger.info("Loading Wan 2.2 I2V A14B model...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16
    
    # Load video model
    self.video_pipe = WanImageToVideoPipeline.from_pretrained(
        "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
        torch_dtype=dtype,
        trust_remote_code=True,
    )
    self.video_pipe.to(device)
    
    # Enable memory optimizations
    if hasattr(self.video_pipe, 'enable_model_cpu_offload'):
        self.video_pipe.enable_model_cpu_offload()
    
    logger.info("Loading MusicGen medium model...")
    
    # Load music model
    self.music_model = MusicGen.get_pretrained('facebook/musicgen-medium')
    
    self.device = device
    self.dtype = dtype
    
    gpu_name = None
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
    
    self.gpu_name = gpu_name
    logger.success(f"Models loaded on {device} (GPU: {gpu_name})")


@chute.cord(
    public_api_path="/generate",
    public_api_method="POST",
    stream=False,
    output_content_type="video/mp4",
)
async def generate_video_with_audio(self, data: VideoWithAudioRequest) -> Response:
    """Generate video with AI soundtrack from image and prompts."""
    import torch
    import numpy as np
    import torchaudio
    from PIL import Image
    from diffusers.utils import export_to_video
    
    logger.info(f"Generating video+audio with prompt: {data.prompt[:100]}...")
    
    # Load input image
    try:
        image = _load_image_from_input(data.image)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load image: {e}")
    
    # Calculate dimensions
    max_area = 480 * 832 if data.resolution == Resolution.RES_480P else 720 * 1280
    aspect_ratio = image.height / image.width
    mod_value = self.video_pipe.vae_scale_factor_spatial * self.video_pipe.transformer.config.patch_size[1]
    height = round(np.sqrt(max_area * aspect_ratio)) // mod_value * mod_value
    width = round(np.sqrt(max_area / aspect_ratio)) // mod_value * mod_value
    height = max(256, min(height, 1280))
    width = max(256, min(width, 1280))
    image = image.resize((width, height))
    
    # Calculate frames from duration
    num_frames = data.duration * data.fps
    num_frames = max(16, min(num_frames, 241))
    
    # Set up generator
    generator = None
    if data.seed is not None:
        generator = torch.Generator(device=self.device).manual_seed(data.seed)
    
    num_inference_steps = 25 if not data.fast else 15
    
    try:
        # Generate video frames
        logger.info("Generating video frames...")
        with torch.no_grad():
            video_output = self.video_pipe(
                image=image,
                prompt=data.prompt,
                negative_prompt=data.negative_prompt,
                height=height,
                width=width,
                num_frames=num_frames,
                guidance_scale=data.guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator,
            )
        
        frames = video_output.frames[0]
        logger.success(f"Generated {len(frames)} frames")
        
        # Generate music
        music_prompt = data.music_prompt or _generate_music_prompt(data.prompt)
        logger.info(f"Generating music with prompt: {music_prompt[:50]}...")
        
        self.music_model.set_generation_params(duration=data.duration, guidance_scale=data.music_guidance_scale)
        if data.seed is not None:
            torch.manual_seed(data.seed)
        
        with torch.no_grad():
            wav = self.music_model.generate(descriptions=[music_prompt], progress=False)
        
        # Save audio to buffer
        audio_buffer = io.BytesIO()
        torchaudio.save(audio_buffer, wav[0].cpu(), sample_rate=32000, format="wav")
        audio_buffer.seek(0)
        logger.success(f"Generated {data.duration}s audio")
        
        # Merge video and audio with ffmpeg
        video_buffer = io.BytesIO()
        export_to_video(frames, video_buffer, fps=data.fps)
        video_buffer.seek(0)
        
        # Use ffmpeg to merge
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
            video_file.write(video_buffer.read())
            video_path = video_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as audio_file:
            audio_file.write(audio_buffer.read())
            audio_path = audio_file.name
        
        output_path = tempfile.mktemp(suffix='.mp4')
        
        try:
            subprocess.run([
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                output_path
            ], check=True, capture_output=True)
            
            with open(output_path, 'rb') as f:
                final_video = f.read()
        finally:
            # Cleanup temp files
            for p in [video_path, audio_path, output_path]:
                if os.path.exists(p):
                    os.unlink(p)
        
        video_id = str(uuid.uuid4())[:8]
        logger.success(f"Video+audio generated: {len(frames)} frames, {data.duration}s audio")
        
        return Response(
            content=final_video,
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename=wan_i2v_audio_{video_id}.mp4"},
        )
        
    except torch.cuda.OutOfMemoryError:
        logger.error("GPU out of memory")
        raise HTTPException(status_code=503, detail="GPU out of memory. Try reducing duration or resolution.")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail="Failed to merge video and audio")
    except Exception as e:
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@chute.cord(
    public_api_path="/health",
    public_api_method="GET",
    output_content_type="application/json",
)
async def health(self) -> HealthStatus:
    """Health check endpoint."""
    import torch
    
    video_loaded = hasattr(self, 'video_pipe') and self.video_pipe is not None
    music_loaded = hasattr(self, 'music_model') and self.music_model is not None
    gpu_available = torch.cuda.is_available()
    
    status = "healthy" if video_loaded and music_loaded and gpu_available else "degraded"
    
    return HealthStatus(
        status=status,
        video_model_loaded=video_loaded,
        music_model_loaded=music_loaded,
        gpu_available=gpu_available,
        gpu_name=getattr(self, 'gpu_name', None),
    )
