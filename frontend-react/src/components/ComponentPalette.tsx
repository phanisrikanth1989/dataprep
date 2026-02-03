import { useState, useMemo } from 'react';
import { Input, Collapse } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { ComponentMetadata } from '../types';
import './ComponentPalette.css';

interface Props {
  components: ComponentMetadata[];
}

// Get icon based on component type
const getComponentIcon = (type: string): string => {
  const lowerType = type.toLowerCase();
  if (lowerType.includes('input')) return '📥';
  if (lowerType.includes('output')) return '📤';
  if (lowerType.includes('map')) return '🔀';
  if (lowerType.includes('filter')) return '🔍';
  if (lowerType.includes('sort')) return '📊';
  if (lowerType.includes('aggregate')) return '📈';
  if (lowerType.includes('join')) return '🔗';
  if (lowerType.includes('union')) return '⊕';
  if (lowerType.includes('database')) return '🗄️';
  if (lowerType.includes('excel')) return '📗';
  if (lowerType.includes('json')) return '{ }';
  if (lowerType.includes('xml')) return '📋';
  return '⚙️';
};

export default function ComponentPalette({ components }: Props) {
  const [search, setSearch] = useState('');

  // Group components by category
  const grouped = useMemo(() => {
    const filtered = components.filter(
      (c) =>
        c.label.toLowerCase().includes(search.toLowerCase()) ||
        c.type.toLowerCase().includes(search.toLowerCase())
    );

    const groups: Record<string, ComponentMetadata[]> = {};
    filtered.forEach((c) => {
      if (!groups[c.category]) groups[c.category] = [];
      groups[c.category].push(c);
    });
    return groups;
  }, [components, search]);

  const onDragStart = (event: React.DragEvent, componentType: string) => {
    event.dataTransfer.setData('application/reactflow', componentType);
    event.dataTransfer.effectAllowed = 'move';
  };

  const collapseItems = Object.entries(grouped).map(([category, items]) => ({
    key: category,
    label: (
      <span className="category-label">
        {category} <span className="count">{items.length}</span>
      </span>
    ),
    children: (
      <div className="components-list">
        {items.map((comp) => (
          <div
            key={comp.type}
            className="component-item"
            draggable
            onDragStart={(e) => onDragStart(e, comp.type)}
            title={comp.description}
          >
            <span className="comp-icon">{getComponentIcon(comp.type)}</span>
            <span className="comp-name">{comp.label}</span>
          </div>
        ))}
      </div>
    ),
  }));

  return (
    <div className="component-palette">
      <div className="palette-header">
        <h3>Components</h3>
      </div>
      
      <div className="palette-search">
        <Input
          prefix={<SearchOutlined />}
          placeholder="Search components..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
      </div>

      <div className="palette-content">
        {Object.keys(grouped).length === 0 ? (
          <div className="no-results">No components found</div>
        ) : (
          <Collapse
            items={collapseItems}
            defaultActiveKey={Object.keys(grouped)}
            ghost
            size="small"
          />
        )}
      </div>
      
      <div className="palette-hint">
        Drag components to canvas
      </div>
    </div>
  );
}
