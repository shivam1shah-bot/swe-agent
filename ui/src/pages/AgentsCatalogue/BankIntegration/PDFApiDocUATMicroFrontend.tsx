/**
 * PDF API Doc UAT Micro-Frontend Page
 * 
 * Storage Management Interface with:
 * - Storage information display
 * - Manual cleanup trigger
 * - Force cleanup option
 * - Emergency cleanup for critical situations
 */

import React, { useState, useEffect } from 'react';
import { Trash2, Database, AlertTriangle } from 'lucide-react';

interface StorageInfo {
  outputs_size_mb: number;
  temp_size_mb: number;
  archive_size_mb: number;
  total_size_mb: number;
  max_size_mb: number;
  usage_percentage: number;
  cleanup_triggered: boolean;
}

interface FileStatistics {
  total_outputs: number;
  total_temp_files: number;
  total_archived: number;
}

interface CleanupResults {
  cleanup_type: string;
  cleanup_results: {
    files_archived?: number;
    files_deleted?: number;
    bytes_freed?: number;
    temp_files_cleaned?: number;
    space_freed_mb?: number;
  };
  storage_info_after_cleanup: StorageInfo;
}

const PDFApiDocUATMicroFrontend: React.FC = () => {
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null);
  const [fileStats, setFileStats] = useState<FileStatistics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastCleanup, setLastCleanup] = useState<CleanupResults | null>(null);

  // Fetch storage information
  const fetchStorageInfo = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/agents-catalogue/pdf-api-doc-uat/storage-info');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.success) {
        setStorageInfo(data.storage_info);
        setFileStats(data.file_statistics);
      } else {
        setError('Failed to retrieve storage information');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  // Trigger cleanup operations
  const triggerCleanup = async (cleanupType: 'normal' | 'force' | 'emergency') => {
    setIsLoading(true);
    setError(null);
    setLastCleanup(null);

    try {
      let url = '/agents-catalogue/pdf-api-doc-uat/cleanup';

      switch (cleanupType) {
        case 'force':
          url += '?force=true';
          break;
        case 'emergency':
          url += '?force=true';
          break;
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.success) {
        setLastCleanup(data);
        // Refresh storage info after cleanup
        setTimeout(fetchStorageInfo, 1000);
      } else {
        setError('Cleanup operation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cleanup operation failed');
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-refresh storage info every 30 seconds
  useEffect(() => {
    fetchStorageInfo();
    
    const interval = setInterval(fetchStorageInfo, 30000);
    return () => clearInterval(interval);
  }, []);

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return 'text-red-600 bg-red-100';
    if (percentage >= 70) return 'text-orange-600 bg-orange-100';
    if (percentage >= 50) return 'text-yellow-600 bg-yellow-100';
    return 'text-green-600 bg-green-100';
  };

  const getProgressBarColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 70) return 'bg-orange-500';
    if (percentage >= 50) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">PDF API Doc UAT Storage Management</h1>
            <p className="text-gray-600 mt-1">Monitor storage usage and manage file cleanup</p>
          </div>
          <button
            onClick={fetchStorageInfo}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
          >
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4" />
            <span>Error: {error}</span>
          </div>
        </div>
      )}

      {/* Storage Information */}
      {storageInfo && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Storage Overview</h2>
          
          {/* Usage Progress Bar */}
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">Storage Usage</span>
              <span className={`text-sm font-bold px-2 py-1 rounded ${getUsageColor(storageInfo.usage_percentage)}`}>
                {storageInfo.usage_percentage}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div 
                className={`h-3 rounded-full transition-all duration-500 ${getProgressBarColor(storageInfo.usage_percentage)}`}
                style={{ width: `${Math.min(storageInfo.usage_percentage, 100)}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>{storageInfo.total_size_mb.toFixed(2)} MB used</span>
              <span>{storageInfo.max_size_mb} MB total</span>
            </div>
          </div>

          {/* Storage Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <h3 className="text-sm font-medium text-blue-800 mb-1">Output Files</h3>
              <div className="text-2xl font-bold text-blue-900">{storageInfo.outputs_size_mb.toFixed(2)} MB</div>
              {fileStats && (
                <div className="text-xs text-blue-600">{fileStats.total_outputs} files</div>
              )}
            </div>
            
            <div className="bg-yellow-50 p-4 rounded-lg">
              <h3 className="text-sm font-medium text-yellow-800 mb-1">Temporary Files</h3>
              <div className="text-2xl font-bold text-yellow-900">{storageInfo.temp_size_mb.toFixed(2)} MB</div>
              {fileStats && (
                <div className="text-xs text-yellow-600">{fileStats.total_temp_files} files</div>
              )}
            </div>
            
            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="text-sm font-medium text-gray-800 mb-1">Archived Files</h3>
              <div className="text-2xl font-bold text-gray-900">{storageInfo.archive_size_mb.toFixed(2)} MB</div>
              {fileStats && (
                <div className="text-xs text-gray-600">{fileStats.total_archived} files</div>
              )}
            </div>
          </div>

          {/* Cleanup Status */}
          {storageInfo.cleanup_triggered && (
            <div className="mt-4 p-3 bg-orange-100 border border-orange-300 rounded-lg">
              <div className="text-orange-800 text-sm">
                Automatic cleanup was triggered due to high storage usage
              </div>
            </div>
          )}
        </div>
      )}

      {/* Cleanup Actions */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Cleanup Operations</h2>
        <p className="text-gray-600 mb-6">
          Manually trigger cleanup operations to free up storage space and archive old files.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Standard Cleanup */}
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-3">
              <Database className="w-5 h-5 text-blue-600" />
              <h3 className="font-medium text-gray-900">Standard Cleanup</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Archive files older than 24 hours and clean temporary files older than 2 hours.
            </p>
            <button
              onClick={() => triggerCleanup('normal')}
              disabled={isLoading}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
            >
              Run Standard Cleanup
            </button>
          </div>

          {/* Force Cleanup */}
          <div className="border border-orange-200 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-3">
              <Trash2 className="w-5 h-5 text-orange-600" />
              <h3 className="font-medium text-gray-900">Force Cleanup</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              More aggressive cleanup - archive files older than 6 hours and clean all temporary files.
            </p>
            <button
              onClick={() => triggerCleanup('force')}
              disabled={isLoading}
              className="w-full px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:bg-gray-400"
            >
              Run Force Cleanup
            </button>
          </div>

          {/* Emergency Cleanup */}
          <div className="border border-red-200 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-3">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              <h3 className="font-medium text-gray-900">Emergency Cleanup</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Critical storage situation - clean all temporary files and aggressively archive outputs.
            </p>
            <button
              onClick={() => triggerCleanup('emergency')}
              disabled={isLoading}
              className="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-400"
            >
              Emergency Cleanup
            </button>
          </div>
        </div>
      </div>

      {/* Last Cleanup Results */}
      {lastCleanup && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Last Cleanup Results</h2>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">
                {lastCleanup.cleanup_results.files_archived || 0}
              </div>
              <div className="text-xs text-gray-600">Files Archived</div>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">
                {lastCleanup.cleanup_results.files_deleted || 0}
              </div>
              <div className="text-xs text-gray-600">Files Deleted</div>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">
                {lastCleanup.cleanup_results.temp_files_cleaned || 0}
              </div>
              <div className="text-xs text-gray-600">Temp Files Cleaned</div>
            </div>
            
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {(lastCleanup.cleanup_results.space_freed_mb || 0).toFixed(2)} MB
              </div>
              <div className="text-xs text-gray-600">Space Freed</div>
            </div>
          </div>

          <div className="text-sm text-gray-600">
            <span className="font-medium">Cleanup Type:</span> {lastCleanup.cleanup_type}
            <span className="ml-4 font-medium">Storage After Cleanup:</span> {lastCleanup.storage_info_after_cleanup.usage_percentage.toFixed(1)}% used
          </div>
        </div>
      )}

      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="flex items-center space-x-3">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span>Processing cleanup operation...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PDFApiDocUATMicroFrontend; 