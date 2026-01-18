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
    "FileInputDelimited": ComponentMetadata(
        type="FileInputDelimited",
        label="file_input_delimited",
        category="File",
        icon="file-text",
        description="Read delimited files (CSV, TSV, etc.) with customizable parsing options",
        fields=[
            ComponentFieldSchema(
                name="filepath",
                type=ComponentFieldType.TEXT,
                label="File Path",
                required=True,
                placeholder="/path/to/file.csv",
                description="Path to the delimited file",
            ),
            ComponentFieldSchema(
                name="delimiter",
                type=ComponentFieldType.TEXT,
                label="Delimiter",
                default=",",
                description="Field delimiter (comma, tab, semicolon, etc.)",
            ),
            ComponentFieldSchema(
                name="encoding",
                type=ComponentFieldType.TEXT,
                label="Encoding",
                default="UTF-8",
                description="File encoding (UTF-8, UTF-16, ISO-8859-1, etc.)",
            ),
            ComponentFieldSchema(
                name="header_rows",
                type=ComponentFieldType.TEXT,
                label="Header Rows",
                default="1",
                description="Number of header rows to skip",
            ),
            ComponentFieldSchema(
                name="footer_rows",
                type=ComponentFieldType.TEXT,
                label="Footer Rows",
                default="0",
                description="Number of footer rows to skip",
            ),
            ComponentFieldSchema(
                name="text_enclosure",
                type=ComponentFieldType.TEXT,
                label="Text Enclosure",
                default='"',
                description="Character used to enclose fields",
            ),
            ComponentFieldSchema(
                name="trim_all",
                type=ComponentFieldType.BOOLEAN,
                label="Trim All Fields",
                default=False,
                description="Remove leading/trailing whitespace from all fields",
            ),
            ComponentFieldSchema(
                name="remove_empty_rows",
                type=ComponentFieldType.BOOLEAN,
                label="Remove Empty Rows",
                default=False,
                description="Skip empty rows during reading",
            ),
            ComponentFieldSchema(
                name="die_on_error",
                type=ComponentFieldType.BOOLEAN,
                label="Die on Error",
                default=True,
                description="Throw error or continue on parsing errors",
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
