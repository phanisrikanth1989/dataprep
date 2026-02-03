import { useState, useEffect, useMemo } from 'react';
import {
  Tabs,
  Form,
  Input,
  InputNumber,
  Switch,
  Select,
  Button,
  Divider,
  Space,
  Table,
  Tag,
  Tooltip,
  Collapse,
  Alert,
  Empty,
} from 'antd';
import {
  SettingOutlined,
  ThunderboltOutlined,
  TableOutlined,
  WarningOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  LinkOutlined,
  DatabaseOutlined,
  QuestionCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { Node } from '@xyflow/react';
import type { ComponentMetadata, SchemaColumn } from '../types';
import FileBrowser from './FileBrowser';
import './PropertiesPanel.css';

// Local type for DB Connection (avoids import issues)
interface DBConnectionLocal {
  id: string;
  name: string;
  dbType?: string;
  type?: string;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
}

interface Props {
  // Support both prop naming patterns
  node?: Node | null;
  selectedNode?: Node | null;
  component?: ComponentMetadata | null | undefined;
  schema?: SchemaColumn[];
  dbConnections: DBConnectionLocal[];
  onConfigChange?: (config: Record<string, any>) => void;
  onSchemaChange?: (schema: SchemaColumn[]) => void;
  onNodeUpdate?: (node: Node) => void;
  onBrowseFile?: () => void;
  onClose?: () => void;
}

// Fields that should use file browser
const FILE_PATH_FIELDS = ['filepath', 'filename', 'file_path', 'input_file', 'output_file', 'path'];

// Error handling options
const ERROR_HANDLING_OPTIONS = [
  { value: 'die', label: 'Stop job on error' },
  { value: 'continue', label: 'Continue processing' },
  { value: 'reject', label: 'Send to reject flow' },
  { value: 'log', label: 'Log and continue' },
];

export default function PropertiesPanel({
  node,
  selectedNode,
  component,
  schema = [],
  dbConnections,
  onConfigChange,
  onSchemaChange,
  onNodeUpdate,
  onBrowseFile,
  onClose,
}: Props) {
  const [form] = Form.useForm();
  const [advancedForm] = Form.useForm();
  const [errorForm] = Form.useForm();
  const [activeTab, setActiveTab] = useState('basic');
  
  // Use either node or selectedNode
  const activeNode = node ?? selectedNode ?? null;
  const [fileBrowserOpen, setFileBrowserOpen] = useState(false);
  const [activeFileField, setActiveFileField] = useState<string | null>(null);
  const [localSchema, setLocalSchema] = useState<SchemaColumn[]>(schema);

  const nodeData = node?.data as Record<string, any>;

  // Reset forms when node changes
  useEffect(() => {
    if (node && component) {
      const config = nodeData?.config || {};
      
      // Basic settings
      const basicValues: Record<string, any> = {
        _componentName: nodeData?.name || nodeData?.label || '',
      };
      component.fields.forEach((field) => {
        basicValues[field.name] = config[field.name] ?? field.default ?? '';
      });
      form.setFieldsValue(basicValues);

      // Advanced settings
      advancedForm.setFieldsValue({
        parallelism: config._parallelism || 1,
        bufferSize: config._bufferSize || 1000,
        tStatCatcher: config._tStatCatcher || false,
      });

      // Error handling
      errorForm.setFieldsValue({
        errorHandling: config._errorHandling || 'die',
        maxErrors: config._maxErrors || 0,
        logErrors: config._logErrors ?? true,
      });

      // Schema
      setLocalSchema(config.output_schema || schema || []);
    }
  }, [node, component, schema, form, advancedForm, errorForm]);

  // Check if field should use file browser
  const isFilePathField = (fieldName: string) =>
    FILE_PATH_FIELDS.includes(fieldName.toLowerCase());

  // Check if field should show DB connection dropdown
  const isConnectionField = (fieldName: string) =>
    fieldName.toLowerCase().includes('connection');

  // Open file browser
  const openFileBrowser = (fieldName: string) => {
    setActiveFileField(fieldName);
    setFileBrowserOpen(true);
  };

  // Handle file selection
  const handleFileSelect = (path: string) => {
    if (activeFileField) {
      form.setFieldValue(activeFileField, path);
    }
    setFileBrowserOpen(false);
    setActiveFileField(null);
  };

  // Save all configurations (auto-save)
  const handleSave = () => {
    const basicValues = form.getFieldsValue();
    const advancedValues = advancedForm.getFieldsValue();
    const errorValues = errorForm.getFieldsValue();

    const config = {
      ...basicValues,
      _componentName: basicValues._componentName,
      _parallelism: advancedValues.parallelism,
      _bufferSize: advancedValues.bufferSize,
      _tStatCatcher: advancedValues.tStatCatcher,
      _errorHandling: errorValues.errorHandling,
      _maxErrors: errorValues.maxErrors,
      _logErrors: errorValues.logErrors,
      output_schema: localSchema,
    };

    // Remove the temporary name field
    delete config._componentName;
    
    const finalConfig = {
      ...config,
      _nodeName: basicValues._componentName,
    };
    
    // Support both callback patterns
    if (onConfigChange) {
      onConfigChange(finalConfig);
    }
    if (onNodeUpdate && activeNode) {
      onNodeUpdate({
        ...activeNode,
        data: {
          ...(activeNode.data as any),
          config: finalConfig,
          name: basicValues._componentName,
        },
      });
    }
  };

  // Auto-save on form value change
  const handleValuesChange = () => {
    // Debounce auto-save
    setTimeout(() => {
      handleSave();
    }, 300);
  };

  // Render form field based on type
  const renderField = (field: any) => {
    // DB Connection dropdown
    if (isConnectionField(field.name)) {
      return (
        <Select
          placeholder="Select connection"
          allowClear
          showSearch
          optionFilterProp="children"
        >
          <Select.OptGroup label="Available Connections">
            {dbConnections.map((conn) => (
              <Select.Option key={conn.id} value={conn.id}>
                <Space>
                  <DatabaseOutlined style={{ color: '#52c41a' }} />
                  {conn.name}
                  <Tag color="blue" style={{ fontSize: 10 }}>{conn.dbType}</Tag>
                </Space>
              </Select.Option>
            ))}
          </Select.OptGroup>
        </Select>
      );
    }

    // File path with browser
    if (field.type === 'text' && isFilePathField(field.name)) {
      return (
        <Space.Compact style={{ width: '100%' }}>
          <Form.Item name={field.name} noStyle>
            <Input placeholder={field.placeholder} style={{ width: 'calc(100% - 32px)' }} />
          </Form.Item>
          <Button icon={<FolderOpenOutlined />} onClick={() => openFileBrowser(field.name)} />
        </Space.Compact>
      );
    }

    // Standard field types
    switch (field.type) {
      case 'text':
        return <Input placeholder={field.placeholder} />;
      case 'number':
        return <InputNumber style={{ width: '100%' }} placeholder={field.placeholder} />;
      case 'boolean':
        return <Switch />;
      case 'select':
        return (
          <Select placeholder={`Select ${field.label}`}>
            {field.options?.map((opt: string) => (
              <Select.Option key={opt} value={opt}>{opt}</Select.Option>
            ))}
          </Select>
        );
      case 'expression':
        return (
          <Input.TextArea
            rows={3}
            placeholder={field.placeholder}
            className="expression-input"
          />
        );
      default:
        return <Input placeholder={field.placeholder} />;
    }
  };

  // Schema editor
  const addSchemaColumn = () => {
    setLocalSchema([...localSchema, { name: '', type: 'id_String', nullable: true }]);
  };

  const updateSchemaColumn = (index: number, field: keyof SchemaColumn, value: any) => {
    const updated = [...localSchema];
    updated[index] = { ...updated[index], [field]: value };
    setLocalSchema(updated);
  };

  const deleteSchemaColumn = (index: number) => {
    setLocalSchema(localSchema.filter((_, i) => i !== index));
  };

  // No node selected
  if (!activeNode || !component) {
    return (
      <div className="properties-panel empty">
        <Empty
          description="Select a component to view properties"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  // Tab items
  const tabItems = [
    {
      key: 'basic',
      label: (
        <span>
          <SettingOutlined /> Basic
        </span>
      ),
      children: (
        <div className="tab-content">
          <Form form={form} layout="vertical" size="small" onValuesChange={handleValuesChange}>
            {/* Component Name */}
            <Form.Item
              name="_componentName"
              label="Component Name"
              tooltip="Custom name for this component"
            >
              <Input placeholder="e.g., Read Customer Data" />
            </Form.Item>

            <Divider style={{ margin: '12px 0' }} />

            {/* Dynamic Fields */}
            {component.fields.map((field) => (
              <Form.Item
                key={field.name}
                name={field.name}
                label={
                  <Space>
                    {field.label}
                    {field.required && <Tag color="red" style={{ fontSize: 10 }}>Required</Tag>}
                  </Space>
                }
                rules={field.required ? [{ required: true, message: `${field.label} is required` }] : []}
                tooltip={field.description}
                valuePropName={field.type === 'boolean' ? 'checked' : 'value'}
              >
                {renderField(field)}
              </Form.Item>
            ))}
          </Form>
        </div>
      ),
    },
    {
      key: 'advanced',
      label: (
        <span>
          <ThunderboltOutlined /> Advanced
        </span>
      ),
      children: (
        <div className="tab-content">
          <Form form={advancedForm} layout="vertical" size="small" onValuesChange={handleValuesChange}>
            <Form.Item
              name="parallelism"
              label="Parallelism"
              tooltip="Number of parallel execution threads"
            >
              <InputNumber min={1} max={16} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              name="bufferSize"
              label="Buffer Size"
              tooltip="Internal buffer size for data processing"
            >
              <InputNumber min={100} max={100000} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              name="tStatCatcher"
              label="Enable Statistics"
              tooltip="Collect runtime statistics"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>

            <Divider />

            <Alert
              message="Advanced settings"
              description="These settings affect performance and resource usage. Use default values unless you have specific requirements."
              type="info"
              showIcon
              style={{ marginTop: 16 }}
            />
          </Form>
        </div>
      ),
    },
    {
      key: 'schema',
      label: (
        <span>
          <TableOutlined /> Schema
        </span>
      ),
      children: (
        <div className="tab-content schema-tab">
          <div className="schema-header">
            <span>Output Schema ({localSchema.length} columns)</span>
            <Button icon={<PlusOutlined />} size="small" onClick={addSchemaColumn}>
              Add Column
            </Button>
          </div>

          {localSchema.length === 0 ? (
            <Empty
              description="No schema defined"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button type="primary" onClick={addSchemaColumn}>Add First Column</Button>
            </Empty>
          ) : (
            <Table
              dataSource={localSchema.map((col, idx) => ({ ...col, key: idx }))}
              columns={[
                {
                  title: 'Name',
                  dataIndex: 'name',
                  render: (value, _, index) => (
                    <Input
                      size="small"
                      value={value}
                      onChange={(e) => updateSchemaColumn(index, 'name', e.target.value)}
                      placeholder="Column name"
                    />
                  ),
                },
                {
                  title: 'Type',
                  dataIndex: 'type',
                  width: 120,
                  render: (value, _, index) => (
                    <Select
                      size="small"
                      value={value}
                      onChange={(v) => updateSchemaColumn(index, 'type', v)}
                      style={{ width: '100%' }}
                    >
                      <Select.Option value="id_String">String</Select.Option>
                      <Select.Option value="id_Integer">Integer</Select.Option>
                      <Select.Option value="id_Long">Long</Select.Option>
                      <Select.Option value="id_Double">Double</Select.Option>
                      <Select.Option value="id_Boolean">Boolean</Select.Option>
                      <Select.Option value="id_Date">Date</Select.Option>
                    </Select>
                  ),
                },
                {
                  title: 'Null',
                  dataIndex: 'nullable',
                  width: 60,
                  render: (value, _, index) => (
                    <Switch
                      size="small"
                      checked={value}
                      onChange={(v) => updateSchemaColumn(index, 'nullable', v)}
                    />
                  ),
                },
                {
                  title: '',
                  width: 40,
                  render: (_, __, index) => (
                    <Button
                      type="text"
                      danger
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={() => deleteSchemaColumn(index)}
                    />
                  ),
                },
              ]}
              size="small"
              pagination={false}
              scroll={{ y: 250 }}
            />
          )}

          <div className="schema-actions">
            <Button size="small" onClick={() => onSchemaChange?.(localSchema)}>
              Apply Schema
            </Button>
          </div>
        </div>
      ),
    },
    {
      key: 'error',
      label: (
        <span>
          <WarningOutlined /> Error Handling
        </span>
      ),
      children: (
        <div className="tab-content">
          <Form form={errorForm} layout="vertical" size="small" onValuesChange={handleValuesChange}>
            <Form.Item
              name="errorHandling"
              label="Error Handling Mode"
              tooltip="How to handle errors during execution"
            >
              <Select options={ERROR_HANDLING_OPTIONS} />
            </Form.Item>

            <Form.Item
              name="maxErrors"
              label="Max Errors"
              tooltip="Maximum number of errors before stopping (0 = unlimited)"
            >
              <InputNumber min={0} max={10000} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              name="logErrors"
              label="Log Errors"
              tooltip="Write errors to execution log"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </Form>
        </div>
      ),
    },
    {
      key: 'doc',
      label: (
        <span>
          <FileTextOutlined /> Doc
        </span>
      ),
      children: (
        <div className="tab-content doc-tab">
          <h4>{component.label}</h4>
          <Tag color="blue">{component.category}</Tag>

          <Divider style={{ margin: '12px 0' }} />

          <p className="description">{component.description || 'No description available'}</p>

          <h5>Connections</h5>
          <div className="connections-info">
            <span>Inputs: {component.input_count}</span>
            <span>Outputs: {component.output_count}</span>
          </div>

          <Divider style={{ margin: '12px 0' }} />

          <h5>Properties</h5>
          <div className="props-list">
            {component.fields.map((field) => (
              <div key={field.name} className="prop-item">
                <span className="prop-name">{field.label}</span>
                {field.required && <Tag color="red" className="required-tag">Required</Tag>}
                <span className="prop-type">{field.type}</span>
              </div>
            ))}
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="properties-panel">
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        size="small"
        className="properties-tabs"
      />

      <FileBrowser
        open={fileBrowserOpen}
        onClose={() => setFileBrowserOpen(false)}
        onSelect={handleFileSelect}
        mode="file"
        title="Select File"
      />
    </div>
  );
}
