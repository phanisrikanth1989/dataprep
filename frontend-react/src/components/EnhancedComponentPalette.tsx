import { useState, useMemo, useRef, useEffect } from 'react';
import { Input, Collapse, Tooltip, Badge, Empty, Tag, Tabs, AutoComplete } from 'antd';
import type { SelectProps } from 'antd';
import {
  SearchOutlined,
  StarOutlined,
  StarFilled,
  DatabaseOutlined,
  FileTextOutlined,
  SettingOutlined,
  CloudOutlined,
  CodeOutlined,
  QuestionCircleOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  BranchesOutlined,
  FilterOutlined,
  SwapOutlined,
  MergeCellsOutlined,
  SortAscendingOutlined,
  CopyOutlined,
  TableOutlined,
  ApiOutlined,
  MailOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { ComponentMetadata } from '../types';
import './EnhancedComponentPalette.css';

interface Props {
  components: ComponentMetadata[];
  onComponentSelect?: (component: ComponentMetadata) => void;
}

// Component categories with icons
const CATEGORY_CONFIG = {
  Favorites: { icon: <StarFilled style={{ color: '#faad14' }} />, color: '#faad14' },
  Databases: { icon: <DatabaseOutlined style={{ color: '#1890ff' }} />, color: '#1890ff' },
  Files: { icon: <FileTextOutlined style={{ color: '#52c41a' }} />, color: '#52c41a' },
  File: { icon: <FileTextOutlined style={{ color: '#52c41a' }} />, color: '#52c41a' },
  Processing: { icon: <SettingOutlined style={{ color: '#722ed1' }} />, color: '#722ed1' },
  Transform: { icon: <SwapOutlined style={{ color: '#722ed1' }} />, color: '#722ed1' },
  Orchestration: { icon: <BranchesOutlined style={{ color: '#fa541c' }} />, color: '#fa541c' },
  Cloud: { icon: <CloudOutlined style={{ color: '#13c2c2' }} />, color: '#13c2c2' },
  Custom: { icon: <CodeOutlined style={{ color: '#eb2f96' }} />, color: '#eb2f96' },
  Database: { icon: <DatabaseOutlined style={{ color: '#1890ff' }} />, color: '#1890ff' },
};

// Component icons based on type
const getComponentIcon = (type: string): React.ReactNode => {
  const lowerType = type.toLowerCase();
  
  if (lowerType.includes('dbinput') || lowerType.includes('databaseinput')) return <DatabaseOutlined style={{ color: '#52c41a' }} />;
  if (lowerType.includes('dboutput') || lowerType.includes('databaseoutput')) return <DatabaseOutlined style={{ color: '#fa541c' }} />;
  if (lowerType.includes('input') && lowerType.includes('delimited')) return <FileTextOutlined style={{ color: '#1890ff' }} />;
  if (lowerType.includes('output') && lowerType.includes('delimited')) return <FileTextOutlined style={{ color: '#fa8c16' }} />;
  if (lowerType.includes('excel')) return <TableOutlined style={{ color: '#52c41a' }} />;
  if (lowerType.includes('json')) return <CodeOutlined style={{ color: '#eb2f96' }} />;
  if (lowerType.includes('xml')) return <CodeOutlined style={{ color: '#722ed1' }} />;
  if (lowerType.includes('map')) return <SwapOutlined style={{ color: '#1890ff' }} />;
  if (lowerType.includes('filter')) return <FilterOutlined style={{ color: '#faad14' }} />;
  if (lowerType.includes('sort')) return <SortAscendingOutlined style={{ color: '#13c2c2' }} />;
  if (lowerType.includes('join')) return <MergeCellsOutlined style={{ color: '#722ed1' }} />;
  if (lowerType.includes('aggregate')) return <ThunderboltOutlined style={{ color: '#fa541c' }} />;
  if (lowerType.includes('deduplicate') || lowerType.includes('unique')) return <CopyOutlined style={{ color: '#1890ff' }} />;
  if (lowerType.includes('log')) return <InfoCircleOutlined style={{ color: '#8c8c8c' }} />;
  if (lowerType.includes('api') || lowerType.includes('rest')) return <ApiOutlined style={{ color: '#13c2c2' }} />;
  if (lowerType.includes('mail') || lowerType.includes('email')) return <MailOutlined style={{ color: '#fa541c' }} />;
  if (lowerType.includes('wait') || lowerType.includes('sleep')) return <ClockCircleOutlined style={{ color: '#8c8c8c' }} />;
  if (lowerType.includes('touch')) return <FileTextOutlined style={{ color: '#52c41a' }} />;
  
  return <SettingOutlined style={{ color: '#8c8c8c' }} />;
};

export default function EnhancedComponentPalette({ components, onComponentSelect }: Props) {
  const [search, setSearch] = useState('');
  const [favorites, setFavorites] = useState<string[]>(['Map', 'FilterRows', 'FileInputDelimited']);
  const [selectedComponent, setSelectedComponent] = useState<ComponentMetadata | null>(null);
  const [activeTab, setActiveTab] = useState('components');
  const [searchFocused, setSearchFocused] = useState(false);
  const searchInputRef = useRef<any>(null);

  // Autocomplete options for search
  const searchOptions = useMemo((): SelectProps['options'] => {
    if (!search) return [];
    
    const filtered = components.filter(
      (c) =>
        c.label.toLowerCase().includes(search.toLowerCase()) ||
        c.type.toLowerCase().includes(search.toLowerCase())
    );

    return filtered.slice(0, 10).map((comp) => ({
      value: comp.type,
      label: (
        <div className="search-suggestion-item">
          <span className="suggestion-icon">{getComponentIcon(comp.type)}</span>
          <span className="suggestion-name">{comp.label}</span>
          <span className="suggestion-category">{comp.category}</span>
        </div>
      ),
    }));
  }, [components, search]);

  // Handle autocomplete select
  const handleSearchSelect = (value: string) => {
    const comp = components.find((c) => c.type === value);
    if (comp) {
      setSelectedComponent(comp);
      onComponentSelect?.(comp);
      setSearch('');
    }
  };

  // Toggle favorite
  const toggleFavorite = (type: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setFavorites((prev) =>
      prev.includes(type) ? prev.filter((f) => f !== type) : [...prev, type]
    );
  };

  // Group components by category with favorites at top
  const grouped = useMemo(() => {
    const filtered = components.filter(
      (c) =>
        c.label.toLowerCase().includes(search.toLowerCase()) ||
        c.type.toLowerCase().includes(search.toLowerCase()) ||
        c.description?.toLowerCase().includes(search.toLowerCase())
    );

    // Separate favorites
    const favs = filtered.filter((c) => favorites.includes(c.type));

    // Group by category
    const groups: Record<string, ComponentMetadata[]> = {};
    
    if (favs.length > 0) {
      groups['Favorites'] = favs;
    }

    filtered.forEach((c) => {
      const category = c.category || 'Other';
      if (!groups[category]) groups[category] = [];
      groups[category].push(c);
    });

    return groups;
  }, [components, search, favorites]);

  // Handle drag start
  const onDragStart = (event: React.DragEvent, componentType: string) => {
    event.dataTransfer.setData('application/reactflow', componentType);
    event.dataTransfer.effectAllowed = 'move';
  };

  // Handle component click for help
  const handleComponentClick = (component: ComponentMetadata) => {
    setSelectedComponent(component);
    onComponentSelect?.(component);
  };

  // Component item renderer
  const renderComponentItem = (comp: ComponentMetadata) => (
    <div
      key={comp.type}
      className={`component-item ${selectedComponent?.type === comp.type ? 'selected' : ''}`}
      draggable
      onDragStart={(e) => onDragStart(e, comp.type)}
      onClick={() => handleComponentClick(comp)}
      title={comp.description}
    >
      <div className="comp-icon">{getComponentIcon(comp.type)}</div>
      <div className="comp-info">
        <span className="comp-name">{comp.label}</span>
      </div>
      <div className="comp-actions">
        <Tooltip title={favorites.includes(comp.type) ? 'Remove from favorites' : 'Add to favorites'}>
          <button
            className="favorite-btn"
            onClick={(e) => toggleFavorite(comp.type, e)}
          >
            {favorites.includes(comp.type) ? (
              <StarFilled style={{ color: '#faad14' }} />
            ) : (
              <StarOutlined style={{ color: '#d9d9d9' }} />
            )}
          </button>
        </Tooltip>
      </div>
    </div>
  );

  // Collapse items
  const collapseItems = Object.entries(grouped).map(([category, items]) => {
    const config = CATEGORY_CONFIG[category as keyof typeof CATEGORY_CONFIG] || {
      icon: <SettingOutlined />,
      color: '#8c8c8c',
    };

    return {
      key: category,
      label: (
        <div className="category-header">
          {config.icon}
          <span className="category-name">{category}</span>
          <Badge count={items.length} style={{ backgroundColor: config.color }} />
        </div>
      ),
      children: <div className="components-list">{items.map(renderComponentItem)}</div>,
    };
  });

  // Component help panel
  const renderHelpPanel = () => {
    if (!selectedComponent) {
      return (
        <div className="help-empty">
          <QuestionCircleOutlined style={{ fontSize: 32, color: '#d9d9d9' }} />
          <p>Select a component to view help</p>
        </div>
      );
    }

    return (
      <div className="help-content">
        <div className="help-header">
          <div className="help-icon">{getComponentIcon(selectedComponent.type)}</div>
          <div className="help-title">
            <h3>{selectedComponent.label}</h3>
            <Tag color="blue">{selectedComponent.category}</Tag>
          </div>
        </div>

        <div className="help-section">
          <h4>Description</h4>
          <p>{selectedComponent.description || 'No description available'}</p>
        </div>

        <div className="help-section">
          <h4>Properties</h4>
          {selectedComponent.fields.length === 0 ? (
            <p className="no-props">No configurable properties</p>
          ) : (
            <div className="props-list">
              {selectedComponent.fields.map((field) => (
                <div key={field.name} className="prop-item">
                  <div className="prop-header">
                    <span className="prop-name">{field.label}</span>
                    {field.required && <Tag color="red" className="required-tag">Required</Tag>}
                  </div>
                  <div className="prop-type">Type: {field.type}</div>
                  {field.description && <div className="prop-desc">{field.description}</div>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="help-section">
          <h4>Connections</h4>
          <div className="connections-info">
            <div className="conn-item">
              <span className="conn-label">Inputs:</span>
              <span className="conn-value">{selectedComponent.input_count}</span>
            </div>
            <div className="conn-item">
              <span className="conn-label">Outputs:</span>
              <span className="conn-value">{selectedComponent.output_count}</span>
            </div>
          </div>
        </div>

        <div className="help-actions">
          <button
            className="drag-hint"
            onDragStart={(e) => onDragStart(e, selectedComponent.type)}
            draggable
          >
            🎯 Drag to canvas to add
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="enhanced-palette">
      <div className="palette-header">
        <span className="header-title">Components</span>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        className="palette-tabs"
        items={[
          {
            key: 'components',
            label: (
              <span>
                <SettingOutlined /> Palette
              </span>
            ),
          },
          {
            key: 'help',
            label: (
              <span>
                <QuestionCircleOutlined /> Help
              </span>
            ),
          },
        ]}
      />

      {activeTab === 'components' ? (
        <>
          <div className="palette-search">
            <AutoComplete
              ref={searchInputRef}
              options={searchOptions}
              onSelect={handleSearchSelect}
              onSearch={setSearch}
              value={search}
              onChange={setSearch}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              popupClassName="component-search-dropdown"
              style={{ width: '100%' }}
            >
              <Input
                prefix={<SearchOutlined />}
                placeholder="Type to search components..."
                allowClear
                size="small"
              />
            </AutoComplete>
            {searchFocused && search && (
              <div className="search-hint">
                Press Enter to select, or drag a component to canvas
              </div>
            )}
          </div>

          <div className="palette-content">
            {Object.keys(grouped).length === 0 ? (
              <Empty
                description="No components found"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : (
              <Collapse
                items={collapseItems}
                defaultActiveKey={[]}
                accordion
                ghost
                size="small"
                expandIconPosition="start"
                className="talend-collapse"
              />
            )}
          </div>

          <div className="palette-hint">
            <InfoCircleOutlined /> Drag components to canvas
          </div>
        </>
      ) : (
        <div className="help-panel">{renderHelpPanel()}</div>
      )}
    </div>
  );
}
