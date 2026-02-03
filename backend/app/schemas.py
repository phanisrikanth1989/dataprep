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
    "FileOutputDelimited": ComponentMetadata(
        type="FileOutputDelimited",
        label="file_output_delimited",
        category="File",
        icon="file-export",
        description="Write delimited files (CSV, TSV, etc.) with customizable formatting options",
        fields=[
            ComponentFieldSchema(
                name="filepath",
                type=ComponentFieldType.TEXT,
                label="File Path",
                required=True,
                placeholder="/path/to/file.csv",
                description="Output file path",
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
                name="include_header",
                type=ComponentFieldType.BOOLEAN,
                label="Include Header",
                default=True,
                description="Include column headers in output",
            ),
            ComponentFieldSchema(
                name="append",
                type=ComponentFieldType.BOOLEAN,
                label="Append to File",
                default=False,
                description="Append to existing file instead of overwriting",
            ),
            ComponentFieldSchema(
                name="text_enclosure",
                type=ComponentFieldType.TEXT,
                label="Text Enclosure",
                default='"',
                description="Quote character for text fields",
            ),
            ComponentFieldSchema(
                name="create_directory",
                type=ComponentFieldType.BOOLEAN,
                label="Create Directory if Missing",
                default=True,
                description="Create parent directories if needed",
            ),
            ComponentFieldSchema(
                name="die_on_error",
                type=ComponentFieldType.BOOLEAN,
                label="Die on Error",
                default=True,
                description="Throw error or continue on errors",
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "FilterRows": ComponentMetadata(
        type="FilterRows",
        label="filter_rows",
        category="Transform",
        icon="filter",
        description="Filter rows based on conditions or advanced expressions",
        fields=[
            ComponentFieldSchema(
                name="use_advanced",
                type=ComponentFieldType.BOOLEAN,
                label="Use Advanced Expression",
                default=False,
                description="Use advanced Java-like expression for filtering",
            ),
            ComponentFieldSchema(
                name="advanced_condition",
                type=ComponentFieldType.TEXT,
                label="Advanced Condition",
                description="Java-like filter expression (e.g., {{java}} col1 > 100 AND col2 == 'value')",
            ),
            ComponentFieldSchema(
                name="logical_operator",
                type=ComponentFieldType.TEXT,
                label="Logical Operator",
                default="AND",
                description="Logical operator for combining conditions (AND/OR)",
            ),
            ComponentFieldSchema(
                name="conditions",
                type=ComponentFieldType.TEXT,
                label="Conditions",
                description="Filter conditions as JSON array with column, operator, value",
            ),
        ],
        input_count=1,
        output_count=2,
    ),
    "FilterColumns": ComponentMetadata(
        type="FilterColumns",
        label="filter_columns",
        category="Transform",
        icon="columns",
        description="Select, reorder, or remove columns from the data flow",
        fields=[
            ComponentFieldSchema(
                name="mode",
                type=ComponentFieldType.SELECT,
                label="Mode",
                default="include",
                options=["include", "exclude"],
                description="Include only specified columns or exclude them",
            ),
            ComponentFieldSchema(
                name="columns",
                type=ComponentFieldType.TEXT,
                label="Columns",
                description="Comma-separated list of column names to include/exclude",
                placeholder="col1, col2, col3",
            ),
            ComponentFieldSchema(
                name="reorder",
                type=ComponentFieldType.BOOLEAN,
                label="Reorder Columns",
                default=False,
                description="Reorder columns to match the specified order",
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "Map": ComponentMetadata(
        type="Map",
        label="map",
        category="Transform",
        icon="arrows-alt",
        description="Transform and map column values using expressions",
        fields=[
            ComponentFieldSchema(
                name="mappings",
                type=ComponentFieldType.TEXT,
                label="Column Mappings",
                description="JSON array of mappings: [{source, target, expression}]",
                placeholder='[{"source": "col1", "target": "new_col", "expression": "upper(col1)"}]',
            ),
            ComponentFieldSchema(
                name="drop_unmapped",
                type=ComponentFieldType.BOOLEAN,
                label="Drop Unmapped Columns",
                default=False,
                description="Remove columns not specified in mappings",
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "Aggregate": ComponentMetadata(
        type="Aggregate",
        label="aggregate",
        category="Transform",
        icon="calculator",
        description="Perform aggregation operations (sum, avg, count, etc.)",
        fields=[
            ComponentFieldSchema(
                name="group_by",
                type=ComponentFieldType.TEXT,
                label="Group By Columns",
                description="Comma-separated list of columns to group by",
                placeholder="col1, col2",
            ),
            ComponentFieldSchema(
                name="aggregations",
                type=ComponentFieldType.TEXT,
                label="Aggregations",
                description="JSON array: [{column, operation, alias}]",
                placeholder='[{"column": "amount", "operation": "sum", "alias": "total_amount"}]',
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "Sort": ComponentMetadata(
        type="Sort",
        label="sort",
        category="Transform",
        icon="sort-amount-down",
        description="Sort rows by one or more columns",
        fields=[
            ComponentFieldSchema(
                name="sort_keys",
                type=ComponentFieldType.TEXT,
                label="Sort Keys",
                description="JSON array: [{column, order: 'asc'|'desc'}]",
                placeholder='[{"column": "name", "order": "asc"}]',
            ),
            ComponentFieldSchema(
                name="null_position",
                type=ComponentFieldType.SELECT,
                label="Null Position",
                default="last",
                options=["first", "last"],
                description="Position of null values in sort order",
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "Join": ComponentMetadata(
        type="Join",
        label="join",
        category="Transform",
        icon="code-branch",
        description="Join two data flows on matching keys",
        fields=[
            ComponentFieldSchema(
                name="join_type",
                type=ComponentFieldType.SELECT,
                label="Join Type",
                default="inner",
                options=["inner", "left", "right", "full", "cross"],
                description="Type of join operation",
            ),
            ComponentFieldSchema(
                name="join_keys",
                type=ComponentFieldType.TEXT,
                label="Join Keys",
                description="JSON array of key pairs: [{left, right}]",
                placeholder='[{"left": "id", "right": "customer_id"}]',
            ),
        ],
        input_count=2,
        output_count=1,
    ),
    "Deduplicate": ComponentMetadata(
        type="Deduplicate",
        label="deduplicate",
        category="Transform",
        icon="copy",
        description="Remove duplicate rows based on key columns",
        fields=[
            ComponentFieldSchema(
                name="key_columns",
                type=ComponentFieldType.TEXT,
                label="Key Columns",
                description="Comma-separated list of columns to check for duplicates",
                placeholder="col1, col2",
            ),
            ComponentFieldSchema(
                name="keep",
                type=ComponentFieldType.SELECT,
                label="Keep",
                default="first",
                options=["first", "last"],
                description="Which duplicate row to keep",
            ),
        ],
        input_count=1,
        output_count=1,
    ),
    "DatabaseInput": ComponentMetadata(
        type="DatabaseInput",
        label="database_input",
        category="Database",
        icon="database",
        description="Read data from a database table or query",
        fields=[
            ComponentFieldSchema(
                name="connection_string",
                type=ComponentFieldType.TEXT,
                label="Connection String",
                required=True,
                description="Database connection string",
                placeholder="postgresql://user:pass@host:5432/db",
            ),
            ComponentFieldSchema(
                name="query",
                type=ComponentFieldType.TEXT,
                label="SQL Query",
                required=True,
                description="SQL query to execute",
                placeholder="SELECT * FROM table_name",
            ),
            ComponentFieldSchema(
                name="fetch_size",
                type=ComponentFieldType.NUMBER,
                label="Fetch Size",
                default=1000,
                description="Number of rows to fetch at a time",
            ),
        ],
        input_count=0,
        output_count=1,
    ),
    "DatabaseOutput": ComponentMetadata(
        type="DatabaseOutput",
        label="database_output",
        category="Database",
        icon="database",
        description="Write data to a database table",
        fields=[
            ComponentFieldSchema(
                name="connection_string",
                type=ComponentFieldType.TEXT,
                label="Connection String",
                required=True,
                description="Database connection string",
            ),
            ComponentFieldSchema(
                name="table_name",
                type=ComponentFieldType.TEXT,
                label="Table Name",
                required=True,
                description="Target table name",
            ),
            ComponentFieldSchema(
                name="write_mode",
                type=ComponentFieldType.SELECT,
                label="Write Mode",
                default="append",
                options=["append", "overwrite", "upsert"],
                description="How to write data to the table",
            ),
            ComponentFieldSchema(
                name="batch_size",
                type=ComponentFieldType.NUMBER,
                label="Batch Size",
                default=1000,
                description="Number of rows per batch insert",
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
