import { useState, useCallback } from 'react';
import {
  Modal,
  Steps,
  Button,
  Form,
  Input,
  Select,
  Upload,
  Table,
  InputNumber,
  Switch,
  Space,
  message,
  Divider,
  Typography,
  Alert,
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  TableOutlined,
  CheckCircleOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import { v4 as uuidv4 } from 'uuid';
import './FileMetadataWizard.css';

const { Text, Title } = Typography;
const { Dragger } = Upload;

interface SchemaColumn {
  name: string;
  type: string;
  length?: number;
  precision?: number;
  nullable: boolean;
}

interface FileMetadata {
  id: string;
  name: string;
  type: 'delimited' | 'excel' | 'json' | 'xml';
  filePath?: string;
  schema: SchemaColumn[];
  settings: Record<string, any>;
}

interface Props {
  visible: boolean;
  fileType: 'delimited' | 'excel' | 'json' | 'xml';
  onSave: (metadata: FileMetadata) => void;
  onCancel: () => void;
}

const DATA_TYPES = [
  { value: 'String', label: 'String' },
  { value: 'Integer', label: 'Integer' },
  { value: 'Long', label: 'Long' },
  { value: 'Float', label: 'Float' },
  { value: 'Double', label: 'Double' },
  { value: 'Boolean', label: 'Boolean' },
  { value: 'Date', label: 'Date' },
  { value: 'Timestamp', label: 'Timestamp' },
  { value: 'BigDecimal', label: 'BigDecimal' },
];

const DELIMITERS = [
  { value: ',', label: 'Comma (,)' },
  { value: ';', label: 'Semicolon (;)' },
  { value: '\t', label: 'Tab (\\t)' },
  { value: '|', label: 'Pipe (|)' },
  { value: ' ', label: 'Space' },
];

const ENCODINGS = [
  { value: 'UTF-8', label: 'UTF-8' },
  { value: 'UTF-16', label: 'UTF-16' },
  { value: 'ISO-8859-1', label: 'ISO-8859-1 (Latin-1)' },
  { value: 'ASCII', label: 'ASCII' },
  { value: 'Windows-1252', label: 'Windows-1252' },
];

export default function FileMetadataWizard({ visible, fileType, onSave, onCancel }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [form] = Form.useForm();
  const [schema, setSchema] = useState<SchemaColumn[]>([]);
  const [previewData, setPreviewData] = useState<string[][]>([]);
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState(false);

  // Reset state when modal closes
  const handleCancel = () => {
    setCurrentStep(0);
    setSchema([]);
    setPreviewData([]);
    setFileContent('');
    form.resetFields();
    onCancel();
  };

  // Parse delimited file content
  const parseDelimitedFile = useCallback((content: string, delimiter: string, hasHeader: boolean) => {
    const lines = content.split(/\r?\n/).filter(line => line.trim());
    if (lines.length === 0) return { columns: [], data: [] };

    const rows = lines.map(line => {
      // Simple CSV parsing (doesn't handle quoted fields with delimiters inside)
      return line.split(delimiter).map(cell => cell.trim().replace(/^["']|["']$/g, ''));
    });

    const headerRow = hasHeader ? rows[0] : rows[0].map((_, i) => `Column_${i + 1}`);
    const dataRows = hasHeader ? rows.slice(1) : rows;

    // Infer column types from data
    const columns: SchemaColumn[] = headerRow.map((name, colIndex) => {
      const values = dataRows.map(row => row[colIndex]).filter(v => v !== undefined && v !== '');
      const inferredType = inferDataType(values);
      return {
        name: name || `Column_${colIndex + 1}`,
        type: inferredType,
        nullable: true,
      };
    });

    return { columns, data: dataRows.slice(0, 10) }; // Preview first 10 rows
  }, []);

  // Infer data type from values
  const inferDataType = (values: string[]): string => {
    if (values.length === 0) return 'String';

    const sample = values.slice(0, 100); // Sample first 100 values

    // Check if all values are integers
    if (sample.every(v => /^-?\d+$/.test(v))) {
      const maxVal = Math.max(...sample.map(v => Math.abs(parseInt(v))));
      return maxVal > 2147483647 ? 'Long' : 'Integer';
    }

    // Check if all values are numbers
    if (sample.every(v => /^-?\d*\.?\d+$/.test(v))) {
      return 'Double';
    }

    // Check if all values are booleans
    if (sample.every(v => /^(true|false|yes|no|1|0)$/i.test(v))) {
      return 'Boolean';
    }

    // Check if all values are dates
    if (sample.every(v => !isNaN(Date.parse(v)) && v.length > 6)) {
      return 'Date';
    }

    return 'String';
  };

  // Handle file upload
  const handleFileUpload = (file: File) => {
    setLoading(true);
    const reader = new FileReader();

    reader.onload = (e) => {
      const content = e.target?.result as string;
      setFileContent(content);

      // Get current form values
      const values = form.getFieldsValue();
      const delimiter = values.delimiter || ',';
      const hasHeader = values.hasHeader !== false;

      if (fileType === 'delimited') {
        const { columns, data } = parseDelimitedFile(content, delimiter, hasHeader);
        setSchema(columns);
        setPreviewData(data);
      } else if (fileType === 'json') {
        try {
          const json = JSON.parse(content);
          const columns = inferJsonSchema(json);
          setSchema(columns);
          setPreviewData([]);
        } catch {
          message.error('Invalid JSON file');
        }
      }

      setLoading(false);
      message.success(`File "${file.name}" loaded successfully`);
    };

    reader.onerror = () => {
      setLoading(false);
      message.error('Failed to read file');
    };

    reader.readAsText(file);
    return false; // Prevent upload
  };

  // Infer JSON schema
  const inferJsonSchema = (json: any): SchemaColumn[] => {
    const sample = Array.isArray(json) ? json[0] : json;
    if (!sample || typeof sample !== 'object') return [];

    return Object.entries(sample).map(([key, value]) => ({
      name: key,
      type: inferJsonType(value),
      nullable: true,
    }));
  };

  const inferJsonType = (value: any): string => {
    if (value === null) return 'String';
    if (typeof value === 'number') return Number.isInteger(value) ? 'Integer' : 'Double';
    if (typeof value === 'boolean') return 'Boolean';
    if (typeof value === 'string') {
      if (!isNaN(Date.parse(value)) && value.length > 6) return 'Date';
    }
    return 'String';
  };

  // Re-parse when settings change
  const handleSettingsChange = () => {
    if (!fileContent) return;

    const values = form.getFieldsValue();
    const delimiter = values.delimiter || ',';
    const hasHeader = values.hasHeader !== false;

    if (fileType === 'delimited') {
      const { columns, data } = parseDelimitedFile(fileContent, delimiter, hasHeader);
      setSchema(columns);
      setPreviewData(data);
    }
  };

  // Update schema column
  const updateSchemaColumn = (index: number, field: string, value: any) => {
    setSchema(prev => prev.map((col, i) => 
      i === index ? { ...col, [field]: value } : col
    ));
  };

  // Add new column
  const addColumn = () => {
    setSchema(prev => [...prev, {
      name: `Column_${prev.length + 1}`,
      type: 'String',
      nullable: true,
    }]);
  };

  // Remove column
  const removeColumn = (index: number) => {
    setSchema(prev => prev.filter((_, i) => i !== index));
  };

  // Handle save
  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      
      const metadata: FileMetadata = {
        id: uuidv4(),
        name: values.name,
        type: fileType,
        filePath: values.filePath,
        schema,
        settings: {
          delimiter: values.delimiter,
          encoding: values.encoding,
          hasHeader: values.hasHeader,
          textEnclosure: values.textEnclosure,
          escapeChar: values.escapeChar,
          skipRows: values.skipRows,
          sheetName: values.sheetName,
        },
      };

      onSave(metadata);
      handleCancel();
      message.success(`${fileType} metadata "${values.name}" created successfully`);
    } catch (error) {
      // Validation failed
    }
  };

  // Schema columns for table
  const schemaColumns = [
    {
      title: 'Column Name',
      dataIndex: 'name',
      width: 150,
      render: (value: string, _: any, index: number) => (
        <Input
          size="small"
          value={value}
          onChange={(e) => updateSchemaColumn(index, 'name', e.target.value)}
        />
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      width: 120,
      render: (value: string, _: any, index: number) => (
        <Select
          size="small"
          value={value}
          onChange={(v) => updateSchemaColumn(index, 'type', v)}
          options={DATA_TYPES}
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: 'Length',
      dataIndex: 'length',
      width: 80,
      render: (value: number, _: any, index: number) => (
        <InputNumber
          size="small"
          value={value}
          onChange={(v) => updateSchemaColumn(index, 'length', v)}
          min={0}
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: 'Nullable',
      dataIndex: 'nullable',
      width: 70,
      render: (value: boolean, _: any, index: number) => (
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
      render: (_: any, __: any, index: number) => (
        <Button size="small" danger type="text" onClick={() => removeColumn(index)}>×</Button>
      ),
    },
  ];

  // Step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="step-content">
            <Form.Item
              name="name"
              label="Metadata Name"
              rules={[{ required: true, message: 'Please enter a name' }]}
            >
              <Input placeholder="e.g., Customer_Data" />
            </Form.Item>

            <Divider>File Settings</Divider>

            {fileType === 'delimited' && (
              <>
                <Form.Item name="delimiter" label="Field Delimiter" initialValue=",">
                  <Select options={DELIMITERS} onChange={handleSettingsChange} />
                </Form.Item>
                <Form.Item name="encoding" label="Encoding" initialValue="UTF-8">
                  <Select options={ENCODINGS} />
                </Form.Item>
                <Form.Item name="hasHeader" label="First Row is Header" valuePropName="checked" initialValue={true}>
                  <Switch onChange={handleSettingsChange} />
                </Form.Item>
                <Form.Item name="textEnclosure" label="Text Enclosure" initialValue='"'>
                  <Input placeholder='"' style={{ width: 100 }} />
                </Form.Item>
                <Form.Item name="skipRows" label="Skip Rows" initialValue={0}>
                  <InputNumber min={0} />
                </Form.Item>
              </>
            )}

            {fileType === 'excel' && (
              <>
                <Form.Item name="sheetName" label="Sheet Name">
                  <Input placeholder="Sheet1" />
                </Form.Item>
                <Form.Item name="hasHeader" label="First Row is Header" valuePropName="checked" initialValue={true}>
                  <Switch />
                </Form.Item>
              </>
            )}

            {fileType === 'json' && (
              <Form.Item name="jsonPath" label="JSON Path (optional)">
                <Input placeholder="$.data[*]" />
              </Form.Item>
            )}

            <Divider>Import from File (Optional)</Divider>
            <Dragger
              accept={fileType === 'delimited' ? '.csv,.txt,.tsv' : fileType === 'excel' ? '.xlsx,.xls' : fileType === 'json' ? '.json' : '.xml'}
              beforeUpload={handleFileUpload}
              showUploadList={false}
              disabled={loading}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Click or drag file to import schema</p>
              <p className="ant-upload-hint">
                Schema will be automatically detected from the file
              </p>
            </Dragger>

            {fileContent && (
              <Alert
                type="success"
                message={`File loaded - ${schema.length} columns detected`}
                style={{ marginTop: 16 }}
              />
            )}
          </div>
        );

      case 1:
        return (
          <div className="step-content schema-step">
            <div className="schema-header">
              <Text strong>Define Schema ({schema.length} columns)</Text>
              <Button size="small" onClick={addColumn}>+ Add Column</Button>
            </div>
            <Table
              dataSource={schema.map((col, i) => ({ ...col, key: i }))}
              columns={schemaColumns}
              size="small"
              pagination={false}
              scroll={{ y: 300 }}
            />

            {previewData.length > 0 && (
              <>
                <Divider>Data Preview</Divider>
                <div className="preview-table">
                  <table>
                    <thead>
                      <tr>
                        {schema.map((col, i) => (
                          <th key={i}>{col.name}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewData.slice(0, 5).map((row, ri) => (
                        <tr key={ri}>
                          {row.map((cell, ci) => (
                            <td key={ci}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        );

      case 2:
        return (
          <div className="step-content summary-step">
            <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
            <Title level={4}>Ready to Create</Title>
            <div className="summary-info">
              <div className="summary-row">
                <Text type="secondary">Name:</Text>
                <Text strong>{form.getFieldValue('name')}</Text>
              </div>
              <div className="summary-row">
                <Text type="secondary">Type:</Text>
                <Text strong>{fileType.toUpperCase()}</Text>
              </div>
              <div className="summary-row">
                <Text type="secondary">Columns:</Text>
                <Text strong>{schema.length}</Text>
              </div>
              {fileType === 'delimited' && (
                <div className="summary-row">
                  <Text type="secondary">Delimiter:</Text>
                  <Text strong>{form.getFieldValue('delimiter') || ','}</Text>
                </div>
              )}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const getTitle = () => {
    switch (fileType) {
      case 'delimited': return 'Create Delimited File Metadata';
      case 'excel': return 'Create Excel File Metadata';
      case 'json': return 'Create JSON File Metadata';
      case 'xml': return 'Create XML File Metadata';
      default: return 'Create File Metadata';
    }
  };

  return (
    <Modal
      title={getTitle()}
      open={visible}
      onCancel={handleCancel}
      width={500}
      className="file-metadata-modal"
      footer={
        <div className="wizard-footer">
          <Button onClick={handleCancel}>Cancel</Button>
          <Space>
            {currentStep > 0 && (
              <Button onClick={() => setCurrentStep(currentStep - 1)}>Previous</Button>
            )}
            {currentStep < 2 ? (
              <Button 
                type="primary" 
                onClick={() => {
                  if (currentStep === 0) {
                    form.validateFields(['name']).then(() => {
                      if (schema.length === 0) {
                        // Add default column if no schema
                        setSchema([{ name: 'Column_1', type: 'String', nullable: true }]);
                      }
                      setCurrentStep(1);
                    });
                  } else {
                    setCurrentStep(currentStep + 1);
                  }
                }}
              >
                Next
              </Button>
            ) : (
              <Button type="primary" onClick={handleSave}>Create Metadata</Button>
            )}
          </Space>
        </div>
      }
    >
      <Steps
        current={currentStep}
        size="small"
        items={[
          { title: 'Settings', icon: <FileTextOutlined /> },
          { title: 'Schema', icon: <TableOutlined /> },
          { title: 'Finish', icon: <CheckCircleOutlined /> },
        ]}
        style={{ marginBottom: 24 }}
      />

      <Form form={form} layout="vertical" size="small">
        {renderStepContent()}
      </Form>
    </Modal>
  );
}
