"""
API schemas and component metadata
"""
from app.models import ComponentMetadata, ComponentFieldSchema, ComponentFieldType


# Component Metadata Registry
COMPONENT_REGISTRY: dict = {
    "Map": ComponentMetadata(
        type="Map",
        label="tMap",
        category="Transform",
        icon="swap",
        description="Data transformation with joins, lookups, and complex expressions",
        fields=[
            ComponentFieldSchema(
                name="die_on_error",
                type=ComponentFieldType.BOOLEAN,
                label="Die on Error",
                description="Stop job if error occurs",
                default=True,
            ),
            ComponentFieldSchema(
                name="execution_mode",
                type=ComponentFieldType.SELECT,
                label="Execution Mode",
                options=["batch", "streaming", "hybrid"],
                default="hybrid",
            ),
        ],
        input_count=1,
        output_count=2,
        allow_multiple_inputs=True,
    ),
    "Filter": ComponentMetadata(
        type="Filter",
        label="tFilter",
        category="Transform",
        icon="filter",
        description="Filter rows based on condition",
        fields=[
            ComponentFieldSchema(
                name="condition",
                type=ComponentFieldType.EXPRESSION,
                label="Filter Condition",
                required=True,
            ),
        ],
        input_count=1,
        output_count=2,
    ),
    "FileInput": ComponentMetadata(
        type="FileInput",
        label="tFileInput",
        category="Input",
        icon="file",
        description="Read data from file (CSV, JSON, Parquet)",
        fields=[
            ComponentFieldSchema(
                name="file_path",
                type=ComponentFieldType.TEXT,
                label="File Path",
                required=True,
                placeholder="/path/to/file.csv",
            ),
            ComponentFieldSchema(
                name="file_format",
                type=ComponentFieldType.SELECT,
                label="File Format",
                options=["csv", "json", "parquet", "excel"],
                default="csv",
            ),
            ComponentFieldSchema(
                name="encoding",
                type=ComponentFieldType.TEXT,
                label="Encoding",
                default="utf-8",
            ),
        ],
        input_count=0,
        output_count=1,
    ),
    "FileOutput": ComponentMetadata(
        type="FileOutput",
        label="tFileOutput",
        category="Output",
        icon="download",
        description="Write data to file",
        fields=[
            ComponentFieldSchema(
                name="file_path",
                type=ComponentFieldType.TEXT,
                label="Output Path",
                required=True,
                placeholder="/path/to/output.csv",
            ),
            ComponentFieldSchema(
                name="file_format",
                type=ComponentFieldType.SELECT,
                label="File Format",
                options=["csv", "json", "parquet", "excel"],
                default="csv",
            ),
            ComponentFieldSchema(
                name="append_mode",
                type=ComponentFieldType.BOOLEAN,
                label="Append to Existing",
                default=False,
            ),
        ],
        input_count=1,
        output_count=0,
    ),
    "Aggregate": ComponentMetadata(
        type="Aggregate",
        label="tAggregate",
        category="Transform",
        icon="area-chart",
        description="Group and aggregate data",
        fields=[
            ComponentFieldSchema(
                name="group_by",
                type=ComponentFieldType.ARRAY,
                label="Group By Columns",
                required=True,
            ),
            ComponentFieldSchema(
                name="aggregations",
                type=ComponentFieldType.ARRAY,
                label="Aggregations",
                description="e.g., sum(amount), count(*)",
                required=True,
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "Sort": ComponentMetadata(
        type="Sort",
        label="tSort",
        category="Transform",
        icon="sort-ascending",
        description="Sort data by columns",
        fields=[
            ComponentFieldSchema(
                name="sort_columns",
                type=ComponentFieldType.ARRAY,
                label="Sort By",
                required=True,
            ),
            ComponentFieldSchema(
                name="sort_order",
                type=ComponentFieldType.SELECT,
                label="Order",
                options=["ascending", "descending"],
                default="ascending",
            ),
        ],
        input_count=1,
        output_count=1,
    ),
}


def get_component_metadata(component_type: str) -> ComponentMetadata:
    """Get metadata for a component type"""
    if component_type not in COMPONENT_REGISTRY:
        raise ValueError(f"Unknown component type: {component_type}")
    return COMPONENT_REGISTRY[component_type]


def list_components() -> dict:
    """List all available components grouped by category"""
    by_category = {}
    for comp_type, metadata in COMPONENT_REGISTRY.items():
        category = metadata.category
        if category not in by_category:
            by_category[category] = []
        by_category[category].append({
            "type": metadata.type,
            "label": metadata.label,
            "icon": metadata.icon,
            "description": metadata.description,
        })
    return by_category
