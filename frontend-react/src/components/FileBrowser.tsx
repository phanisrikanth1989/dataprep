import { useState, useEffect, useCallback } from 'react';
import { Modal, Input, Button, Breadcrumb, List, Space, Select, Spin, message } from 'antd';
import {
  FolderOutlined,
  FileOutlined,
  HomeOutlined,
  ArrowUpOutlined,
  ReloadOutlined,
  FolderAddOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import './FileBrowser.css';

interface FileItem {
  name: string;
  path: string;
  is_dir: boolean;
  size?: number;
  modified?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  mode?: 'file' | 'directory' | 'save';
  title?: string;
  fileFilter?: string;
  defaultPath?: string;
  defaultFileName?: string;
}

const API_BASE = 'http://localhost:8000/api/filesystem';

export default function FileBrowser({
  open,
  onClose,
  onSelect,
  mode = 'file',
  title = 'Select File',
  fileFilter,
  defaultPath = 'C:\\',
  defaultFileName = '',
}: Props) {
  const [currentPath, setCurrentPath] = useState(defaultPath);
  const [items, setItems] = useState<FileItem[]>([]);
  const [drives, setDrives] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<FileItem | null>(null);
  const [fileName, setFileName] = useState(defaultFileName);
  const [newFolderModalOpen, setNewFolderModalOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  // Load directory contents
  const loadDirectory = useCallback(async (path: string) => {
    setLoading(true);
    try {
      const params: any = { path, show_files: mode !== 'directory' };
      if (fileFilter) params.file_filter = fileFilter;
      
      const response = await axios.get(`${API_BASE}/browse`, { params });
      setItems(response.data.items);
      setDrives(response.data.drives || []);
      setCurrentPath(response.data.path);
      setSelectedItem(null);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to load directory');
    } finally {
      setLoading(false);
    }
  }, [mode, fileFilter]);

  // Initial load
  useEffect(() => {
    if (open) {
      loadDirectory(defaultPath);
      setFileName(defaultFileName);
    }
  }, [open, defaultPath, defaultFileName, loadDirectory]);

  // Handle item click
  const handleItemClick = (item: FileItem) => {
    if (item.is_dir) {
      loadDirectory(item.path);
    } else {
      setSelectedItem(item);
      setFileName(item.name);
    }
  };

  // Handle item double-click
  const handleItemDoubleClick = (item: FileItem) => {
    if (item.is_dir) {
      loadDirectory(item.path);
    } else {
      handleConfirm(item.path);
    }
  };

  // Go to parent directory
  const goUp = () => {
    const parentPath = currentPath.split('\\').slice(0, -1).join('\\') || 'C:\\';
    loadDirectory(parentPath);
  };

  // Handle drive change
  const handleDriveChange = (drive: string) => {
    loadDirectory(drive);
  };

  // Handle confirm selection
  const handleConfirm = (path?: string) => {
    let finalPath = path;
    
    if (!finalPath) {
      if (mode === 'directory') {
        finalPath = selectedItem?.is_dir ? selectedItem.path : currentPath;
      } else if (mode === 'save') {
        finalPath = fileName ? `${currentPath}\\${fileName}` : currentPath;
      } else {
        finalPath = selectedItem?.path || '';
      }
    }
    
    if (finalPath) {
      onSelect(finalPath);
      onClose();
    } else {
      message.warning('Please select a file or folder');
    }
  };

  // Create new folder
  const createNewFolder = async () => {
    if (!newFolderName.trim()) {
      message.warning('Please enter a folder name');
      return;
    }
    
    try {
      const newPath = `${currentPath}\\${newFolderName}`;
      await axios.post(`${API_BASE}/create-directory`, null, { params: { path: newPath } });
      message.success('Folder created');
      setNewFolderModalOpen(false);
      setNewFolderName('');
      loadDirectory(currentPath);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to create folder');
    }
  };

  // Parse path to breadcrumb items
  const pathParts = currentPath.split('\\').filter(Boolean);

  // Format file size
  const formatSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  };

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onClose}
      width={700}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button key="confirm" type="primary" onClick={() => handleConfirm()}>
          {mode === 'save' ? 'Save' : 'Select'}
        </Button>,
      ]}
      className="file-browser-modal"
    >
      <div className="file-browser">
        {/* Toolbar */}
        <div className="browser-toolbar">
          <Space>
            <Select
              value={currentPath.split('\\')[0] + '\\'}
              onChange={handleDriveChange}
              style={{ width: 80 }}
              options={drives.map(d => ({ label: d, value: d }))}
            />
            <Button icon={<ArrowUpOutlined />} onClick={goUp} title="Go up">
              Up
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => loadDirectory(currentPath)} title="Refresh">
              Refresh
            </Button>
            <Button icon={<FolderAddOutlined />} onClick={() => setNewFolderModalOpen(true)} title="New folder">
              New Folder
            </Button>
          </Space>
        </div>

        {/* Breadcrumb */}
        <div className="browser-breadcrumb">
          <Breadcrumb
            items={[
              {
                title: <HomeOutlined />,
                onClick: () => loadDirectory(drives[0] || 'C:\\'),
              },
              ...pathParts.map((part, index) => ({
                title: part,
                onClick: () => {
                  const newPath = pathParts.slice(0, index + 1).join('\\');
                  loadDirectory(newPath + (index === 0 ? '\\' : ''));
                },
              })),
            ]}
          />
        </div>

        {/* File list */}
        <div className="browser-content">
          <Spin spinning={loading}>
            <List
              size="small"
              dataSource={items}
              locale={{ emptyText: 'Empty folder' }}
              renderItem={(item) => (
                <List.Item
                  className={`file-item ${selectedItem?.path === item.path ? 'selected' : ''}`}
                  onClick={() => handleItemClick(item)}
                  onDoubleClick={() => handleItemDoubleClick(item)}
                >
                  <div className="file-item-content">
                    <span className="file-icon">
                      {item.is_dir ? (
                        <FolderOutlined style={{ color: '#faad14', fontSize: 18 }} />
                      ) : (
                        <FileOutlined style={{ color: '#1890ff', fontSize: 18 }} />
                      )}
                    </span>
                    <span className="file-name">{item.name}</span>
                    <span className="file-size">{formatSize(item.size)}</span>
                  </div>
                </List.Item>
              )}
            />
          </Spin>
        </div>

        {/* File name input (for save mode) */}
        {mode === 'save' && (
          <div className="browser-filename">
            <Input
              addonBefore="File name:"
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
              placeholder="Enter file name"
            />
          </div>
        )}

        {/* Current path display */}
        <div className="browser-path">
          <Input
            addonBefore="Path:"
            value={selectedItem?.path || (mode === 'save' && fileName ? `${currentPath}\\${fileName}` : currentPath)}
            readOnly
          />
        </div>
      </div>

      {/* New Folder Modal */}
      <Modal
        title="Create New Folder"
        open={newFolderModalOpen}
        onCancel={() => setNewFolderModalOpen(false)}
        onOk={createNewFolder}
        okText="Create"
      >
        <Input
          value={newFolderName}
          onChange={(e) => setNewFolderName(e.target.value)}
          placeholder="Enter folder name"
          onPressEnter={createNewFolder}
        />
      </Modal>
    </Modal>
  );
}
