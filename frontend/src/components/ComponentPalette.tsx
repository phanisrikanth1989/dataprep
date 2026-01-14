import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Collapse } from 'antd';
import { componentsAPI } from '../services/api.ts';

interface ComponentPaletteProps {
  onComponentDragStart: (componentType: string) => void;
}

interface ComponentsByCategory {
  [category: string]: Array<{
    type: string;
    label: string;
    icon: string;
    description: string;
  }>;
}

const ComponentPalette: React.FC<ComponentPaletteProps> = ({ onComponentDragStart }) => {
  const [components, setComponents] = useState<ComponentsByCategory>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadComponents = async () => {
      try {
        const response = await componentsAPI.list();
        setComponents(response.data);
      } catch (error) {
        console.error('Error loading components:', error);
      } finally {
        setLoading(false);
      }
    };

    loadComponents();
  }, []);

  const handleDragStart = (e: React.DragEvent, componentType: string) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('componentType', componentType);
    onComponentDragStart(componentType);
  };

  const items = Object.entries(components).map(([category, comps]) => ({
    key: category,
    label: category,
    children: (
      <Row gutter={[8, 8]}>
        {comps.map((comp) => (
          <Col key={comp.type} span={24}>
            <Card
              hoverable
              draggable
              onDragStart={(e) => handleDragStart(e, comp.type)}
              size="small"
              style={{
                cursor: 'move',
                padding: '8px',
              }}
            >
              <div style={{ fontSize: 12 }}>
                <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{comp.label}</div>
                <div style={{ fontSize: 11, color: '#666' }}>{comp.description}</div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    ),
  }));

  return (
    <div
      style={{
        padding: '10px',
        borderRight: '1px solid #ddd',
        overflowY: 'auto',
        maxHeight: '100%',
      }}
    >
      <div style={{ marginBottom: 16, fontWeight: 'bold', fontSize: 14 }}>
        Components
      </div>
      <Collapse items={items} accordion />
    </div>
  );
};

export default ComponentPalette;
