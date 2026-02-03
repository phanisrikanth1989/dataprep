"""
API routes for database connections and context variables management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import uuid4
import json
import os

router = APIRouter(prefix="/api", tags=["connections"])

# Storage file paths
CONNECTIONS_FILE = "connections.json"
CONTEXTS_FILE = "contexts.json"


# ============================================
# Pydantic Models
# ============================================

class DBSchema(BaseModel):
    name: str
    tables: List[str] = []


class DBConnection(BaseModel):
    id: Optional[str] = None
    name: str
    type: str  # mysql, postgresql, oracle, sqlserver, sqlite
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl: bool = False
    extra_params: Optional[Dict[str, Any]] = None
    schemas: Optional[List[DBSchema]] = None


class ContextVariable(BaseModel):
    id: Optional[str] = None
    name: str
    value: str
    type: str = "string"  # string, number, password, boolean
    description: Optional[str] = None


class ContextGroup(BaseModel):
    id: Optional[str] = None
    name: str
    variables: List[ContextVariable] = []
    isDefault: bool = False


class TestConnectionRequest(BaseModel):
    type: str
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl: bool = False


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    version: Optional[str] = None


class RetrieveSchemaRequest(BaseModel):
    type: str
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl: bool = False


class TableColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True
    primaryKey: bool = False


class TableInfo(BaseModel):
    name: str
    columns: List[TableColumn] = []


class SchemaInfo(BaseModel):
    name: str
    tables: List[TableInfo] = []


class RetrieveSchemaResponse(BaseModel):
    success: bool
    schemas: List[SchemaInfo] = []
    message: Optional[str] = None


# ============================================
# Helper Functions
# ============================================

def load_connections() -> List[DBConnection]:
    """Load connections from file"""
    if os.path.exists(CONNECTIONS_FILE):
        with open(CONNECTIONS_FILE, 'r') as f:
            data = json.load(f)
            return [DBConnection(**conn) for conn in data]
    return []


def save_connections(connections: List[DBConnection]):
    """Save connections to file"""
    with open(CONNECTIONS_FILE, 'w') as f:
        json.dump([conn.model_dump() for conn in connections], f, indent=2)


def load_contexts() -> List[ContextGroup]:
    """Load context groups from file"""
    if os.path.exists(CONTEXTS_FILE):
        with open(CONTEXTS_FILE, 'r') as f:
            data = json.load(f)
            return [ContextGroup(**ctx) for ctx in data]
    # Return default contexts
    return [
        ContextGroup(id="ctx-dev", name="DEV", variables=[], isDefault=True),
        ContextGroup(id="ctx-qa", name="QA", variables=[], isDefault=False),
        ContextGroup(id="ctx-prod", name="PROD", variables=[], isDefault=False),
    ]


def save_contexts(contexts: List[ContextGroup]):
    """Save context groups to file"""
    with open(CONTEXTS_FILE, 'w') as f:
        json.dump([ctx.model_dump() for ctx in contexts], f, indent=2)


# ============================================
# DB Connection Endpoints
# ============================================

@router.get("/connections", response_model=List[DBConnection])
async def list_connections():
    """List all database connections"""
    return load_connections()


@router.post("/connections", response_model=DBConnection)
async def create_connection(connection: DBConnection):
    """Create a new database connection"""
    connections = load_connections()
    
    # Generate ID if not provided
    if not connection.id:
        connection.id = f"conn-{uuid4()}"
    
    # Check for duplicate names
    if any(c.name == connection.name for c in connections):
        raise HTTPException(status_code=400, detail="Connection name already exists")
    
    connections.append(connection)
    save_connections(connections)
    return connection


@router.get("/connections/{connection_id}", response_model=DBConnection)
async def get_connection(connection_id: str):
    """Get a specific connection by ID"""
    connections = load_connections()
    for conn in connections:
        if conn.id == connection_id:
            return conn
    raise HTTPException(status_code=404, detail="Connection not found")


@router.put("/connections/{connection_id}", response_model=DBConnection)
async def update_connection(connection_id: str, connection: DBConnection):
    """Update an existing connection"""
    connections = load_connections()
    for i, conn in enumerate(connections):
        if conn.id == connection_id:
            connection.id = connection_id
            connections[i] = connection
            save_connections(connections)
            return connection
    raise HTTPException(status_code=404, detail="Connection not found")


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str):
    """Delete a connection"""
    connections = load_connections()
    connections = [c for c in connections if c.id != connection_id]
    save_connections(connections)
    return {"status": "deleted"}


@router.post("/connections/test", response_model=TestConnectionResponse)
async def test_connection(request: TestConnectionRequest):
    """Test database connection"""
    # In a real implementation, this would actually try to connect
    # For now, we simulate the connection test
    
    try:
        # Simulate connection test based on type
        if request.type == "postgresql":
            # Would use psycopg2 or asyncpg
            return TestConnectionResponse(
                success=True,
                message="Connection successful",
                version="PostgreSQL 15.2"
            )
        elif request.type == "mysql":
            # Would use mysql-connector or pymysql
            return TestConnectionResponse(
                success=True,
                message="Connection successful",
                version="MySQL 8.0.32"
            )
        elif request.type == "oracle":
            return TestConnectionResponse(
                success=True,
                message="Connection successful",
                version="Oracle 19c"
            )
        elif request.type == "sqlserver":
            return TestConnectionResponse(
                success=True,
                message="Connection successful",
                version="SQL Server 2019"
            )
        elif request.type == "sqlite":
            return TestConnectionResponse(
                success=True,
                message="Connection successful",
                version="SQLite 3.40.0"
            )
        else:
            return TestConnectionResponse(
                success=False,
                message=f"Unsupported database type: {request.type}"
            )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}"
        )


@router.post("/connections/schema", response_model=RetrieveSchemaResponse)
async def retrieve_schema(request: RetrieveSchemaRequest):
    """Retrieve database schema (tables, columns)"""
    # In a real implementation, this would query the database metadata
    # For now, we return simulated schema
    
    try:
        # Simulate schema retrieval
        schemas = [
            SchemaInfo(
                name="public" if request.type == "postgresql" else request.database,
                tables=[
                    TableInfo(
                        name="customers",
                        columns=[
                            TableColumn(name="id", type="integer", nullable=False, primaryKey=True),
                            TableColumn(name="name", type="varchar(255)", nullable=False),
                            TableColumn(name="email", type="varchar(255)", nullable=True),
                            TableColumn(name="created_at", type="timestamp", nullable=True),
                        ]
                    ),
                    TableInfo(
                        name="orders",
                        columns=[
                            TableColumn(name="id", type="integer", nullable=False, primaryKey=True),
                            TableColumn(name="customer_id", type="integer", nullable=False),
                            TableColumn(name="total", type="decimal(10,2)", nullable=False),
                            TableColumn(name="status", type="varchar(50)", nullable=True),
                            TableColumn(name="order_date", type="timestamp", nullable=True),
                        ]
                    ),
                    TableInfo(
                        name="products",
                        columns=[
                            TableColumn(name="id", type="integer", nullable=False, primaryKey=True),
                            TableColumn(name="name", type="varchar(255)", nullable=False),
                            TableColumn(name="price", type="decimal(10,2)", nullable=False),
                            TableColumn(name="category", type="varchar(100)", nullable=True),
                        ]
                    ),
                ]
            )
        ]
        
        return RetrieveSchemaResponse(
            success=True,
            schemas=schemas
        )
    except Exception as e:
        return RetrieveSchemaResponse(
            success=False,
            message=f"Failed to retrieve schema: {str(e)}"
        )


# ============================================
# Context Variables Endpoints
# ============================================

@router.get("/contexts", response_model=List[ContextGroup])
async def list_contexts():
    """List all context groups"""
    return load_contexts()


@router.post("/contexts", response_model=ContextGroup)
async def create_context(context: ContextGroup):
    """Create a new context group"""
    contexts = load_contexts()
    
    # Generate ID if not provided
    if not context.id:
        context.id = f"ctx-{uuid4()}"
    
    # Generate IDs for variables
    for var in context.variables:
        if not var.id:
            var.id = f"var-{uuid4()}"
    
    # Check for duplicate names
    if any(c.name == context.name for c in contexts):
        raise HTTPException(status_code=400, detail="Context name already exists")
    
    contexts.append(context)
    save_contexts(contexts)
    return context


@router.get("/contexts/{context_id}", response_model=ContextGroup)
async def get_context(context_id: str):
    """Get a specific context group by ID"""
    contexts = load_contexts()
    for ctx in contexts:
        if ctx.id == context_id:
            return ctx
    raise HTTPException(status_code=404, detail="Context not found")


@router.put("/contexts/{context_id}", response_model=ContextGroup)
async def update_context(context_id: str, context: ContextGroup):
    """Update an existing context group"""
    contexts = load_contexts()
    for i, ctx in enumerate(contexts):
        if ctx.id == context_id:
            context.id = context_id
            # Generate IDs for new variables
            for var in context.variables:
                if not var.id:
                    var.id = f"var-{uuid4()}"
            contexts[i] = context
            save_contexts(contexts)
            return context
    raise HTTPException(status_code=404, detail="Context not found")


@router.delete("/contexts/{context_id}")
async def delete_context(context_id: str):
    """Delete a context group"""
    contexts = load_contexts()
    contexts = [c for c in contexts if c.id != context_id]
    save_contexts(contexts)
    return {"status": "deleted"}


@router.put("/contexts", response_model=List[ContextGroup])
async def update_all_contexts(contexts: List[ContextGroup]):
    """Update all context groups at once"""
    # Generate IDs for new contexts and variables
    for ctx in contexts:
        if not ctx.id:
            ctx.id = f"ctx-{uuid4()}"
        for var in ctx.variables:
            if not var.id:
                var.id = f"var-{uuid4()}"
    
    save_contexts(contexts)
    return contexts
