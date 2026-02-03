import { useState, useEffect } from 'react';
import { Button, Input, Select, Switch, Table, Space, Popconfirm, message } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { SchemaColumn } from '../types';
import './SchemaEditor.css';

const DATA_TYPES = [
  { value: 'id_String', label: 'String' },
  { value: 'id_Integer', label: 'Integer' },
  { value: 'id_Long', label: 'Long' },
  { value: 'id_Float', label: 'Float' },
  { value: 'id_Double', label: 'Double' },
  { value: 'id_Boolean', label: 'Boolean' },
  { value: 'id_Date', label: 'Date' },
  { value: 'id_BigDecimal', label: 'Decimal' },
];

interface Props {
  schema: SchemaColumn[];
  onSave: (schema: SchemaColumn[]) => void;
}

export default function SchemaEditor({ schema, onSave }: Props) {
  const [columns, setColumns] = useState<SchemaColumn[]>([]);

  useEffect(() => {
    setColumns(schema.length > 0 ? [...schema] : []);
  }, [schema]);

  const addColumn = () => {
    setColumns([...columns, { name: '', type: 'id_String', nullable: true }]);
  };

  const updateColumn = (index: number, field: keyof SchemaColumn, value: any) => {
    const updated = [...columns];
    updated[index] = { ...updated[index], [field]: value };
    setColumns(updated);
  };

  const deleteColumn = (index: number) => {
    setColumns(columns.filter((_, i) => i !== index));
  };

  const clearAll = () => {
    setColumns([]);
    message.info('Schema cleared');
  };

  const handleSave = () => {
    const validColumns = columns.filter((c) => c.name.trim() !== '');
    if (validColumns.length === 0) {
      message.warning('Add at least one column');
      return;
    }
    onSave(validColumns);
  };

  const tableColumns = [
    {
      title: '#',
      width: 50,
      render: (_: any, __: any, index: number) => index + 1,
    },
    {
      title: 'Column Name',
      dataIndex: 'name',
      render: (value: string, _: any, index: number) => (
        <Input
          value={value}
          onChange={(e) => updateColumn(index, 'name', e.target.value)}
          placeholder="e.g., customer_id"
          size="small"
        />
      ),
    },
    {
      title: 'Data Type',
      dataIndex: 'type',
      width: 140,
      render: (value: string, _: any, index: number) => (
        <Select
          value={value}
          onChange={(v) => updateColumn(index, 'type', v)}
          options={DATA_TYPES}
          size="small"
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: 'Nullable',
      dataIndex: 'nullable',
      width: 80,
      render: (value: boolean, _: any, index: number) => (
        <Switch
          checked={value}
          onChange={(v) => updateColumn(index, 'nullable', v)}
          size="small"
        />
      ),
    },
    {
      title: '',
      width: 50,
      render: (_: any, __: any, index: number) => (
        <Button
          type="text"
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={() => deleteColumn(index)}
        />
      ),
    },
  ];

  return (
    <div className="schema-editor">
      <div className="schema-header">
        <h4>Output Schema</h4>
        <Space>
          <Button size="small" icon={<PlusOutlined />} onClick={addColumn}>
            Add Column
          </Button>
          <Popconfirm title="Clear all columns?" onConfirm={clearAll} disabled={columns.length === 0}>
            <Button size="small" danger disabled={columns.length === 0}>
              Clear All
            </Button>
          </Popconfirm>
        </Space>
      </div>

      {columns.length === 0 ? (
        <div className="empty-schema">
          <p>No columns defined yet.</p>
          <Button type="primary" icon={<PlusOutlined />} onClick={addColumn}>
            Add First Column
          </Button>
        </div>
      ) : (
        <Table
          dataSource={columns.map((c, i) => ({ ...c, key: i }))}
          columns={tableColumns}
          pagination={false}
          size="small"
          className="schema-table"
        />
      )}

      <div className="schema-actions">
        <Button type="primary" onClick={handleSave} disabled={columns.length === 0}>
          Save Schema
        </Button>
      </div>
    </div>
  );
}
