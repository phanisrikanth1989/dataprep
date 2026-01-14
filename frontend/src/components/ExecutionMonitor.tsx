import React, { useEffect, useState } from 'react';
import {
  Card,
  Progress,
  Row,
  Col,
  Statistic,
  Table,
  Spin,
  Button,
  Tag,
  Space,
  Divider,
} from 'antd';
import { PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import { useWebSocket } from '../services/websocket.ts';
import { ExecutionStatus, ExecutionUpdate } from '../types/index.ts';
import { executionAPI } from '../services/api.ts';

interface ExecutionMonitorProps {
  taskId: string;
  onComplete?: (status: ExecutionStatus) => void;
}

const ExecutionMonitor: React.FC<ExecutionMonitorProps> = ({ taskId, onComplete }) => {
  const [execution, setExecution] = useState<ExecutionStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const { connect, disconnect } = useWebSocket();

  useEffect(() => {
    // Fetch initial status
    const loadInitialStatus = async () => {
      try {
        const response = await executionAPI.getStatus(taskId);
        setExecution(response.data);
      } catch (error) {
        console.error('Error loading execution status:', error);
      } finally {
        setLoading(false);
      }
    };

    loadInitialStatus();

    // Connect to WebSocket for updates
    const cleanup = connect(taskId, (update: ExecutionUpdate) => {
      if (update.type === 'update' || update.type === 'status') {
        setExecution(update.data as ExecutionStatus);
      } else if (update.type === 'log') {
        setLogs((prev) => [...prev, update.message || '']);
      } else if (update.type === 'complete') {
        setExecution(update.data as ExecutionStatus);
        if (onComplete) {
          onComplete(update.data as ExecutionStatus);
        }
      } else if (update.type === 'error') {
        setLogs((prev) => [...prev, `ERROR: ${update.message}`]);
      }
    });

    return () => {
      cleanup();
      disconnect(taskId);
    };
  }, [taskId, connect, disconnect, onComplete]);

  const handleStop = async () => {
    try {
      await executionAPI.stop(taskId);
      setLogs((prev) => [...prev, 'Stop requested...']);
    } catch (error) {
      console.error('Error stopping execution:', error);
    }
  };

  if (loading) {
    return <Spin />;
  }

  if (!execution) {
    return <div>Execution not found</div>;
  }

  const statusColor = {
    pending: 'default',
    running: 'processing',
    success: 'success',
    error: 'error',
  };

  const componentStats = Object.entries(execution.stats).map(([key, value]) => ({
    component: key,
    value: value,
  }));

  return (
    <div style={{ padding: '20px' }}>
      <Card
        title="Job Execution"
        extra={
          <Space>
            <Tag color={statusColor[execution.status as keyof typeof statusColor]}>
              {execution.status.toUpperCase()}
            </Tag>
            {execution.status === 'running' && (
              <Button
                danger
                size="small"
                icon={<StopOutlined />}
                onClick={handleStop}
              >
                Stop
              </Button>
            )}
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>
            Progress
          </div>
          <Progress
            percent={execution.progress}
            status={
              execution.status === 'error'
                ? 'exception'
                : execution.status === 'success'
                ? 'success'
                : undefined
            }
          />
        </div>

        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Statistic
              title="Status"
              value={execution.status}
              valueStyle={{ fontSize: 14 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Started"
              value={execution.started_at ? new Date(execution.started_at).toLocaleTimeString() : '-'}
              valueStyle={{ fontSize: 12 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Completed"
              value={execution.completed_at ? new Date(execution.completed_at).toLocaleTimeString() : '-'}
              valueStyle={{ fontSize: 12 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Task ID"
              value={taskId.slice(0, 8)}
              valueStyle={{ fontSize: 12 }}
            />
          </Col>
        </Row>

        {execution.error_message && (
          <Card type="inner" style={{ marginBottom: 16, borderColor: '#ff4d4f' }}>
            <div style={{ color: '#ff4d4f', fontSize: 12 }}>
              <strong>Error:</strong> {execution.error_message}
            </div>
          </Card>
        )}

        <Divider />

        <div style={{ marginBottom: 16, fontSize: 14, fontWeight: 'bold' }}>
          Statistics
        </div>
        {componentStats.length > 0 && (
          <Table
            dataSource={componentStats}
            columns={[
              { title: 'Component', dataIndex: 'component', key: 'component' },
              { title: 'Value', dataIndex: 'value', key: 'value' },
            ]}
            pagination={false}
            size="small"
            style={{ marginBottom: 24 }}
          />
        )}

        <div style={{ marginBottom: 16, fontSize: 14, fontWeight: 'bold' }}>
          Logs
        </div>
        <Card
          type="inner"
          style={{
            maxHeight: '300px',
            overflow: 'auto',
            backgroundColor: '#f5f5f5',
            fontSize: 12,
            fontFamily: 'monospace',
          }}
        >
          {logs.length === 0 ? (
            <div style={{ color: '#999' }}>No logs yet</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} style={{ marginBottom: 4, color: '#333' }}>
                {log}
              </div>
            ))
          )}
        </Card>
      </Card>
    </div>
  );
};

export default ExecutionMonitor;
