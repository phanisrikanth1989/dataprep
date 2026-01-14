import React, { useEffect, useState } from 'react';
import { Form, Input, Select, Switch, Button, Card, Collapse, Divider } from 'antd';
import { ComponentMetadata } from '../types/index.ts';
import { componentsAPI } from '../services/api.ts';

interface ConfigPanelProps {
  selectedNodeType?: string;
  selectedNodeConfig?: Record<string, any>;
  onConfigChange: (config: Record<string, any>) => void;
}

const ConfigPanel: React.FC<ConfigPanelProps> = ({
  selectedNodeType,
  selectedNodeConfig = {},
  onConfigChange,
}) => {
  const [form] = Form.useForm();
  const [metadata, setMetadata] = useState<ComponentMetadata | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedNodeType) {
      setMetadata(null);
      return;
    }

    const loadMetadata = async () => {
      setLoading(true);
      try {
        const response = await componentsAPI.get(selectedNodeType);
        setMetadata(response.data);
        form.setFieldsValue(selectedNodeConfig);
      } catch (error) {
        console.error('Error loading component metadata:', error);
      } finally {
        setLoading(false);
      }
    };

    loadMetadata();
  }, [selectedNodeType, form, selectedNodeConfig]);

  const handleSubmit = (values: Record<string, any>) => {
    onConfigChange(values);
  };

  if (!selectedNodeType) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#999' }}>
        Select a component to configure
      </div>
    );
  }

  if (!metadata) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>
    );
  }

  return (
    <div
      style={{
        padding: '16px',
        borderLeft: '1px solid #ddd',
        overflowY: 'auto',
        maxHeight: '100%',
      }}
    >
      <Card
        title={metadata.label}
        size="small"
        style={{ marginBottom: 16 }}
      >
        <p style={{ fontSize: 12, color: '#666', margin: 0 }}>
          {metadata.description}
        </p>
      </Card>

      <Divider style={{ margin: '12px 0' }} />

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={selectedNodeConfig}
        style={{ fontSize: 12 }}
      >
        {metadata.fields.map((field) => (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            required={field.required}
          >
            {field.type === 'text' && (
              <Input
                placeholder={field.placeholder}
                size="small"
              />
            )}
            {field.type === 'number' && (
              <Input
                type="number"
                placeholder={field.placeholder}
                size="small"
              />
            )}
            {field.type === 'boolean' && (
              <Switch />
            )}
            {field.type === 'select' && (
              <Select
                options={field.options?.map((opt) => ({
                  label: opt,
                  value: opt,
                }))}
                size="small"
              />
            )}
            {field.type === 'expression' && (
              <Input.TextArea
                rows={3}
                placeholder={field.placeholder || 'Enter expression...'}
              />
            )}
          </Form.Item>
        ))}

        <Button type="primary" htmlType="submit" block size="small">
          Save Configuration
        </Button>
      </Form>
    </div>
  );
};

export default ConfigPanel;
