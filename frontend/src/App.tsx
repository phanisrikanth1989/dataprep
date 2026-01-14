import React, { useState } from 'react';
import { Layout, Tabs, Button, Space, message } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import JobList from './components/JobList.tsx';
import JobDesigner from './pages/JobDesigner.tsx';
import ExecutionMonitor from './components/ExecutionMonitor.tsx';
import { ExecutionStatus } from './types';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<'list' | 'designer' | 'execution'>('list');
  const [selectedJobId, setSelectedJobId] = useState<string | undefined>(undefined);
  const [executionTaskId, setExecutionTaskId] = useState<string | undefined>(undefined);

  const handleJobSelect = (jobId: string) => {
    setSelectedJobId(jobId);
    setCurrentPage('designer');
  };

  const handleJobExecute = async (jobId: string) => {
    try {
      const { executionAPI } = await import('./services/api');
      const response = await executionAPI.start(jobId);
      setExecutionTaskId(response.data.task_id);
      setCurrentPage('execution');
      message.success('Job execution started');
    } catch (error) {
      message.error('Error starting job execution');
      console.error(error);
    }
  };

  const handleExecutionComplete = (status: ExecutionStatus) => {
    if (status.status === 'success') {
      message.success('Job completed successfully');
    } else if (status.status === 'error') {
      message.error(`Job failed: ${status.error_message}`);
    }
  };

  const handleBack = () => {
    setCurrentPage(currentPage === 'designer' ? 'list' : 'list');
    setSelectedJobId(undefined);
  };

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Layout.Header
        style={{
          background: '#001529',
          color: 'white',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ fontSize: 20, fontWeight: 'bold' }}>
          RecDataPrep - ETL Visual Designer
        </div>
        {currentPage !== 'list' && (
          <Button
            type="primary"
            icon={<ArrowLeftOutlined />}
            onClick={handleBack}
          >
            Back to Jobs
          </Button>
        )}
      </Layout.Header>

      <Layout.Content style={{ flex: 1, overflow: 'hidden' }}>
        {currentPage === 'list' && (
          <JobList
            onJobSelect={handleJobSelect}
            onJobExecute={handleJobExecute}
          />
        )}

        {currentPage === 'designer' && selectedJobId && (
          <JobDesigner
            jobId={selectedJobId}
            onExecute={handleJobExecute}
          />
        )}

        {currentPage === 'execution' && executionTaskId && (
          <ExecutionMonitor
            taskId={executionTaskId}
            onComplete={handleExecutionComplete}
          />
        )}
      </Layout.Content>
    </Layout>
  );
};

export default App;
