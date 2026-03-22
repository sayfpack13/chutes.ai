"""
Configuration Manager for Chutes AI Management System

Handles reading, writing, and validating YAML configuration files for chutes.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ModelSource(str, Enum):
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    CUSTOM = "custom"


class EndpointMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class ModelConfig(BaseModel):
    source: ModelSource = ModelSource.HUGGINGFACE
    name: str = Field(..., description="Model name or path")
    revision: str = Field(default="main", description="Model revision/branch")
    trust_remote_code: bool = Field(default=False)
    custom_download_url: Optional[str] = None


class HardwareConfig(BaseModel):
    gpu_count: int = Field(default=1, ge=1, le=8)
    min_vram_gb_per_gpu: int = Field(
        default=16,
        ge=16,
        le=80,
        description="Chutes NodeSelector requires at least 16 GB per GPU",
    )
    include: List[str] = Field(default_factory=lambda: [])
    exclude: List[str] = Field(default_factory=lambda: [])
    
    def to_node_selector_dict(self) -> Dict[str, Any]:
        result = {
            "gpu_count": self.gpu_count,
            "min_vram_gb_per_gpu": self.min_vram_gb_per_gpu,
        }
        if self.include:
            result["include"] = self.include
        if self.exclude:
            result["exclude"] = self.exclude
        return result


class EndpointConfig(BaseModel):
    path: str = Field(..., description="API endpoint path")
    method: EndpointMethod = Field(default=EndpointMethod.POST)
    input_schema: str = Field(default="TextInput", description="Pydantic input schema name")
    output_content_type: str = Field(default="application/json")
    stream: bool = Field(default=False)
    description: str = Field(default="")


class DockerImageConfig(BaseModel):
    """Docker / Chutes Image() settings."""
    base_image: str = Field(default="nvidia/cuda:12.1-runtime-ubuntu22.04")
    python_version: str = Field(default="3.11")
    system_packages: List[str] = Field(default_factory=lambda: ["git", "curl", "ffmpeg"])
    python_packages: List[str] = Field(default_factory=lambda: [])
    extra_pip_index: Optional[str] = None
    env_vars: Dict[str, str] = Field(default_factory=dict)
    # Chutes Image registry name/tag (defaults derived from chute name if empty)
    image_name: str = Field(default="", description="Image name passed to chutes.image.Image")
    image_tag: str = Field(default="1.0.0", description="Image tag for Chutes registry")
    image_readme: str = Field(default="", description="Short readme for the image on Chutes")


class ChuteConfig(BaseModel):
    """Complete configuration for a chute."""
    name: str = Field(..., description="Chute name (unique identifier)")
    chute_type: Literal[
        "music",
        "image",
        "llm",
        "speech",
        "vision",
        "tts",
        "custom",
        "vllm",
        "sglang",
        "diffusion",
        "embedding",
        "video",
        "moderation",
    ] = Field(default="custom", description="Scaffold used by the code generator")
    username: str = Field(default="your_username", description="Chutes.ai username")
    tagline: str = Field(default="AI Service", description="Short description")
    description: str = Field(default="", description="Full description/readme")
    model: ModelConfig
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    docker: DockerImageConfig = Field(default_factory=DockerImageConfig)
    api: List[EndpointConfig] = Field(default_factory=lambda: [EndpointConfig(path="/generate")])
    concurrency: int = Field(default=4, ge=1, le=64)
    allow_external_egress: bool = Field(default=True)
    shutdown_after_seconds: int = Field(default=300, ge=60, le=3600)
    # Chutes SDK template builders (vllm / sglang / diffusion / embedding)
    engine_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Passed to build_*_chute engine_args (vLLM/SGLang/diffusion/embedding)",
    )
    template_max_instances: int = Field(default=1, ge=1, le=64)
    template_scaling_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    embedding_pooling_type: str = Field(default="auto")
    embedding_max_embed_len: int = Field(default=3072000, ge=256, le=10_000_000)
    embedding_enable_chunked_processing: bool = Field(default=True)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError("Name must contain only alphanumeric characters, hyphens, and underscores")
        return v.lower()


class ConfigManager:
    """Manages chute configuration files."""
    
    def __init__(self, configs_dir: str = "configs"):
        self.configs_dir = Path(configs_dir)
        self.configs_dir.mkdir(parents=True, exist_ok=True)
        
        self.templates_dir = self.configs_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def list_configs(self) -> List[str]:
        """List all configuration files."""
        configs = []
        for f in self.configs_dir.glob("*.yaml"):
            if f.is_file():
                configs.append(f.stem)
        return sorted(configs)
    
    def list_templates(self) -> List[str]:
        """List all template files."""
        templates = []
        for f in self.templates_dir.glob("*.yaml"):
            if f.is_file():
                templates.append(f.stem)
        return sorted(templates)
    
    def load_config(self, name: str) -> ChuteConfig:
        """Load a configuration by name."""
        config_path = self.configs_dir / f"{name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration not found: {name}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return ChuteConfig(**data)
    
    def load_template(self, name: str) -> ChuteConfig:
        """Load a template by name."""
        template_path = self.templates_dir / f"{name}.yaml"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {name}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return ChuteConfig(**data)
    
    def save_config(self, config: ChuteConfig) -> Path:
        """Save a configuration to file."""
        config_path = self.configs_dir / f"{config.name}.yaml"
        
        with open(config_path, 'w', encoding='utf-8') as f:
            # mode='json' ensures enums and types are YAML-serializable
            yaml.dump(config.model_dump(mode='json'), f, default_flow_style=False, sort_keys=False)
        
        return config_path
    
    def save_template(self, config: ChuteConfig) -> Path:
        """Save a configuration as a template."""
        template_path = self.templates_dir / f"{config.name}.yaml"
        
        with open(template_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.model_dump(mode='json'), f, default_flow_style=False, sort_keys=False)
        
        return template_path
    
    def delete_config(self, name: str) -> bool:
        """Delete a configuration file."""
        config_path = self.configs_dir / f"{name}.yaml"
        
        if config_path.exists():
            config_path.unlink()
            return True
        return False
    
    def config_exists(self, name: str) -> bool:
        """Check if a configuration exists."""
        return (self.configs_dir / f"{name}.yaml").exists()
    
    def create_from_template(self, template_name: str, new_name: str, **overrides) -> ChuteConfig:
        """Create a new config from a template with overrides."""
        template = self.load_template(template_name)
        
        # Create new config with overrides
        config_dict = template.model_dump()
        config_dict['name'] = new_name
        
        for key, value in overrides.items():
            if '.' in key:
                # Handle nested updates like 'model.name'
                parts = key.split('.')
                current = config_dict
                for part in parts[:-1]:
                    current = current[part]
                current[parts[-1]] = value
            else:
                config_dict[key] = value
        
        new_config = ChuteConfig(**config_dict)
        self.save_config(new_config)
        
        return new_config
    
    def get_config_path(self, name: str) -> Path:
        """Get the file path for a configuration."""
        return self.configs_dir / f"{name}.yaml"
    
    def get_all_configs(self) -> Dict[str, ChuteConfig]:
        """Load all configurations."""
        configs = {}
        for name in self.list_configs():
            try:
                configs[name] = self.load_config(name)
            except Exception as e:
                print(f"Error loading {name}: {e}")
        return configs


def load_config_from_file(filepath: str) -> ChuteConfig:
    """Load configuration from a specific file path."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return ChuteConfig(**data)


def save_config_to_file(config: ChuteConfig, filepath: str) -> None:
    """Save configuration to a specific file path."""
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(config.model_dump(mode='json'), f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    # Test the config manager
    manager = ConfigManager()
    
    # Create a sample config
    sample = ChuteConfig(
        name="test-chute",
        model=ModelConfig(
            name="facebook/musicgen-medium",
        ),
        hardware=HardwareConfig(
            gpu_count=1,
            min_vram_gb_per_gpu=16,
        )
    )
    
    print("Sample config:")
    print(yaml.dump(sample.model_dump(), default_flow_style=False))
