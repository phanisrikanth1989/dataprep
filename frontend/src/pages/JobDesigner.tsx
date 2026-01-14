import React, { useState } from 'react';
import { Layout, Menu, Button, Tooltip, Space, message, Modal, Form, Input } from 'antd';
import {
  FileOutlined,
  PlayCircleOutlined,
  SaveOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { Node, Edge } from 'reactflow';
import Canvas from '../components/Canvas.tsx';
import ComponentPalette from '../components/ComponentPalette.tsx';
import ConfigPanel from '../components/ConfigPanel.tsx';
import { JobSchema, JobNode, JobEdge } from '../types/index.ts';
import { jobsAPI } from '../services/api.ts';

const { Content, Sider } = Layout;

interface JobDesignerProps {
  jobId?: string;
  onExecute?: (jobId: string) => void;
}

const JobDesigner: React.FC<JobDesignerProps> = ({ jobId, onExecute }) => {
  const [job, setJob] = useState<JobSchema | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [nameModalOpen, setNameModalOpen] = useState(false);
  const [form] = Form.useForm();

  React.useEffect(() => {
    if (jobId) {
      loadJob(jobId);
    }
  }, [jobId]);

  const loadJob = async (id: string) => {
    try {
      const response = await jobsAPI.get(id);
      const loadedJob = response.data;
      setJob(loadedJob);

      // Convert JobNode to React Flow Node
      const flowNodes: Node[] = loadedJob.nodes.map((node: JobNode) => ({
        id: node.id,
        data: { label: node.type, type: node.type },
        position: { x: node.x, y: node.y },
        type: 'component',
      }));
      setNodes(flowNodes);

      // Convert JobEdge to React Flow Edge
      const flowEdges: Edge[] = loadedJob.edges.map((edge: JobEdge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.name,
      }));
      setEdges(flowEdges);
    } catch (error) {
      message.error('Error loading job');
      console.error(error);
    }
  };

  const handleNodesChange = (updatedNodes: Node[]) => {
    setNodes(updatedNodes);
  };

  const handleEdgesChange = (updatedEdges: Edge[]) => {
    setEdges(updatedEdges);
  };

  const handleConfigChange = (config: Record<string, any>) => {
    if (selectedNode) {
      const updatedNodes = nodes.map((node) =>
        node.id === selectedNode.id
          ? { ...node, data: { ...node.data, config } }
          : node
      );
      setNodes(updatedNodes);
    }
  };

  const handleSaveJob = async () => {
    if (!job) {
      setNameModalOpen(true);
      return;
    }

    setSaveLoading(true);
    try {
      const updatedJob: JobSchema = {
        ...job,
        nodes: nodes.map((node) => ({
          id: node.id,
          type: node.data.type,
          label: node.data.label,
          x: node.position.x,
          y: node.position.y,
          config: node.data.config || {},
        })),
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          edge_type: 'flow',
          name: edge.label as string,
        })),
      };

      if (job.id) {
        await jobsAPI.update(job.id, updatedJob);
        setJob(updatedJob);
        message.success('Job saved successfully');
      }
    } catch (error) {
      message.error('Error saving job');
      console.error(error);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleCreateNewJob = async (values: any) => {
    try {
      const newJob: JobSchema = {
        id: `job_${Date.now()}`,
        name: values.name,
        description: values.description,
        nodes: [],
        edges: [],
        context: {},
        java_config: { enabled: false },
        python_config: { enabled: false },
      };

      await jobsAPI.create(newJob);
      setJob(newJob);
      setNameModalOpen(false);
      form.resetFields();
      message.success('Job created successfully');
    } catch (error) {
      message.error('Error creating job');
      console.error(error);
    }
  };

  const handleExportConfig = async () => {
    if (!job?.id) {
      message.error('Please save the job first');
      return;
    }

    try {
      const response = await jobsAPI.export(job.id);
      const dataStr = JSON.stringify(response.data, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${job.name}.json`;
      link.click();
      message.success('Job exported successfully');
    } catch (error) {
      message.error('Error exporting job');
      console.error(error);
    }
  };

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider width={250} style={{ overflowY: 'auto' }}>
        <ComponentPalette onComponentDragStart={() => {}} />
      </Sider>

      <Layout>
        <Content style={{ display: 'flex', flexDirection: 'column' }}>
          <div
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid #ddd',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: '#fafafa',
            }}
          >
            <div style={{ fontWeight: 'bold' }}>
              {job ? `Job: ${job.name}` : 'Untitled Job'}
            </div>
            <Space>
              <Tooltip title="Save">
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={saveLoading}
                  onClick={handleSaveJob}
                  size="small"
                >
                  Save
                </Button>
              </Tooltip>
              <Tooltip title="Export Config">
                <Button
                  icon={<DownloadOutlined />}
                  onClick={handleExportConfig}
                  size="small"
                >
                  Export
                </Button>
              </Tooltip>
              <Tooltip title="Execute">
                <Button
                  type="primary"
                  danger
                  icon={<PlayCircleOutlined />}
                  onClick={() => {
                    if (job?.id) {
                      onExecute?.(job.id);
                    } else {
                      message.error('Please save the job first');
                    }
                  }}
                  size="small"
                >
                  Run
                </Button>
              </Tooltip>
            </Space>
          </div>

          <div style={{ flex: 1, display: 'flex' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Canvas
                onNodesChange={handleNodesChange}
                onEdgesChange={handleEdgesChange}
                initialNodes={nodes}
                initialEdges={edges}
              />
            </div>
            <Sider width={300} style={{ overflowY: 'auto', borderLeft: '1px solid #ddd' }}>
              <ConfigPanel
                selectedNodeType={selectedNode?.data?.type}
                selectedNodeConfig={selectedNode?.data?.config}
                onConfigChange={handleConfigChange}
              />
            </Sider>
          </div>
        </Content>
      </Layout>

      <Modal
        title="Create New Job"
        open={nameModalOpen}
        onOk={() => form.submit()}
        onCancel={() => {
          setNameModalOpen(false);
          form.resetFields();
        }}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateNewJob}>
          <Form.Item
            name="name"
            label="Job Name"
            rules={[{ required: true, message: 'Please enter job name' }]}
          >
            <Input placeholder="e.g., Sales Pipeline ETL" />
          </Form.Item>
          <Form.Item
            name="description"
            label="Description"
          >
            <Input.TextArea placeholder="Enter job description" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
};

export default JobDesigner;
