import { useState, useEffect, useCallback } from 'react';
import { Button, Input, Select, Table, Space, Tooltip, Modal, Popconfirm, Tag, Empty } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  ArrowRightOutlined,
  EditOutlined,
  CopyOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { SchemaColumn } from '../types';
import './MapEditor.css';

interface ColumnMapping {
  id: string;
  sourceColumn: string;
  targetColumn: string;
  expression: string;
  dataType: string;
}

interface Props {
  inputSchema: SchemaColumn[];
  outputMappings: ColumnMapping[];
  onSave: (mappings: ColumnMapping[]) => void;
}

const DATA_TYPES = ['string', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'binary'];

const EXPRESSION_TEMPLATES = [
  { label: 'Direct Copy', value: '', desc: 'Copy value as-is' },
  { label: 'Upper Case', value: 'upper({col})', desc: 'Convert to uppercase' },
  { label: 'Lower Case', value: 'lower({col})', desc: 'Convert to lowercase' },
  { label: 'Trim', value: 'trim({col})', desc: 'Remove leading/trailing spaces' },
  { label: 'Substring', value: 'substring({col}, 0, 10)', desc: 'Extract substring' },
  { label: 'Replace', value: 'replace({col}, "old", "new")', desc: 'Replace text' },
  { label: 'Concatenate', value: 'concat({col}, " ", other_col)', desc: 'Join strings' },
  { label: 'To Integer', value: 'parseInt({col})', desc: 'Convert to integer' },
  { label: 'To Decimal', value: 'parseFloat({col})', desc: 'Convert to decimal' },
  { label: 'To Date', value: 'parseDate({col}, "yyyy-MM-dd")', desc: 'Parse date string' },
  { label: 'Format Date', value: 'formatDate({col}, "MM/dd/yyyy")', desc: 'Format date' },
  { label: 'If Null', value: 'ifNull({col}, "default")', desc: 'Replace null values' },
  { label: 'Conditional', value: 'if({col} > 0, "positive", "negative")', desc: 'If-then-else' },
];

