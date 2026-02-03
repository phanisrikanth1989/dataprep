import { useState, useCallback, useEffect } from 'react';
import {
  Modal,
  Steps,
  Form,
  Input,
  Select,
  InputNumber,
  Switch,
  Button,
  Space,
  Table,
  Checkbox,
  message,
  Spin,
  Alert,
  Divider,
  Typography,
  Tag,
  Tooltip,
  Progress,
} from 'antd';
import {
  DatabaseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  InfoCircleOutlined,
  LockOutlined,
  TableOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import type { DBConnection, DBSchema, DBTable, DBColumn, DEFAULT_DB_PORTS } from '../types/repository';
import './DBConnectionWizard.css';

const { Text, Title } = Typography;

interface Props {
  // Support both prop naming patterns
  open?: boolean;
  visible?: boolean;
  onClose?: () => void;
  onCancel?: () => void;
  onSave: (connection: DBConnection) => void;
  editConnection?: DBConnection | null;
  connection?: DBConnection;
}

const DB_TYPES = [
  { value: 'postgres', label: 'PostgreSQL', icon: '🐘', defaultPort: 5432 },
  { value: 'mysql', label: 'MySQL', icon: '🐬', defaultPort: 3306 },
  { value: 'oracle', label: 'Oracle', icon: '🔴', defaultPort: 1521 },
  { value: 'sqlserver', label: 'SQL Server', icon: '🔷', defaultPort: 1433 },
  { value: 'db2', label: 'IBM DB2', icon: '📘', defaultPort: 50000 },
  { value: 'sqlite', label: 'SQLite', icon: '📦', defaultPort: 0 },
];

const SSL_MODES = [
  { value: 'disable', label: 'Disable' },
  { value: 'allow', label: 'Allow' },
  { value: 'prefer', label: 'Prefer' },
  { value: 'require', label: 'Require' },
  { value: 'verify-ca', label: 'Verify CA' },
  { value: 'verify-full', label: 'Verify Full' },
];

export default function DBConnectionWizard({ 
  open, 
  visible,
  onClose, 
  onCancel,
  onSave, 
  editConnection,
  connection,
}: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [form] = Form.useForm();
  const [advancedForm] = Form.useForm();
  
  // Support both prop patterns
  const isOpen = open ?? visible ?? false;
  const handleClose = onClose ?? onCancel ?? (() => {});
  const connToEdit = editConnection ?? connection ?? null;
  
  // State
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState('');
  const [schemas, setSchemas] = useState<DBSchema[]>([]);
  const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
  const [tables, setTables] = useState<DBTable[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [loadingSchemas, setLoadingSchemas] = useState(false);
  const [loadingTables, setLoadingTables] = useState(false);
  const [tableSearch, setTableSearch] = useState('');
  const [previewColumns, setPreviewColumns] = useState<DBColumn[]>([]);

  // Reset form when opening
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(0);
      setTestStatus('idle');
      setTestMessage('');
      setSchemas([]);
      setSelectedSchema(null);
      setTables([]);
      setSelectedTables([]);
      
      if (connToEdit) {
        form.setFieldsValue({
          name: connToEdit.name,
          dbType: connToEdit.dbType || connToEdit.type,
          host: connToEdit.host,
          port: connToEdit.port,
          database: connToEdit.database,
          serviceName: connToEdit.serviceName,
          username: connToEdit.username,
          password: connToEdit.password,
          ssl: connToEdit.ssl,
          sslMode: connToEdit.sslMode,
        });
        advancedForm.setFieldsValue({
          connectionTimeout: connToEdit.connectionTimeout,
          fetchSize: connToEdit.fetchSize,
          autoCommit: connToEdit.autoCommit,
          readOnly: connToEdit.readOnly,
          driverClass: connToEdit.driverClass,
          jdbcUrl: connToEdit.jdbcUrl,
        });
      } else {
        form.resetFields();
        advancedForm.resetFields();
        advancedForm.setFieldsValue({
          connectionTimeout: 30,
          fetchSize: 1000,
          autoCommit: true,
          readOnly: false,
        });
      }
    }
  }, [open, editConnection, form, advancedForm]);

  // Handle DB type change - update port
  const handleDbTypeChange = (dbType: string) => {
    const dbConfig = DB_TYPES.find((db) => db.value === dbType);
    if (dbConfig && !form.getFieldValue('port')) {
      form.setFieldValue('port', dbConfig.defaultPort);
    }
  };

  // Test connection
  const testConnection = async () => {
    try {
      await form.validateFields();
      setTestStatus('testing');
      setTestMessage('Testing connection...');

      // Simulate connection test (replace with actual API call)
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Simulate success/failure
      const success = Math.random() > 0.2; // 80% success rate for demo
      if (success) {
        setTestStatus('success');
        setTestMessage('Connection successful!');
      } else {
        setTestStatus('error');
        setTestMessage('Connection failed: Unable to connect to database');
      }
    } catch (error) {
      setTestStatus('error');
      setTestMessage('Please fill in all required fields');
    }
  };

  // Retrieve schemas
  const retrieveSchemas = async () => {
    setLoadingSchemas(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1500));
      
      // Mock schemas
      setSchemas([
        { name: 'public', tables: [] },
        { name: 'sales', tables: [] },
        { name: 'hr', tables: [] },
        { name: 'inventory', tables: [] },
      ]);
    } catch (error) {
      message.error('Failed to retrieve schemas');
    } finally {
      setLoadingSchemas(false);
    }
  };

  // Load tables for selected schema
  const loadTables = async (schemaName: string) => {
    setSelectedSchema(schemaName);
    setLoadingTables(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000));
      
      // Mock tables
      const mockTables: DBTable[] = [
        { name: 'customers', schema: schemaName, type: 'TABLE', rowCount: 5000, columns: [] },
        { name: 'orders', schema: schemaName, type: 'TABLE', rowCount: 25000, columns: [] },
        { name: 'products', schema: schemaName, type: 'TABLE', rowCount: 1000, columns: [] },
        { name: 'order_items', schema: schemaName, type: 'TABLE', rowCount: 75000, columns: [] },
        { name: 'categories', schema: schemaName, type: 'TABLE', rowCount: 50, columns: [] },
        { name: 'customer_view', schema: schemaName, type: 'VIEW', rowCount: 5000, columns: [] },
      ];
      setTables(mockTables);
    } catch (error) {
      message.error('Failed to load tables');
    } finally {
      setLoadingTables(false);
    }
  };

  // Preview columns for a table
  const previewTable = async (tableName: string) => {
    // Mock columns
    const mockColumns: DBColumn[] = [
      { name: 'id', type: 'INTEGER', nullable: false, primaryKey: true },
      { name: 'name', type: 'VARCHAR', nullable: false, primaryKey: false, length: 255 },
      { name: 'email', type: 'VARCHAR', nullable: true, primaryKey: false, length: 255 },
      { name: 'created_at', type: 'TIMESTAMP', nullable: false, primaryKey: false },
      { name: 'updated_at', type: 'TIMESTAMP', nullable: true, primaryKey: false },
      { name: 'status', type: 'VARCHAR', nullable: false, primaryKey: false, length: 50 },
    ];
    setPreviewColumns(mockColumns);
  };

  // Handle step navigation
  const nextStep = async () => {
    if (currentStep === 0) {
      try {
        await form.validateFields();
        setCurrentStep(1);
      } catch {
        message.error('Please fill in all required fields');
      }
    } else if (currentStep === 1) {
      setCurrentStep(2);
      retrieveSchemas();
    }
  };

  const prevStep = () => {
    setCurrentStep(currentStep - 1);
  };

  // Handle finish
  const handleFinish = () => {
    const basicValues = form.getFieldsValue();
    const advancedValues = advancedForm.getFieldsValue();

    const connection: DBConnection = {
      id: editConnection?.id || `conn_${Date.now()}`,
      name: basicValues.name,
      dbType: basicValues.dbType,
      host: basicValues.host,
      port: basicValues.port,
      database: basicValues.database,
      serviceName: basicValues.serviceName,
      username: basicValues.username,
      password: basicValues.password,
      ssl: basicValues.ssl || false,
      sslMode: basicValues.sslMode,
      connectionTimeout: advancedValues.connectionTimeout || 30,
      fetchSize: advancedValues.fetchSize || 1000,
      autoCommit: advancedValues.autoCommit ?? true,
      readOnly: advancedValues.readOnly || false,
      driverClass: advancedValues.driverClass,
      jdbcUrl: advancedValues.jdbcUrl,
      status: testStatus === 'success' ? 'connected' : 'disconnected',
      lastTested: testStatus === 'success' ? new Date().toISOString() : undefined,
      createdAt: connToEdit?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    onSave(connection);
    handleClose();
  };

  // Filter tables by search
  const filteredTables = tables.filter((t) =>
    t.name.toLowerCase().includes(tableSearch.toLowerCase())
  );

  // Step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="wizard-step-content">
            <Form form={form} layout="vertical" requiredMark="optional">
              <Form.Item
                name="name"
                label="Connection Name"
                rules={[{ required: true, message: 'Please enter a connection name' }]}
              >
                <Input placeholder="e.g., Production Database" prefix={<DatabaseOutlined />} />
              </Form.Item>

              <Form.Item
                name="dbType"
                label="Database Type"
                rules={[{ required: true, message: 'Please select a database type' }]}
              >
                <Select
                  placeholder="Select database type"
                  onChange={handleDbTypeChange}
                  options={DB_TYPES.map((db) => ({
                    value: db.value,
                    label: (
                      <span>
                        {db.icon} {db.label}
                      </span>
                    ),
                  }))}
                />
              </Form.Item>

              <div className="form-row">
                <Form.Item
                  name="host"
                  label="Host"
                  rules={[{ required: true, message: 'Required' }]}
                  style={{ flex: 2 }}
                >
                  <Input placeholder="localhost or IP address" />
                </Form.Item>

                <Form.Item
                  name="port"
                  label="Port"
                  rules={[{ required: true, message: 'Required' }]}
                  style={{ flex: 1 }}
                >
                  <InputNumber min={1} max={65535} style={{ width: '100%' }} />
                </Form.Item>
              </div>

              <Form.Item
                name="database"
                label="Database / Schema"
                rules={[{ required: true, message: 'Please enter database name' }]}
              >
                <Input placeholder="Database name" />
              </Form.Item>

              <Form.Item
                name="serviceName"
                label="Service Name / SID"
                tooltip="For Oracle connections"
              >
                <Input placeholder="Optional - for Oracle" />
              </Form.Item>

              <Divider />

              <div className="form-row">
                <Form.Item
                  name="username"
                  label="Username"
                  rules={[{ required: true, message: 'Required' }]}
                  style={{ flex: 1 }}
                >
                  <Input placeholder="Database username" />
                </Form.Item>

                <Form.Item
                  name="password"
                  label="Password"
                  rules={[{ required: true, message: 'Required' }]}
                  style={{ flex: 1 }}
                >
                  <Input.Password placeholder="Database password" prefix={<LockOutlined />} />
                </Form.Item>
              </div>

              <div className="form-row">
                <Form.Item name="ssl" label="Enable SSL" valuePropName="checked">
                  <Switch />
                </Form.Item>

                <Form.Item name="sslMode" label="SSL Mode" style={{ flex: 1 }}>
                  <Select placeholder="Select SSL mode" options={SSL_MODES} allowClear />
                </Form.Item>
              </div>

              {/* Test Connection Section */}
              <div className="test-connection-section">
                <Button
                  type="default"
                  icon={
                    testStatus === 'testing' ? (
                      <LoadingOutlined />
                    ) : testStatus === 'success' ? (
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    ) : testStatus === 'error' ? (
                      <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                    ) : (
                      <DatabaseOutlined />
                    )
                  }
                  onClick={testConnection}
                  loading={testStatus === 'testing'}
                >
                  Test Connection
                </Button>
                {testMessage && (
                  <Alert
                    message={testMessage}
                    type={testStatus === 'success' ? 'success' : testStatus === 'error' ? 'error' : 'info'}
                    showIcon
                    style={{ marginTop: 12 }}
                  />
                )}
              </div>
            </Form>
          </div>
        );

      case 1:
        return (
          <div className="wizard-step-content">
            <Form form={advancedForm} layout="vertical" requiredMark="optional">
              <Title level={5}>Connection Settings</Title>
              
              <div className="form-row">
                <Form.Item
                  name="connectionTimeout"
                  label="Connection Timeout (seconds)"
                  style={{ flex: 1 }}
                >
                  <InputNumber min={1} max={300} style={{ width: '100%' }} />
                </Form.Item>

                <Form.Item
                  name="fetchSize"
                  label="Fetch Size (rows)"
                  style={{ flex: 1 }}
                >
                  <InputNumber min={1} max={100000} style={{ width: '100%' }} />
                </Form.Item>
              </div>

              <div className="form-row">
                <Form.Item
                  name="autoCommit"
                  label="Auto Commit"
                  valuePropName="checked"
                  tooltip="Automatically commit each statement"
                >
                  <Switch />
                </Form.Item>

                <Form.Item
                  name="readOnly"
                  label="Read Only"
                  valuePropName="checked"
                  tooltip="Connection in read-only mode"
                >
                  <Switch />
                </Form.Item>
              </div>

              <Divider />

              <Title level={5}>Advanced Options</Title>

              <Form.Item
                name="driverClass"
                label="JDBC Driver Class"
                tooltip="Override default driver class"
              >
                <Input placeholder="e.g., org.postgresql.Driver" />
              </Form.Item>

              <Form.Item
                name="jdbcUrl"
                label="Custom JDBC URL"
                tooltip="Override auto-generated URL"
              >
                <Input.TextArea
                  placeholder="jdbc:postgresql://host:port/database"
                  rows={2}
                />
              </Form.Item>

              <Alert
                message="Tip"
                description="Leave advanced options empty to use default values based on your database type."
                type="info"
                showIcon
                style={{ marginTop: 16 }}
              />
            </Form>
          </div>
        );

      case 2:
        return (
          <div className="wizard-step-content schema-retrieval">
            <div className="schema-panels">
              {/* Schemas Panel */}
              <div className="schema-panel">
                <div className="panel-header">
                  <span>Schemas</span>
                  <Button
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={retrieveSchemas}
                    loading={loadingSchemas}
                  >
                    Refresh
                  </Button>
                </div>
                <div className="panel-content">
                  {loadingSchemas ? (
                    <div className="loading-state">
                      <Spin />
                      <span>Loading schemas...</span>
                    </div>
                  ) : schemas.length === 0 ? (
                    <div className="empty-state">
                      <Text type="secondary">Click "Refresh" to load schemas</Text>
                    </div>
                  ) : (
                    <div className="schema-list">
                      {schemas.map((schema) => (
                        <div
                          key={schema.name}
                          className={`schema-item ${selectedSchema === schema.name ? 'selected' : ''}`}
                          onClick={() => loadTables(schema.name)}
                        >
                          <DatabaseOutlined />
                          <span>{schema.name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Tables Panel */}
              <div className="schema-panel">
                <div className="panel-header">
                  <span>Tables / Views</span>
                  <Input
                    size="small"
                    placeholder="Search..."
                    prefix={<SearchOutlined />}
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    style={{ width: 150 }}
                    allowClear
                  />
                </div>
                <div className="panel-content">
                  {loadingTables ? (
                    <div className="loading-state">
                      <Spin />
                      <span>Loading tables...</span>
                    </div>
                  ) : !selectedSchema ? (
                    <div className="empty-state">
                      <Text type="secondary">Select a schema to view tables</Text>
                    </div>
                  ) : filteredTables.length === 0 ? (
                    <div className="empty-state">
                      <Text type="secondary">No tables found</Text>
                    </div>
                  ) : (
                    <div className="table-list">
                      {filteredTables.map((table) => (
                        <div
                          key={table.name}
                          className="table-item"
                          onClick={() => previewTable(table.name)}
                        >
                          <Checkbox
                            checked={selectedTables.includes(table.name)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedTables([...selectedTables, table.name]);
                              } else {
                                setSelectedTables(selectedTables.filter((t) => t !== table.name));
                              }
                            }}
                          />
                          <TableOutlined style={{ color: table.type === 'VIEW' ? '#722ed1' : '#1890ff' }} />
                          <span className="table-name">{table.name}</span>
                          <Tag color={table.type === 'VIEW' ? 'purple' : 'blue'} className="table-type">
                            {table.type}
                          </Tag>
                          {table.rowCount && (
                            <span className="row-count">{table.rowCount.toLocaleString()} rows</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="panel-footer">
                  <Button
                    size="small"
                    onClick={() => setSelectedTables(filteredTables.map((t) => t.name))}
                    disabled={filteredTables.length === 0}
                  >
                    Select All
                  </Button>
                  <Button
                    size="small"
                    onClick={() => setSelectedTables([])}
                    disabled={selectedTables.length === 0}
                  >
                    Clear Selection
                  </Button>
                </div>
              </div>

              {/* Columns Preview Panel */}
              <div className="schema-panel">
                <div className="panel-header">
                  <span>Column Preview</span>
                </div>
                <div className="panel-content">
                  {previewColumns.length === 0 ? (
                    <div className="empty-state">
                      <Text type="secondary">Click a table to preview columns</Text>
                    </div>
                  ) : (
                    <Table
                      dataSource={previewColumns}
                      columns={[
                        {
                          title: 'Column',
                          dataIndex: 'name',
                          render: (name, record) => (
                            <span>
                              {record.primaryKey && <span className="pk-indicator">🔑</span>}
                              {name}
                            </span>
                          ),
                        },
                        { title: 'Type', dataIndex: 'type', width: 100 },
                        {
                          title: 'Null',
                          dataIndex: 'nullable',
                          width: 50,
                          render: (v) => (v ? '✓' : '✗'),
                        },
                      ]}
                      size="small"
                      pagination={false}
                      rowKey="name"
                    />
                  )}
                </div>
              </div>
            </div>

            {selectedTables.length > 0 && (
              <Alert
                message={`${selectedTables.length} table(s) selected`}
                description="These tables will be available in the metadata repository after saving."
                type="success"
                showIcon
                style={{ marginTop: 16 }}
              />
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Modal
      title={
        <div className="wizard-title">
          <DatabaseOutlined />
          <span>{connToEdit ? 'Edit Database Connection' : 'Create Database Connection'}</span>
        </div>
      }
      open={isOpen}
      onCancel={handleClose}
      width={900}
      footer={null}
      className="db-connection-wizard"
      destroyOnClose
    >
      <div className="wizard-container">
        <div className="wizard-steps">
          <Steps
            current={currentStep}
            direction="vertical"
            size="small"
            items={[
              {
                title: 'Connection Details',
                description: 'Basic settings',
              },
              {
                title: 'Advanced Settings',
                description: 'Timeouts & options',
              },
              {
                title: 'Retrieve Schema',
                description: 'Select tables',
              },
            ]}
          />
        </div>

        <div className="wizard-content">
          {renderStepContent()}

          <div className="wizard-footer">
            <Button onClick={handleClose}>Cancel</Button>
            <Space>
              {currentStep > 0 && <Button onClick={prevStep}>Back</Button>}
              {currentStep < 2 ? (
                <Button type="primary" onClick={nextStep}>
                  Next
                </Button>
              ) : (
                <Button type="primary" onClick={handleFinish}>
                  Finish
                </Button>
              )}
            </Space>
          </div>
        </div>
      </div>
    </Modal>
  );
}
