import { useEffect, useState } from 'react';
import { Form, Input, InputNumber, Switch, Select, Button, Divider, Space } from 'antd';
import { FolderOpenOutlined } from '@ant-design/icons';
import type { Node } from '@xyflow/react';
import type { ComponentMetadata } from '../types';
import FileBrowser from './FileBrowser';
import './ConfigPanel.css';

interface Props {
  node: Node;
  component: ComponentMetadata;
  onSave: (config: Record<string, any>) => void;
  onCancel: () => void;
}

// Fields that should use the file browser
const FILE_PATH_FIELDS = ['filepath', 'filename', 'file_path', 'input_file', 'output_file', 'path'];

export default function ConfigPanel({ node, component, onSave, onCancel }: Props) {
  const [form] = Form.useForm();
  const nodeData = node.data as Record<string, any>;
  const [fileBrowserOpen, setFileBrowserOpen] = useState(false);
  const [activeFileField, setActiveFileField] = useState<string | null>(null);
  const [fileBrowserMode, setFileBrowserMode] = useState<'file' | 'directory' | 'save'>('file');

  useEffect(() => {
    // Set initial values from node config
    const initialValues: Record<string, any> = {
      _nodeName: nodeData.name || '',
    };
    
    component.fields.forEach((field) => {
      initialValues[field.name] = nodeData.config?.[field.name] ?? field.default ?? '';
    });
    
    form.setFieldsValue(initialValues);
  }, [node, component, form]);

  const handleSubmit = (values: Record<string, any>) => {
    onSave(values);
  };

  // Check if this is an input or output component
  const isInputComponent = component.type.toLowerCase().includes('input');
  const isOutputComponent = component.type.toLowerCase().includes('output');

  // Open file browser for a field
  const openFileBrowser = (fieldName: string) => {
    setActiveFileField(fieldName);
    // Set mode based on component type
    if (isOutputComponent) {
      setFileBrowserMode('save');
    } else {
      setFileBrowserMode('file');
    }
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

  // Get file filter based on component type
  const getFileFilter = () => {
    const componentType = component.type.toLowerCase();
    if (componentType.includes('delimited') || componentType.includes('csv')) {
      return '.csv,.txt,.tsv,.dat';
    }
    if (componentType.includes('excel')) {
      return '.xlsx,.xls';
    }
    if (componentType.includes('json')) {
      return '.json';
    }
    if (componentType.includes('xml')) {
      return '.xml';
    }
    return undefined;
  };

  // Custom component for file path fields that works with Form.Item
  const FilePathInput = ({ value, onChange, placeholder, fieldName }: {
    value?: string;
    onChange?: (value: string) => void;
    placeholder?: string;
    fieldName: string;
  }) => {
    return (
      <Space.Compact style={{ width: '100%' }}>
        <Input 
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder} 
          style={{ width: 'calc(100% - 32px)' }}
        />
        <Button 
          icon={<FolderOpenOutlined />} 
          onClick={() => openFileBrowser(fieldName)}
          title="Browse files"
        />
      </Space.Compact>
    );
  };

  // Render field input with file browser button if applicable
  const renderFieldInput = (field: any) => {
    const isFilePath = FILE_PATH_FIELDS.includes(field.name.toLowerCase());
    
    if (field.type === 'text' && isFilePath) {
      return (
        <FilePathInput 
          placeholder={field.placeholder}
          fieldName={field.name}
        />
      );
    }
    
    if (field.type === 'text') {
      return <Input placeholder={field.placeholder} />;
    }
    
    if (field.type === 'number') {
      return <InputNumber style={{ width: '100%' }} placeholder={field.placeholder} />;
    }
    
    if (field.type === 'boolean') {
      return <Switch />;
    }
    
    if (field.type === 'select') {
      return (
        <Select placeholder={`Select ${field.label}`}>
          {field.options?.map((opt: string) => (
            <Select.Option key={opt} value={opt}>{opt}</Select.Option>
          ))}
        </Select>
      );
    }
    
    if (field.type === 'expression') {
      return <Input.TextArea rows={3} placeholder={field.placeholder} />;
    }
    
    return <Input placeholder={field.placeholder} />;
  };

  return (
    <div className="config-panel">
      <Form form={form} layout="vertical" onFinish={handleSubmit} size="small">
        {/* Custom Name Field */}
        <Form.Item
          name="_nodeName"
          label="Component Name"
          tooltip="Custom name for this component (for development)"
        >
          <Input placeholder="e.g., Read Customer Data" />
        </Form.Item>

        <Divider />

        {/* Dynamic Fields */}
        {component.fields.map((field) => (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={field.required ? [{ required: true, message: `${field.label} is required` }] : []}
            tooltip={field.description}
          >
            {renderFieldInput(field)}
          </Form.Item>
        ))}

        <div className="form-actions">
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="primary" htmlType="submit">Save Configuration</Button>
        </div>
      </Form>

      {/* File Browser Modal */}
      <FileBrowser
        open={fileBrowserOpen}
        onClose={() => setFileBrowserOpen(false)}
        onSelect={handleFileSelect}
        mode={fileBrowserMode}
        title={isOutputComponent ? 'Select Output File' : 'Select Input File'}
        fileFilter={getFileFilter()}
        defaultPath="C:\\"
      />
    </div>
  );
}
