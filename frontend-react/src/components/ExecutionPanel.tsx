import { useState, useEffect, useRef } from 'react';
import {
  Tabs,
  Button,
  Space,
  Select,
  Progress,
  Tag,
  Table,
  Empty,
  Badge,
  Tooltip,
  Typography,
} from 'antd';
import {
  PlayCircleOutlined,
  BugOutlined,
  StopOutlined,
  ClearOutlined,
  DownloadOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  PauseOutlined,
} from '@ant-design/icons';
import type { ExecutionLog, ValidationProblem, ContextGroup } from '../types/repository';
import './ExecutionPanel.css';

const { Text } = Typography;

interface Props {
  isRunning?: boolean;
  isExecuting?: boolean;
  executionStatus?: 'idle' | 'running' | 'success' | 'error' | 'paused';
  progress: number;
  logs: ExecutionLog[];
  problems: ValidationProblem[];
  contextGroups: ContextGroup[];
  selectedContext: string;
  onContextChange: (contextId: string) => void;
  onRun: () => void;
  onDebug: () => void;
  onStop: () => void;
  onClear?: () => void;
  onClearLogs?: () => void;
  onProblemClick?: (problem: ValidationProblem) => void;
}

// Log level colors
const LOG_LEVEL_CONFIG = {
  INFO: { color: '#1890ff', icon: <InfoCircleOutlined /> },
  WARN: { color: '#faad14', icon: <WarningOutlined /> },
  ERROR: { color: '#ff4d4f', icon: <CloseCircleOutlined /> },
  DEBUG: { color: '#8c8c8c', icon: <BugOutlined /> },
};

// Problem severity colors
const SEVERITY_CONFIG = {
  error: { color: 'red', icon: <CloseCircleOutlined /> },
  warning: { color: 'orange', icon: <WarningOutlined /> },
  info: { color: 'blue', icon: <InfoCircleOutlined /> },
};

