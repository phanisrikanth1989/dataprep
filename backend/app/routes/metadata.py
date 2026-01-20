"""
Metadata browser API routes
Provides access to database connections, tables, and schemas
"""
from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metadata", tags=["metadata"])

# Mock database connections for demo purposes
MOCK_CONNECTIONS = {
    "customer_db": {
        "type": "database",
        "host": "localhost",
        "port": 5432,
        "database": "customer_db",
        "tables": [
            {
                "name": "customers",
                "rows": 5000,
                "columns": [
                    {"name": "customer_id", "type": "INTEGER", "nullable": False},
                    {"name": "first_name", "type": "VARCHAR", "nullable": False},
                    {"name": "last_name", "type": "VARCHAR", "nullable": False},
                    {"name": "email", "type": "VARCHAR", "nullable": True},
                    {"name": "phone", "type": "VARCHAR", "nullable": True},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                ]
            },
            {
                "name": "orders",
                "rows": 25000,
                "columns": [
                    {"name": "order_id", "type": "INTEGER", "nullable": False},
                    {"name": "customer_id", "type": "INTEGER", "nullable": False},
                    {"name": "order_date", "type": "TIMESTAMP", "nullable": False},
                    {"name": "total_amount", "type": "DECIMAL", "nullable": False},
                    {"name": "status", "type": "VARCHAR", "nullable": False},
                ]
            },
            {
                "name": "products",
                "rows": 1000,
                "columns": [
                    {"name": "product_id", "type": "INTEGER", "nullable": False},
                    {"name": "name", "type": "VARCHAR", "nullable": False},
                    {"name": "category", "type": "VARCHAR", "nullable": False},
                    {"name": "price", "type": "DECIMAL", "nullable": False},
                    {"name": "stock", "type": "INTEGER", "nullable": True},
                ]
            }
        ]
    },
    "sales_db": {
        "type": "database",
        "host": "localhost",
        "port": 5432,
        "database": "sales_db",
        "tables": [
            {
                "name": "sales",
                "rows": 50000,
                "columns": [
                    {"name": "sale_id", "type": "INTEGER", "nullable": False},
                    {"name": "product_id", "type": "INTEGER", "nullable": False},
                    {"name": "quantity", "type": "INTEGER", "nullable": False},
                    {"name": "sale_date", "type": "DATE", "nullable": False},
                    {"name": "amount", "type": "DECIMAL", "nullable": False},
                ]
            },
            {
                "name": "regions",
                "rows": 20,
                "columns": [
                    {"name": "region_id", "type": "INTEGER", "nullable": False},
                    {"name": "region_name", "type": "VARCHAR", "nullable": False},
                    {"name": "country", "type": "VARCHAR", "nullable": False},
                ]
            }
        ]
    }
}


@router.get("/connections")
async def list_connections():
    """List all available database connections"""
    try:
        connections = []
        for conn_name, conn_info in MOCK_CONNECTIONS.items():
            connections.append({
                "id": conn_name,
                "name": conn_name,
                "type": conn_info.get("type", "database"),
                "host": conn_info.get("host", "N/A"),
                "database": conn_info.get("database", "N/A"),
                "table_count": len(conn_info.get("tables", []))
            })
        return connections
    except Exception as e:
        logger.error(f"Error listing connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}")
async def get_connection(connection_id: str):
    """Get connection details"""
    try:
        if connection_id not in MOCK_CONNECTIONS:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        conn = MOCK_CONNECTIONS[connection_id]
        return {
            "id": connection_id,
            "name": connection_id,
            "type": conn.get("type", "database"),
            "host": conn.get("host", "N/A"),
            "database": conn.get("database", "N/A"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection {connection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}/tables")
async def list_tables(connection_id: str):
    """List all tables in a connection"""
    try:
        if connection_id not in MOCK_CONNECTIONS:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        conn = MOCK_CONNECTIONS[connection_id]
        tables = []
        
        for table in conn.get("tables", []):
            tables.append({
                "name": table["name"],
                "rows": table.get("rows", 0),
                "column_count": len(table.get("columns", [])),
                "columns": [
                    {
                        "name": col["name"],
                        "type": col["type"],
                        "nullable": col.get("nullable", False)
                    }
                    for col in table.get("columns", [])
                ]
            })
        
        return tables
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tables for {connection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}/tables/{table_name}")
async def get_table_schema(connection_id: str, table_name: str):
    """Get schema details for a specific table"""
    try:
        if connection_id not in MOCK_CONNECTIONS:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        conn = MOCK_CONNECTIONS[connection_id]
        
        for table in conn.get("tables", []):
            if table["name"] == table_name:
                return {
                    "name": table["name"],
                    "rows": table.get("rows", 0),
                    "columns": [
                        {
                            "name": col["name"],
                            "type": col["type"],
                            "nullable": col.get("nullable", False),
                            "key": col.get("key", False),
                            "precision": col.get("precision", None),
                        }
                        for col in table.get("columns", [])
                    ]
                }
        
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for {connection_id}.{table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}/tables/{table_name}/preview")
async def preview_table_data(connection_id: str, table_name: str, limit: int = 10):
    """Get preview data from a table (first N rows)"""
    try:
        if connection_id not in MOCK_CONNECTIONS:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Return mock preview data
        schema_response = await get_table_schema(connection_id, table_name)
        columns = [col["name"] for col in schema_response["columns"]]
        
        # Generate mock data based on column types
        rows = []
        for i in range(min(limit, 5)):
            row = {}
            for col in schema_response["columns"]:
                if "INT" in col["type"].upper():
                    row[col["name"]] = i + 1
                elif "DECIMAL" in col["type"].upper():
                    row[col["name"]] = round((i + 1) * 10.5, 2)
                elif "DATE" in col["type"].upper() or "TIMESTAMP" in col["type"].upper():
                    row[col["name"]] = "2024-01-" + str(f"{i+1:02d}").zfill(2)
                else:
                    row[col["name"]] = f"value_{i+1}"
            rows.append(row)
        
        return {
            "connection": connection_id,
            "table": table_name,
            "columns": columns,
            "rows": rows,
            "total_rows": schema_response["rows"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing table {connection_id}.{table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