export default function MapEditor({ inputSchema, outputMappings, onSave }: Props) {
  const [mappings, setMappings] = useState<ColumnMapping[]>(outputMappings || []);
  const [expressionModalOpen, setExpressionModalOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<ColumnMapping | null>(null);
  const [draggedColumn, setDraggedColumn] = useState<SchemaColumn | null>(null);

  useEffect(() => {
    setMappings(outputMappings || []);
  }, [outputMappings]);

  // Generate unique ID
  const generateId = () => `map_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  // Add new mapping
  const addMapping = useCallback((sourceCol?: SchemaColumn) => {
    const newMapping: ColumnMapping = {
      id: generateId(),
      sourceColumn: sourceCol?.name || '',
      targetColumn: sourceCol?.name || '',
      expression: '',
      dataType: sourceCol?.type || 'string',
    };
    setMappings((prev) => [...prev, newMapping]);
  }, []);

  // Copy all input columns to output
  const copyAllColumns = useCallback(() => {
    const newMappings: ColumnMapping[] = inputSchema.map((col) => ({
      id: generateId(),
      sourceColumn: col.name,
      targetColumn: col.name,
      expression: '',
      dataType: col.type,
    }));
    setMappings(newMappings);
  }, [inputSchema]);

  // Update mapping
  const updateMapping = useCallback((id: string, field: keyof ColumnMapping, value: string) => {
    setMappings((prev) =>
      prev.map((m) => (m.id === id ? { ...m, [field]: value } : m))
    );
  }, []);

  // Delete mapping
  const deleteMapping = useCallback((id: string) => {
    setMappings((prev) => prev.filter((m) => m.id !== id));
  }, []);

  // Move mapping up/down
  const moveMapping = useCallback((id: string, direction: 'up' | 'down') => {
    setMappings((prev) => {
      const index = prev.findIndex((m) => m.id === id);
      if (index < 0) return prev;
      if (direction === 'up' && index === 0) return prev;
      if (direction === 'down' && index === prev.length - 1) return prev;

      const newMappings = [...prev];
      const swapIndex = direction === 'up' ? index - 1 : index + 1;
      [newMappings[index], newMappings[swapIndex]] = [newMappings[swapIndex], newMappings[index]];
      return newMappings;
    });
  }, []);

  // Handle drag start from input columns
  const handleDragStart = (col: SchemaColumn) => {
    setDraggedColumn(col);
  };

  // Handle drop on output area
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (draggedColumn) {
      addMapping(draggedColumn);
      setDraggedColumn(null);
    }
  };

  // Open expression editor
  const openExpressionEditor = (mapping: ColumnMapping) => {
    setEditingMapping(mapping);
    setExpressionModalOpen(true);
  };

  // Apply expression template
  const applyExpressionTemplate = (template: string) => {
    if (editingMapping) {
      const expr = template.replace(/{col}/g, editingMapping.sourceColumn);
      updateMapping(editingMapping.id, 'expression', expr);
      setEditingMapping({ ...editingMapping, expression: expr });
    }
  };

  // Save mappings
  const handleSave = () => {
    onSave(mappings);
  };

  // Input columns table
  const inputColumns = [
    {
      title: 'Input Columns',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: SchemaColumn) => (
        <div
          className="input-column-item"
          draggable
          onDragStart={() => handleDragStart(record)}
        >
          <span className="column-name">{name}</span>
          <Tag color="blue" className="column-type">{record.type}</Tag>
        </div>
      ),
    },
  ];

  // Output mappings table columns
  const outputColumns = [
    {
      title: 'Source',
      dataIndex: 'sourceColumn',
      key: 'sourceColumn',
      width: 150,
      render: (value: string, record: ColumnMapping) => (
        <Select
          value={value}
          onChange={(v) => updateMapping(record.id, 'sourceColumn', v)}
          style={{ width: '100%' }}
          placeholder="Select column"
          allowClear
          showSearch
        >
          {inputSchema.map((col) => (
            <Select.Option key={col.name} value={col.name}>
              {col.name}
            </Select.Option>
          ))}
        </Select>
      ),
    },
    {
      title: '',
      key: 'arrow',
      width: 40,
      render: () => <ArrowRightOutlined style={{ color: '#1890ff' }} />,
    },
    {
      title: 'Target',
      dataIndex: 'targetColumn',
      key: 'targetColumn',
      width: 150,
      render: (value: string, record: ColumnMapping) => (
        <Input
          value={value}
          onChange={(e) => updateMapping(record.id, 'targetColumn', e.target.value)}
          placeholder="Output column name"
        />
      ),
    },
    {
      title: 'Type',
      dataIndex: 'dataType',
      key: 'dataType',
      width: 100,
      render: (value: string, record: ColumnMapping) => (
        <Select
          value={value}
          onChange={(v) => updateMapping(record.id, 'dataType', v)}
          style={{ width: '100%' }}
        >
          {DATA_TYPES.map((t) => (
            <Select.Option key={t} value={t}>{t}</Select.Option>
          ))}
        </Select>
      ),
    },
    {
      title: 'Expression',
      dataIndex: 'expression',
      key: 'expression',
      render: (value: string, record: ColumnMapping) => (
        <div className="expression-cell">
          <Input
            value={value}
            onChange={(e) => updateMapping(record.id, 'expression', e.target.value)}
            placeholder="(optional) transformation"
            suffix={
              <Tooltip title="Expression Editor">
                <ThunderboltOutlined
                  className="expr-editor-btn"
                  onClick={() => openExpressionEditor(record)}
                />
              </Tooltip>
            }
          />
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 80,
      render: (_: any, record: ColumnMapping) => (
        <Space size="small">
          <Popconfirm
            title="Delete this mapping?"
            onConfirm={() => deleteMapping(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="map-editor">
      {/* Header */}
      <div className="map-editor-header">
        <h3>🔀 Column Mapper</h3>
        <Space>
          <Button
            icon={<CopyOutlined />}
            onClick={copyAllColumns}
            disabled={inputSchema.length === 0}
          >
            Copy All
          </Button>
          <Button type="primary" onClick={handleSave}>
            Save Mappings
          </Button>
        </Space>
      </div>

      {/* Main content - split view */}
      <div className="map-editor-content">
        {/* Left side - Input Schema */}
        <div className="input-schema-panel">
          <div className="panel-header">
            <span>📥 Input Schema</span>
            <Tag>{inputSchema.length} columns</Tag>
          </div>
          {inputSchema.length === 0 ? (
            <Empty
              description="No input schema available"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ) : (
            <Table
              dataSource={inputSchema}
              columns={inputColumns}
              rowKey="name"
              size="small"
              pagination={false}
              className="input-columns-table"
            />
          )}
          <div className="drag-hint">
            💡 Drag columns to the output panel
          </div>
        </div>

        {/* Right side - Output Mappings */}
        <div
          className="output-mappings-panel"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <div className="panel-header">
            <span>📤 Output Mappings</span>
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              size="small"
              onClick={() => addMapping()}
            >
              Add Column
            </Button>
          </div>
          
          {mappings.length === 0 ? (
            <div className="empty-mappings">
              <Empty
                description="No mappings defined"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" onClick={() => addMapping()}>
                  Add First Mapping
                </Button>
              </Empty>
            </div>
          ) : (
            <Table
              dataSource={mappings}
              columns={outputColumns}
              rowKey="id"
              size="small"
              pagination={false}
              className="output-mappings-table"
            />
          )}
        </div>
      </div>

      {/* Expression Editor Modal */}
      <Modal
        title="Expression Editor"
        open={expressionModalOpen}
        onCancel={() => setExpressionModalOpen(false)}
        onOk={() => setExpressionModalOpen(false)}
        width={700}
        className="expression-modal"
      >
        {editingMapping && (
          <div className="expression-editor">
            <div className="expr-info">
              <p>
                <strong>Source Column:</strong> {editingMapping.sourceColumn || '(none)'}
              </p>
              <p>
                <strong>Target Column:</strong> {editingMapping.targetColumn}
              </p>
            </div>

            <div className="expr-templates">
              <h4>Quick Templates</h4>
              <div className="template-grid">
                {EXPRESSION_TEMPLATES.map((tmpl) => (
                  <Tooltip key={tmpl.label} title={tmpl.desc}>
                    <Button
                      size="small"
                      onClick={() => applyExpressionTemplate(tmpl.value)}
                    >
                      {tmpl.label}
                    </Button>
                  </Tooltip>
                ))}
              </div>
            </div>

            <div className="expr-input">
              <h4>Expression</h4>
              <Input.TextArea
                value={editingMapping.expression}
                onChange={(e) => {
                  updateMapping(editingMapping.id, 'expression', e.target.value);
                  setEditingMapping({ ...editingMapping, expression: e.target.value });
                }}
                rows={4}
                placeholder="Enter transformation expression (leave empty for direct copy)"
              />
            </div>

            <div className="expr-help">
              <h4>Available Functions</h4>
              <ul>
                <li><code>upper(col)</code> - Convert to uppercase</li>
                <li><code>lower(col)</code> - Convert to lowercase</li>
                <li><code>trim(col)</code> - Remove whitespace</li>
                <li><code>substring(col, start, length)</code> - Extract substring</li>
                <li><code>replace(col, old, new)</code> - Replace text</li>
                <li><code>concat(col1, col2, ...)</code> - Concatenate strings</li>
                <li><code>parseInt(col)</code> / <code>parseFloat(col)</code> - Convert to number</li>
                <li><code>parseDate(col, format)</code> - Parse date string</li>
                <li><code>formatDate(col, format)</code> - Format date</li>
                <li><code>ifNull(col, default)</code> - Replace null values</li>
                <li><code>if(condition, then, else)</code> - Conditional expression</li>
              </ul>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
