import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Modal, Form, Input, message, Drawer } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { jobsAPI } from '../services/api.ts';
import { JobSchema } from '../types/index.ts';

interface JobListProps {
  onJobSelect?: (jobId: string) => void;
  onJobExecute?: (jobId: string) => void;
}

const JobList: React.FC<JobListProps> = ({ onJobSelect, onJobExecute }) => {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [form] = Form.useForm();

  const loadJobs = async () => {
    setLoading(true);
    try {
      const response = await jobsAPI.list();
      setJobs(response.data);
    } catch (error) {
      message.error('Error loading jobs');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleCreateJob = async (values: any) => {
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
      message.success('Job created successfully');
      setCreateModalOpen(false);
      form.resetFields();
      loadJobs();
      if (onJobSelect) {
        onJobSelect(newJob.id);
      }
    } catch (error) {
      message.error('Error creating job');
      console.error(error);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    Modal.confirm({
      title: 'Delete Job',
      content: 'Are you sure you want to delete this job?',
      okText: 'Yes',
      cancelText: 'No',
      onOk: async () => {
        try {
          await jobsAPI.delete(jobId);
          message.success('Job deleted successfully');
          loadJobs();
        } catch (error) {
          message.error('Error deleting job');
          console.error(error);
        }
      },
    });
  };

  const columns = [
    {
      title: 'Job Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Button
          type="link"
          onClick={() => onJobSelect?.(record.id)}
        >
          {text}
        </Button>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Components',
      dataIndex: 'node_count',
      key: 'node_count',
      width: 100,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => date ? new Date(date).toLocaleDateString() : '-',
      width: 120,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="primary"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => onJobExecute?.(record.id)}
          >
            Run
          </Button>
          <Button
            size="small"
            icon={<DeleteOutlined />}
            danger
            onClick={() => handleDeleteJob(record.id)}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <Space style={{ marginBottom: '16px' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalOpen(true)}
        >
          New Job
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={jobs}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="Create New Job"
        open={createModalOpen}
        onOk={() => form.submit()}
        onCancel={() => {
          setCreateModalOpen(false);
          form.resetFields();
        }}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateJob}>
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
    </div>
  );
};

export default JobList;
