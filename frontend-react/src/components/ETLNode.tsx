import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import './ETLNode.css';

export interface ETLNodeData {
  label: string;
  type: string;
  name?: string;
  config?: Record<string, any>;
}

function ETLNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ETLNodeData;
  
  return (
    <div className={`etl-node ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Left} className="handle input-handle" />
      
      <div className="node-content">
        <div className="node-type">{nodeData.type}</div>
        <div className="node-label">{nodeData.name || nodeData.label}</div>
      </div>
      
      <Handle type="source" position={Position.Right} className="handle output-handle" />
    </div>
  );
}

export default memo(ETLNode);