export default function ExecutionPanel({
  isRunning,
  isExecuting,
  executionStatus = 'idle',
  progress,
  logs,
  problems,
  contextGroups,
  selectedContext,
  onContextChange,
  onRun,
  onDebug,
  onStop,
  onClear,
  onClearLogs,
  onProblemClick,
}: Props) {
  const [activeTab, setActiveTab] = useState('run');
  const [autoScroll, setAutoScroll] = useState(true);
  const [logFilter, setLogFilter] = useState<string>('all');
  const consoleRef = useRef<HTMLDivElement>(null);
  
  // Use either isRunning or isExecuting
  const running = isRunning ?? isExecuting ?? false;
  // Use either onClear or onClearLogs
  const handleClear = onClear ?? onClearLogs ?? (() => {});

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Filter logs by level
  const filteredLogs = logs.filter(
    (log) => logFilter === 'all' || log.level === logFilter
  );

  // Count problems by severity
  const errorCount = problems.filter((p) => p.severity === 'error').length;
  const warningCount = problems.filter((p) => p.severity === 'warning').length;

  // Get status indicator
  const getStatusIndicator = () => {
    switch (executionStatus) {
      case 'running':
        return (
          <Tag icon={<LoadingOutlined spin />} color="processing">
            Running
          </Tag>
        );
      case 'success':
        return (
          <Tag icon={<CheckCircleOutlined />} color="success">
            Success
          </Tag>
        );
      case 'error':
        return (
          <Tag icon={<CloseCircleOutlined />} color="error">
            Failed
          </Tag>
        );
      case 'paused':
        return (
          <Tag icon={<PauseOutlined />} color="warning">
            Paused
          </Tag>
        );
      default:
        return (
          <Tag color="default">
            Ready
          </Tag>
        );
    }
  };

  // Format timestamp
  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      const seconds = date.getSeconds().toString().padStart(2, '0');
      const ms = date.getMilliseconds().toString().padStart(3, '0');
      return `${hours}:${minutes}:${seconds}.${ms}`;
    } catch {
      return timestamp;
    }
  };

  // Export logs
  const exportLogs = () => {
    const content = logs
      .map((log) => `[${log.timestamp}] [${log.level}] ${log.component ? `[${log.component}]` : ''} ${log.message}`)
      .join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `execution_log_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Run tab content
  const renderRunTab = () => (
    <div className="run-tab">
      <div className="run-toolbar">
        <Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={onRun}
            disabled={running}
            className="run-btn"
          >
            Run
          </Button>
          <Button
            icon={<BugOutlined />}
            onClick={onDebug}
            disabled={running}
          >
            Debug
          </Button>
          <Button
            icon={<StopOutlined />}
            onClick={onStop}
            disabled={!running}
            danger
          >
            Stop
          </Button>
        </Space>

        <Space>
          <span className="context-label">Context:</span>
          <Select
            value={selectedContext}
            onChange={onContextChange}
            style={{ width: 150 }}
            size="small"
            disabled={running}
          >
            {contextGroups.map((ctx) => (
              <Select.Option key={ctx.id} value={ctx.id}>
                {ctx.name}
                {ctx.isDefault && <Tag color="green" style={{ marginLeft: 6, fontSize: 9 }}>Default</Tag>}
              </Select.Option>
            ))}
          </Select>
        </Space>

        <Space>
          {getStatusIndicator()}
          {running && (
            <Progress
              percent={progress}
              size="small"
              style={{ width: 100 }}
              status={executionStatus === 'error' ? 'exception' : 'active'}
            />
          )}
        </Space>
      </div>

      {/* Execution stats */}
      {(executionStatus === 'success' || executionStatus === 'error') && (
        <div className="execution-stats">
          <div className="stat-item">
            <span className="stat-label">Duration:</span>
            <span className="stat-value">2.3s</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Rows Processed:</span>
            <span className="stat-value">5,234</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Components:</span>
            <span className="stat-value">4 / 4</span>
          </div>
        </div>
      )}
    </div>
  );

  // Console tab content
  const renderConsoleTab = () => (
    <div className="console-tab">
      <div className="console-toolbar">
        <Space>
          <Select
            value={logFilter}
            onChange={setLogFilter}
            size="small"
            style={{ width: 100 }}
          >
            <Select.Option value="all">All</Select.Option>
            <Select.Option value="INFO">Info</Select.Option>
            <Select.Option value="WARN">Warn</Select.Option>
            <Select.Option value="ERROR">Error</Select.Option>
            <Select.Option value="DEBUG">Debug</Select.Option>
          </Select>
          <span className="log-count">{filteredLogs.length} entries</span>
        </Space>

        <Space>
          <Tooltip title="Auto-scroll">
            <Button
              size="small"
              type={autoScroll ? 'primary' : 'default'}
              onClick={() => setAutoScroll(!autoScroll)}
            >
              ↓
            </Button>
          </Tooltip>
          <Tooltip title="Export logs">
            <Button size="small" icon={<DownloadOutlined />} onClick={exportLogs} />
          </Tooltip>
          <Tooltip title="Clear console">
            <Button size="small" icon={<ClearOutlined />} onClick={handleClear} />
          </Tooltip>
        </Space>
      </div>

      <div className="console-content" ref={consoleRef}>
        {filteredLogs.length === 0 ? (
          <div className="console-empty">
            <Text type="secondary">No log entries</Text>
          </div>
        ) : (
          filteredLogs.map((log) => {
            const levelKey = log.level.toUpperCase() as keyof typeof LOG_LEVEL_CONFIG;
            const levelConfig = LOG_LEVEL_CONFIG[levelKey] || LOG_LEVEL_CONFIG.INFO;
            return (
              <div key={log.id} className={`log-entry log-${log.level.toLowerCase()}`}>
                <span className="log-time">{formatTime(log.timestamp)}</span>
                <span className="log-level" style={{ color: levelConfig.color }}>
                  {levelConfig.icon} {log.level.toUpperCase()}
                </span>
                {log.component && (
                  <span className="log-component">[{log.component}]</span>
                )}
                <span className="log-message">{log.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  // Problems tab content
  const renderProblemsTab = () => (
    <div className="problems-tab">
      {problems.length === 0 ? (
        <Empty
          description="No problems detected"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          className="problems-empty"
        >
          <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
        </Empty>
      ) : (
        <Table
          dataSource={problems}
          columns={[
            {
              title: '',
              dataIndex: 'severity',
              width: 40,
              render: (severity: string) => {
                const config = SEVERITY_CONFIG[severity as keyof typeof SEVERITY_CONFIG];
                return <span style={{ color: config?.color }}>{config?.icon}</span>;
              },
            },
            {
              title: 'Component',
              dataIndex: 'component',
              width: 120,
              render: (comp: string) => comp || '-',
            },
            {
              title: 'Message',
              dataIndex: 'message',
            },
            {
              title: 'Suggestion',
              dataIndex: 'suggestion',
              width: 200,
              render: (sug: string) => (
                <Text type="secondary" ellipsis>
                  {sug || '-'}
                </Text>
              ),
            },
          ]}
          rowKey="id"
          size="small"
          pagination={false}
          onRow={(record) => ({
            onClick: () => onProblemClick?.(record),
            style: { cursor: onProblemClick ? 'pointer' : 'default' },
          })}
        />
      )}
    </div>
  );

  // Tab items
  const tabItems = [
    {
      key: 'run',
      label: (
        <span>
          <PlayCircleOutlined /> Run
        </span>
      ),
      children: renderRunTab(),
    },
    {
      key: 'console',
      label: (
        <span>
          <InfoCircleOutlined /> Console
          {logs.length > 0 && (
            <Badge count={logs.length} size="small" offset={[5, -3]} />
          )}
        </span>
      ),
      children: renderConsoleTab(),
    },
    {
      key: 'problems',
      label: (
        <span>
          <WarningOutlined /> Problems
          {errorCount > 0 && (
            <Badge count={errorCount} size="small" offset={[5, -3]} color="red" />
          )}
          {errorCount === 0 && warningCount > 0 && (
            <Badge count={warningCount} size="small" offset={[5, -3]} color="orange" />
          )}
        </span>
      ),
      children: renderProblemsTab(),
    },
  ];

  return (
    <div className="execution-panel">
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        size="small"
        className="execution-tabs"
      />
    </div>
  );
}
