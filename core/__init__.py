# Core module for Chutes AI Management System

from .config_manager import (
    ConfigManager,
    ChuteConfig,
    ModelConfig,
    HardwareConfig,
    DockerImageConfig,
    EndpointConfig,
    ModelSource,
    EndpointMethod,
    load_config_from_file,
    save_config_to_file,
)

from .templates import (
    TEMPLATES,
    get_template,
    get_template_names,
    get_template_catalog,
    get_all_templates,
    group_local_configs_for_home,
)

from .chute_generator import write_chute_module, module_ref, generate_python_source
from .deployer import (
    build_chute,
    deploy_chute,
    chutes_list,
    chutes_get,
    chutes_logs,
    chutes_executable,
    chutes_on_path,
    CommandResult,
)
from .seed_templates import seed_builtin_templates
from .chute_kinds import PLATFORM_IMAGE_CHUTE_TYPES, uses_chutes_platform_image

__all__ = [
    "ConfigManager",
    "ChuteConfig",
    "ModelConfig",
    "HardwareConfig",
    "DockerImageConfig",
    "EndpointConfig",
    "ModelSource",
    "EndpointMethod",
    "load_config_from_file",
    "save_config_to_file",
    "TEMPLATES",
    "get_template",
    "get_template_names",
    "get_template_catalog",
    "get_all_templates",
    "group_local_configs_for_home",
    "write_chute_module",
    "module_ref",
    "generate_python_source",
    "build_chute",
    "deploy_chute",
    "chutes_list",
    "chutes_get",
    "chutes_logs",
    "chutes_executable",
    "chutes_on_path",
    "CommandResult",
    "seed_builtin_templates",
    "PLATFORM_IMAGE_CHUTE_TYPES",
    "uses_chutes_platform_image",
]
