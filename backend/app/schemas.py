"""
API schemas and component metadata
"""
from app.models import ComponentMetadata, ComponentFieldSchema, ComponentFieldType


# Component Metadata Registry
COMPONENT_REGISTRY: dict = {
    "FileTouch": ComponentMetadata(
        type="FileTouch",
        label="file_touch",
        category="File",
        icon="file-plus",
        description="Create an empty file at specified path",
        fields=[
            ComponentFieldSchema(
                name="filename",
                type=ComponentFieldType.TEXT,
                label="File Path",
                required=True,
                placeholder="/path/to/file.txt",
            ),
            ComponentFieldSchema(
                name="create_dir",
                type=ComponentFieldType.BOOLEAN,
                label="Create Directory if Missing",
                default=False,
            ),
        ],
        input_count=0,
        output_count=1,
    ),
}


def get_component_metadata(component_type: str) -> ComponentMetadata:
    """Get metadata for a component type"""
    if component_type not in COMPONENT_REGISTRY:
        raise ValueError(f"Unknown component type: {component_type}")
    return COMPONENT_REGISTRY[component_type]


def list_components() -> list:
    """List all available components as flat array with category"""
    components = []
    for comp_type, metadata in COMPONENT_REGISTRY.items():
        components.append({
            "type": metadata.type,
            "label": metadata.label,
            "category": metadata.category,
            "icon": metadata.icon,
            "description": metadata.description,
            "fields": [
                {
                    "name": field.name,
                    "type": field.type.value,
                    "label": field.label,
                    "description": field.description,
                    "required": field.required,
                    "default": field.default,
                    "options": field.options,
                }
                for field in metadata.fields
            ],
            "input_count": metadata.input_count,
            "output_count": metadata.output_count,
        })
    return components
