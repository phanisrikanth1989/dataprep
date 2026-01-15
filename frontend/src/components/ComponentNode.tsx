import React from 'react';
import { Handle, Position } from 'reactflow';
import { Card } from 'antd';
import {
  SwapOutlined,
  FilterOutlined,
  FileOutlined,
  DownloadOutlined,
  BarChartOutlined,
  SortAscendingOutlined,
} from '@ant-design/icons';

interface ComponentNodeProps {
  data: {
    label: string;
    type: string;
  };
  selected?: boolean;
}

const iconMap: Record<string, React.ReactNode> = {
  Map: <SwapOutlined />,
  Filter: <FilterOutlined />,
  FileInput: <FileOutlined />,
  FileOutput: <DownloadOutlined />,
  Aggregate: <BarChartOutlined />,
  Sort: <SortAscendingOutlined />,
};

const ComponentNode: React.FC<ComponentNodeProps> = ({ data, selected }) => {
  return (
    <Card
      size="small"
      style={{
        width: 120,
        padding: 0,
        border: selected ? '2px solid #1890ff' : '1px solid #d9d9d9',
        borderRadius: 4,
      }}
    >
      <div
        style={{
          textAlign: 'center',
          fontSize: 12,
          padding: '8px 4px',
        }}
      >
        <div style={{ fontSize: 16, marginBottom: 4 }}>
          {iconMap[data.type] || <SwapOutlined />}
        </div>
        <div style={{ fontWeight: 'bold' }}>{data.label}</div>
      </div>

      {/* Input handles */}
      <Handle type="target" position={Position.Top} />

      {/* Output handles */}
      <Handle type="source" position={Position.Bottom} />
    </Card>
  );
};

export default ComponentNode;
