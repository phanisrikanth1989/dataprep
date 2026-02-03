import { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Table,
  Space,
  Tabs,
  Tag,
  Popconfirm,
  message,
  Empty,
  Divider,
  Alert,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CopyOutlined,
  SettingOutlined,
  CheckOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import type { ContextGroup, ContextVariable } from '../types/repository';
import './ContextVariablesManager.css';

const { Text, Title } = Typography;

interface Props {
  // Support both prop naming patterns
  open?: boolean;
  visible?: boolean;
  onClose?: () => void;
  onCancel?: () => void;
  contextGroups: ContextGroup[];
  onSave: (groups: ContextGroup[]) => void;
  selectedGroupId?: string;
}

const VARIABLE_TYPES = [
  { value: 'string', label: 'String', icon: '📝' },
  { value: 'integer', label: 'Integer', icon: '🔢' },
  { value: 'boolean', label: 'Boolean', icon: '☑️' },
  { value: 'password', label: 'Password', icon: '🔒' },
  { value: 'date', label: 'Date', icon: '📅' },
  { value: 'file', label: 'File Path', icon: '📁' },
];

// Predefined variable templates
const VARIABLE_TEMPLATES = [
  { name: 'DB_HOST', type: 'string', description: 'Database host address' },
  { name: 'DB_PORT', type: 'integer', description: 'Database port number' },
  { name: 'DB_USER', type: 'string', description: 'Database username' },
  { name: 'DB_PASSWORD', type: 'password', description: 'Database password' },
  { name: 'DB_NAME', type: 'string', description: 'Database name' },
  { name: 'FILE_INPUT_PATH', type: 'file', description: 'Input file path' },
  { name: 'FILE_OUTPUT_PATH', type: 'file', description: 'Output file path' },
  { name: 'API_URL', type: 'string', description: 'API endpoint URL' },
  { name: 'API_KEY', type: 'password', description: 'API authentication key' },
  { name: 'DEBUG_MODE', type: 'boolean', description: 'Enable debug mode' },
];

export default function ContextVariablesManager({
  open,
  visible,
  onClose,
  onCancel,
  contextGroups,
  onSave,
  selectedGroupId,
}: Props) {
  // Support both prop patterns
  const isOpen = open ?? visible ?? false;
  const handleClose = onClose ?? onCancel ?? (() => {});
  
  const [groups, setGroups] = useState<ContextGroup[]>(contextGroups);
  const [activeGroupId, setActiveGroupId] = useState<string | null>(selectedGroupId || null);
  const [editingVariable, setEditingVariable] = useState<ContextVariable | null>(null);
  const [variableModalOpen, setVariableModalOpen] = useState(false);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<ContextGroup | null>(null);

  const [variableForm] = Form.useForm();
  const [groupForm] = Form.useForm();

  useEffect(() => {
    setGroups(contextGroups);
    if (!activeGroupId && contextGroups.length > 0) {
      setActiveGroupId(contextGroups[0].id);
    }
  }, [contextGroups, activeGroupId]);

  // Get active group
  const activeGroup = groups.find((g) => g.id === activeGroupId);

  // Generate unique ID
  const generateId = () => `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  // Create new context group
  const handleCreateGroup = () => {
    setEditingGroup(null);
    groupForm.resetFields();
    setGroupModalOpen(true);
  };

  // Edit context group
  const handleEditGroup = (group: ContextGroup) => {
    setEditingGroup(group);
    groupForm.setFieldsValue({
      name: group.name,
      description: group.description,
      isDefault: group.isDefault,
    });
    setGroupModalOpen(true);
  };

  // Save context group
  const handleSaveGroup = () => {
    groupForm.validateFields().then((values) => {
      if (editingGroup) {
        // Update existing
        setGroups((prev) =>
          prev.map((g) =>
            g.id === editingGroup.id
              ? { ...g, ...values, updatedAt: new Date().toISOString() }
              : values.isDefault
              ? { ...g, isDefault: false }
              : g
          )
        );
      } else {
        // Create new
        const newGroup: ContextGroup = {
          id: generateId(),
          name: values.name,
          description: values.description,
          isDefault: values.isDefault || groups.length === 0,
          variables: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        setGroups((prev) => {
          const updated = values.isDefault
            ? prev.map((g) => ({ ...g, isDefault: false }))
            : prev;
          return [...updated, newGroup];
        });
        setActiveGroupId(newGroup.id);
      }
      setGroupModalOpen(false);
    });
  };

  // Delete context group
  const handleDeleteGroup = (groupId: string) => {
    setGroups((prev) => prev.filter((g) => g.id !== groupId));
    if (activeGroupId === groupId) {
      setActiveGroupId(groups.find((g) => g.id !== groupId)?.id || null);
    }
    message.success('Context group deleted');
  };

  // Duplicate context group
  const handleDuplicateGroup = (group: ContextGroup) => {
    const newGroup: ContextGroup = {
      ...group,
      id: generateId(),
      name: `${group.name}_copy`,
      isDefault: false,
      variables: group.variables.map((v) => ({ ...v, id: generateId() })),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setGroups((prev) => [...prev, newGroup]);
    message.success('Context group duplicated');
  };

  // Create new variable
  const handleCreateVariable = () => {
    setEditingVariable(null);
    variableForm.resetFields();
    variableForm.setFieldsValue({ type: 'string', promptAtRun: false });
    setVariableModalOpen(true);
  };

  // Edit variable
  const handleEditVariable = (variable: ContextVariable) => {
    setEditingVariable(variable);
    variableForm.setFieldsValue(variable);
    setVariableModalOpen(true);
  };

  // Save variable
  const handleSaveVariable = () => {
    variableForm.validateFields().then((values) => {
      if (!activeGroupId) return;

      setGroups((prev) =>
        prev.map((g) => {
          if (g.id !== activeGroupId) return g;

          if (editingVariable) {
            // Update existing variable
            return {
              ...g,
              variables: g.variables.map((v) =>
                v.id === editingVariable.id ? { ...v, ...values } : v
              ),
              updatedAt: new Date().toISOString(),
            };
          } else {
            // Add new variable
            const newVariable: ContextVariable = {
              id: generateId(),
              ...values,
            };
            return {
              ...g,
              variables: [...g.variables, newVariable],
              updatedAt: new Date().toISOString(),
            };
          }
        })
      );

      setVariableModalOpen(false);
    });
  };

  // Delete variable
  const handleDeleteVariable = (variableId: string) => {
    if (!activeGroupId) return;

    setGroups((prev) =>
      prev.map((g) => {
        if (g.id !== activeGroupId) return g;
        return {
          ...g,
          variables: g.variables.filter((v) => v.id !== variableId),
          updatedAt: new Date().toISOString(),
        };
      })
    );
    message.success('Variable deleted');
  };

  // Add from template
  const handleAddFromTemplate = (template: typeof VARIABLE_TEMPLATES[0]) => {
    if (!activeGroupId) return;

    const newVariable: ContextVariable = {
      id: generateId(),
      name: template.name,
      type: template.type as any,
      value: '',
      description: template.description,
      promptAtRun: false,
    };

    setGroups((prev) =>
      prev.map((g) => {
        if (g.id !== activeGroupId) return g;
        return {
          ...g,
          variables: [...g.variables, newVariable],
          updatedAt: new Date().toISOString(),
        };
      })
    );
    message.success(`Added ${template.name}`);
  };

  // Save all changes
  const handleSaveAll = () => {
    onSave(groups);
    handleClose();
    message.success('Context variables saved');
  };

  // Variable columns
  const variableColumns = [
    {
      title: 'Name',
      dataIndex: 'name',
      render: (name: string) => (
        <span className="variable-name">
          <CodeOutlined style={{ color: '#1890ff', marginRight: 6 }} />
          {name}
        </span>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      width: 100,
      render: (type: string) => {
        const typeConfig = VARIABLE_TYPES.find((t) => t.value === type);
        return (
          <Tag>
            {typeConfig?.icon} {typeConfig?.label || type}
          </Tag>
        );
      },
    },
    {
      title: 'Value',
      dataIndex: 'value',
      render: (value: string, record: ContextVariable) => {
        if (record.type === 'password') {
          return <Text type="secondary">••••••••</Text>;
        }
        return <Text ellipsis style={{ maxWidth: 150 }}>{value || '-'}</Text>;
      },
    },
    {
      title: 'Prompt',
      dataIndex: 'promptAtRun',
      width: 70,
      render: (v: boolean) => (v ? <CheckOutlined style={{ color: '#52c41a' }} /> : '-'),
    },
    {
      title: 'Actions',
      width: 100,
      render: (_: any, record: ContextVariable) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditVariable(record)}
          />
          <Popconfirm
            title="Delete this variable?"
            onConfirm={() => handleDeleteVariable(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // Group tabs
  const groupTabs = groups.map((group) => ({
    key: group.id,
    label: (
      <span className="group-tab">
        {group.name}
        {group.isDefault && <Tag color="green" className="default-tag">Default</Tag>}
      </span>
    ),
  }));

  return (
    <Modal
      title={
        <div className="modal-title">
          <SettingOutlined />
          <span>Context Variables Manager</span>
        </div>
      }
      open={isOpen}
      onCancel={handleClose}
      width={900}
      footer={[
        <Button key="cancel" onClick={handleClose}>
          Cancel
        </Button>,
        <Button key="save" type="primary" onClick={handleSaveAll}>
          Save All Changes
        </Button>,
      ]}
      className="context-manager-modal"
    >
      <div className="context-manager">
        {/* Groups Header */}
        <div className="groups-header">
          <Tabs
            activeKey={activeGroupId || undefined}
            onChange={setActiveGroupId}
            items={groupTabs}
            size="small"
            tabBarExtraContent={
              <Space>
                <Button size="small" icon={<PlusOutlined />} onClick={handleCreateGroup}>
                  New Context
                </Button>
              </Space>
            }
          />
        </div>

        {/* Group Actions */}
        {activeGroup && (
          <div className="group-actions">
            <Space>
              <Button size="small" onClick={() => handleEditGroup(activeGroup)}>
                Edit Group
              </Button>
              <Button size="small" onClick={() => handleDuplicateGroup(activeGroup)}>
                Duplicate
              </Button>
              {!activeGroup.isDefault && (
                <Popconfirm
                  title="Delete this context group?"
                  onConfirm={() => handleDeleteGroup(activeGroup.id)}
                >
                  <Button size="small" danger>
                    Delete
                  </Button>
                </Popconfirm>
              )}
            </Space>
            <Text type="secondary" className="group-desc">
              {activeGroup.description || 'No description'}
            </Text>
          </div>
        )}

        <Divider style={{ margin: '12px 0' }} />

        {/* Variables Section */}
        {activeGroup ? (
          <>
            <div className="variables-header">
              <span>Variables ({activeGroup.variables.length})</span>
              <Button icon={<PlusOutlined />} size="small" onClick={handleCreateVariable}>
                Add Variable
              </Button>
            </div>

            {activeGroup.variables.length === 0 ? (
              <Empty
                description="No variables defined"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Space direction="vertical">
                  <Button type="primary" onClick={handleCreateVariable}>
                    Add First Variable
                  </Button>
                  <Text type="secondary">or add from templates:</Text>
                  <div className="template-buttons">
                    {VARIABLE_TEMPLATES.slice(0, 5).map((t) => (
                      <Button
                        key={t.name}
                        size="small"
                        onClick={() => handleAddFromTemplate(t)}
                      >
                        + {t.name}
                      </Button>
                    ))}
                  </div>
                </Space>
              </Empty>
            ) : (
              <Table
                dataSource={activeGroup.variables}
                columns={variableColumns}
                rowKey="id"
                size="small"
                pagination={false}
                scroll={{ y: 300 }}
              />
            )}

            {/* Usage Info */}
            <Alert
              message="Usage in Properties"
              description={
                <span>
                  Reference variables using: <code>{'${context.VARIABLE_NAME}'}</code>
                </span>
              }
              type="info"
              showIcon
              style={{ marginTop: 16 }}
            />
          </>
        ) : (
          <Empty description="Create a context group to get started">
            <Button type="primary" onClick={handleCreateGroup}>
              Create Context Group
            </Button>
          </Empty>
        )}
      </div>

      {/* Variable Edit Modal */}
      <Modal
        title={editingVariable ? 'Edit Variable' : 'Add Variable'}
        open={variableModalOpen}
        onCancel={() => setVariableModalOpen(false)}
        onOk={handleSaveVariable}
        okText="Save"
      >
        <Form form={variableForm} layout="vertical">
          <Form.Item
            name="name"
            label="Variable Name"
            rules={[
              { required: true, message: 'Required' },
              { pattern: /^[A-Z_][A-Z0-9_]*$/i, message: 'Use UPPER_SNAKE_CASE' },
            ]}
          >
            <Input placeholder="e.g., DB_HOST" />
          </Form.Item>

          <Form.Item name="type" label="Type" rules={[{ required: true }]}>
            <Select
              options={VARIABLE_TYPES.map((t) => ({
                value: t.value,
                label: `${t.icon} ${t.label}`,
              }))}
            />
          </Form.Item>

          <Form.Item name="value" label="Value">
            <Input.TextArea rows={2} placeholder="Default value" />
          </Form.Item>

          <Form.Item name="description" label="Description">
            <Input placeholder="Optional description" />
          </Form.Item>

          <Form.Item name="promptAtRun" valuePropName="checked">
            <Switch /> <span style={{ marginLeft: 8 }}>Prompt at runtime</span>
          </Form.Item>
        </Form>
      </Modal>

      {/* Group Edit Modal */}
      <Modal
        title={editingGroup ? 'Edit Context Group' : 'Create Context Group'}
        open={groupModalOpen}
        onCancel={() => setGroupModalOpen(false)}
        onOk={handleSaveGroup}
        okText="Save"
      >
        <Form form={groupForm} layout="vertical">
          <Form.Item
            name="name"
            label="Group Name"
            rules={[{ required: true, message: 'Required' }]}
          >
            <Input placeholder="e.g., DEV, QA, PROD" />
          </Form.Item>

          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="Optional description" />
          </Form.Item>

          <Form.Item name="isDefault" valuePropName="checked">
            <Switch /> <span style={{ marginLeft: 8 }}>Set as default context</span>
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  );
}
