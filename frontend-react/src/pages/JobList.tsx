import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Modal, Form, Input, message, Spin, Empty, Popconfirm, Upload } from 'antd';
import { PlusOutlined, EditOutlined, PlayCircleOutlined, DeleteOutlined, LogoutOutlined, ImportOutlined, UploadOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { v4 as uuidv4 } from 'uuid';
import type { JobSchema } from '../types';
import './JobList.css';

export default function JobList() {
  const navigate = useNavigate();
  const { jobs, jobsLoading, loadJobs, createJob, deleteJob, logout, username } = useStore();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const newJob: JobSchema = {
        id: uuidv4(),
        name: values.name,
        description: values.description || '',
        nodes: [],
        edges: [],
        context: {},
        java_config: { enabled: false },
        python_config: { enabled: false },
      };
      await createJob(newJob);
      message.success('Job created successfully');
      setIsModalOpen(false);
      form.resetFields();
      navigate(`/designer/${newJob.id}`);
    } catch (error) {
      console.error('Create job error:', error);
    }
  };

  // Import job from JSON file
  const handleImportJob = (file: File) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = e.target?.result as string;
        const jobData = JSON.parse(content);
        
        // Validate job structure
        if (!jobData.nodes || !Array.isArray(jobData.nodes)) {
          message.error('Invalid job file: missing nodes array');
          return;
        }
        if (!jobData.edges || !Array.isArray(jobData.edges)) {
          message.error('Invalid job file: missing edges array');
          return;
        }

        // Create a new job with imported data but new ID
        const newJob: JobSchema = {
          id: uuidv4(),
          name: jobData.name ? `${jobData.name} (Imported)` : 'Imported Job',
          description: jobData.description || '',
          nodes: jobData.nodes,
          edges: jobData.edges,
          context: jobData.context || {},
          java_config: jobData.java_config || { enabled: false },
          python_config: jobData.python_config || { enabled: false },
        };
        
        await createJob(newJob);
        message.success(`Job "${newJob.name}" imported successfully with ${jobData.nodes.length} nodes`);
        navigate(`/designer/${newJob.id}`);
      } catch (error: any) {
        console.error('Import error:', error);
        message.error(`Failed to import job: ${error.message || 'Invalid JSON'}`);
      }
    };
    reader.onerror = () => {
      message.error('Failed to read file');
    };
    reader.readAsText(file);
    
    // Prevent upload to server
    return false;
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteJob(id);
      message.success('Job deleted');
    } catch (error) {
      message.error('Failed to delete job');
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="job-list-page">
      {/* Header */}
      <header className="page-header">
        <div className="header-left">
          <h1>⚡ RecDataPrep</h1>
          <span className="tagline">Visual ETL Designer</span>
        </div>
        <div className="header-right">
          <span className="username">{username}</span>
          <Button icon={<LogoutOutlined />} onClick={handleLogout}>Logout</Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="page-content">
        <aside className="sidebar">
          <Button type="primary" icon={<PlusOutlined />} size="large" block onClick={() => setIsModalOpen(true)}>
            Create New Job
          </Button>
          <div className="sidebar-info">
            <h3>Getting Started</h3>
            <p>Create a new job to start building your ETL pipeline visually.</p>
          </div>
        </aside>

        <main className="jobs-area">
          <h2>Your Jobs</h2>
          
          {jobsLoading ? (
            <div className="loading-state"><Spin size="large" /></div>
          ) : jobs.length === 0 ? (
            <Empty description="No jobs yet. Create your first job!" />
          ) : (
            <div className="jobs-grid">
              {jobs.map((job) => (
                <Card key={job.id} className="job-card" hoverable>
                  <h3>{job.name}</h3>
                  <p className="job-description">{job.description || 'No description'}</p>
                  <div className="job-stats">
                    <span>📦 {job.node_count} components</span>
                    <span>→ {job.edge_count} connections</span>
                  </div>
                  <div className="job-date">
                    Updated: {new Date(job.updated_at).toLocaleDateString()}
                  </div>
                  <div className="job-actions">
                    <Button icon={<EditOutlined />} onClick={() => navigate(`/designer/${job.id}`)}>
                      Edit
                    </Button>
                    <Button icon={<PlayCircleOutlined />} onClick={() => message.info('Starting execution...')}>
                      Run
                    </Button>
                    <Popconfirm
                      title="Delete this job?"
                      onConfirm={() => handleDelete(job.id)}
                      okText="Yes"
                      cancelText="No"
                    >
                      <Button danger icon={<DeleteOutlined />}>Delete</Button>
                    </Popconfirm>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Create Job Modal */}
      <Modal
        title="Create New Job"
        open={isModalOpen}
        onOk={handleCreate}
        onCancel={() => setIsModalOpen(false)}
        okText="Create"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Job Name" rules={[{ required: true, message: 'Please enter a job name' }]}>
            <Input placeholder="e.g., Customer Data Pipeline" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} placeholder="Describe what this job does..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
