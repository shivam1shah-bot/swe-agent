/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
/**
 * PDF API Documentation & UAT Testing Component
 * 
 * Provides a comprehensive interface for:
 * - PDF file upload and processing
 * - Custom crypto specification uploads  
 * - UAT testing configuration
 * - Real-time progress tracking
 * - Results display and download
 */

import React, { useState, useCallback, useEffect } from 'react';
import { 
  FileText, 
  Settings, 
  Play, 
  CheckCircle, 
  AlertCircle, 
  Download,
  Key,
  Clock
} from 'lucide-react';
import { getAuthCredentials, createBasicAuthHeader } from '../../../lib/auth';
import { getApiBaseUrl } from '../../../lib/environment';
import { apiClient } from '../../../lib/api';

interface PDFApiDocUATState {
  // File uploads
  pdfFile: File | null;
  cryptoFile: File | null;
  
  // Configuration
  bankName: string;
  customPrompt: string;
  apisToTest: string[];
  enableEncryption: boolean;
  
  // Processing state
  isProcessing: boolean;
  currentStep: string;
  progress: number;
  status: string | null; // Track actual task status
  
  // Results
  taskId: string | null;
  results: any | null;
  error: string | null;
  
  // UI state
  activeTab: string;
  showAdvancedSettings: boolean;
}

interface FileUploadProps {
  label: string;
  description: string;
  accept: string;
  file: File | null;
  onFileSelect: (file: File | null) => void;
  icon: React.ReactNode;
  required?: boolean;
}

const FileUploadZone: React.FC<FileUploadProps> = ({
  label,
  description,
  accept,
  file,
  onFileSelect,
  icon,
  required = false
}) => {
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      onFileSelect(droppedFiles[0]);
    }
  }, [onFileSelect]);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null;
    onFileSelect(selectedFile);
  }, [onFileSelect]);

  return (
    <div className="mb-6">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {icon} {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          file ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => document.getElementById(`file-input-${label}`)?.click()}
      >
        <input
          id={`file-input-${label}`}
          type="file"
          accept={accept}
          onChange={handleFileSelect}
          className="hidden"
        />
        
        {file ? (
          <div className="flex items-center justify-center space-x-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="text-green-700 font-medium">{file.name}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onFileSelect(null);
              }}
              className="text-red-500 hover:text-red-700"
            >
              ×
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-gray-500">
              {icon}
            </div>
            <div>
              <p className="text-lg font-medium text-gray-700">Drop file here or click to browse</p>
              <p className="text-sm text-gray-500">{description}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const PDFApiDocUATComponent: React.FC = () => {
  const [state, setState] = useState<PDFApiDocUATState>({
    pdfFile: null,
    cryptoFile: null,
    bankName: '',
    customPrompt: '',
    apisToTest: [],
    enableEncryption: false,
    isProcessing: false,
    currentStep: '',
    progress: 0,
    status: null,
    taskId: null,
    results: null,
    error: null,
    activeTab: 'setup',
    showAdvancedSettings: false
  });

  const [cryptoFileUploaded, setCryptoFileUploaded] = useState<string | null>(null);
  const [pdfFileUploaded, setPdfFileUploaded] = useState<string | null>(null);

  // Debug state changes
  useEffect(() => {
    console.log('PDFApiDocUATComponent state updated:', {
      taskId: state.taskId,
      status: state.status,
      isProcessing: state.isProcessing,
      currentStep: state.currentStep,
      progress: state.progress,
      error: state.error,
      hasResults: !!state.results
    });
  }, [state.taskId, state.status, state.isProcessing, state.currentStep, state.progress, state.error, state.results]);

  // Handle crypto file upload to server
  const uploadCryptoFile = async (file: File): Promise<string | null> => {
    try {
      const response = await apiClient.uploadFile(file, 'crypto');
      return response.crypto_file_path || response.file_path || null;
    } catch (error) {
      console.error('Crypto file upload failed:', error);
      throw error; // Re-throw to allow caller to handle
    }
  };

  // Handle PDF file upload to server
  const uploadPdfFile = async (file: File): Promise<string | null> => {
    try {
      const response = await apiClient.uploadFile(file, 'pdf');
      return response.pdf_file_path || response.file_path || null;
    } catch (error) {
      console.error('PDF file upload failed:', error);
      throw error; // Re-throw to allow caller to handle
    }
  };

  // Handle crypto file selection
  const handleCryptoFileSelect = async (file: File | null) => {
    setState(prev => ({ ...prev, cryptoFile: file, error: null }));
    
    if (file) {
      try {
        const uploadedPath = await uploadCryptoFile(file);
        setCryptoFileUploaded(uploadedPath);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to upload crypto file';
        setState(prev => ({ 
          ...prev, 
          error: errorMessage,
          cryptoFile: null 
        }));
        setCryptoFileUploaded(null);
      }
    } else {
      setCryptoFileUploaded(null);
    }
  };

  // Handle PDF file selection
  const handlePdfFileSelect = async (file: File | null) => {
    setState(prev => ({ ...prev, pdfFile: file, error: null }));
    
    if (file) {
      try {
        const uploadedPath = await uploadPdfFile(file);
        setPdfFileUploaded(uploadedPath);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to upload PDF file';
        setState(prev => ({ 
          ...prev, 
          error: errorMessage,
          pdfFile: null 
        }));
        setPdfFileUploaded(null);
      }
    } else {
      setPdfFileUploaded(null);
    }
  };

  // Start UAT processing
  const startUATProcess = async () => {
    if (!state.pdfFile || !state.bankName.trim()) {
      setState(prev => ({ ...prev, error: 'PDF file and bank name are required' }));
      return;
    }

    if (!pdfFileUploaded) {
      setState(prev => ({ ...prev, error: 'PDF file must be uploaded before processing' }));
      return;
    }

    setState(prev => ({ 
      ...prev, 
      isProcessing: true, 
      error: null, 
      currentStep: 'Starting UAT process...',
      progress: 10
    }));

    try {
      const requestData = {
        pdf_file_path: pdfFileUploaded,
        bank_name: state.bankName,
        custom_prompt: state.customPrompt || 'Generate comprehensive API documentation',
        apis_to_test: state.apisToTest.filter(api => api.trim().length > 0),
        enable_encryption: state.enableEncryption,
        ...(cryptoFileUploaded && { crypto_file_path: cryptoFileUploaded })
      };

      // Submit UAT request
      setState(prev => ({ ...prev, currentStep: 'Processing PDF...', progress: 30 }));

      const credentials = await getAuthCredentials();
      const authHeader = createBasicAuthHeader(credentials.username, credentials.password);
      const apiBaseUrl = getApiBaseUrl();

      const response = await fetch(`${apiBaseUrl}/api/v1/agents-catalogue/workflow/pdf-api-doc-uat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': authHeader,
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        throw new Error('Failed to start UAT process');
      }

      const result = await response.json();
      console.log('UAT Process started successfully:', result);
      
      setState(prev => ({ 
        ...prev, 
        taskId: result.task_id,
        status: 'created', // Set initial status
        currentStep: 'UAT processing started...',
        progress: 30
      }));

      // Poll for results
      console.log('Starting polling for task:', result.task_id);
      pollForResults(result.task_id);

    } catch (error) {
      setState(prev => ({ 
        ...prev, 
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        isProcessing: false
      }));
    }
  };

  // Poll for processing results
  const pollForResults = async (taskId: string) => {
    let pollAttempts = 0;
    const maxAttempts = 30; // 5 minutes at 10-second intervals
    
    console.log(`Starting polling for task ${taskId} with 10-second intervals`);
    
    const pollInterval = setInterval(async () => {
      pollAttempts++;
      
      try {
        const credentials = await getAuthCredentials();
        const authHeader = createBasicAuthHeader(credentials.username, credentials.password);
        const apiBaseUrl = getApiBaseUrl();

        console.log(`Polling attempt ${pollAttempts} for task ${taskId}`);
        
        const response = await fetch(`${apiBaseUrl}/api/v1/tasks/${taskId}`, {
          headers: {
            'Authorization': authHeader,
            'Content-Type': 'application/json',
          },
        });
        
        if (!response.ok) {
          console.error(`API request failed with status ${response.status}: ${response.statusText}`);
          if (response.status === 401) {
            console.error('Authentication failed - check credentials');
          }
          return; // Continue polling on API errors
        }

        const task = await response.json();
        console.log(`Task status update - Attempt ${pollAttempts}:`, task);
        
        // Update state with current status
        setState(prev => ({
          ...prev,
          status: task.status
        }));

        if (task.status === 'completed') {
          clearInterval(pollInterval);
          console.log('Task completed successfully');
          setState(prev => ({ 
            ...prev, 
            status: 'completed',
            results: task.result,
            isProcessing: false,
            progress: 100,
            currentStep: 'Completed!',
            activeTab: 'results'
          }));
        } else if (task.status === 'failed') {
          clearInterval(pollInterval);
          console.log('Task failed:', task.error);
          setState(prev => ({ 
            ...prev, 
            status: 'failed',
            error: task.error || task.result?.error || 'Processing failed - no details provided',
            isProcessing: false
          }));
        } else if (task.status === 'pending' || task.status === 'running' || task.status === 'created') {
          // Keep polling for these statuses
          let progress = 30;
          let currentStep = 'Processing...';
          
          if (task.status === 'pending') {
            progress = 40;
            currentStep = 'Task pending...';
          } else if (task.status === 'running') {
            progress = 50;
            currentStep = 'Running...';
          }
          
          if (task.result?.workflow_status === 'parsing_pdf') {
            progress = 60;
            currentStep = 'Parsing PDF content...';
          } else if (task.result?.workflow_status === 'generating_docs') {
            progress = 70;
            currentStep = 'Generating API documentation...';
          } else if (task.result?.workflow_status === 'extracting_urls') {
            progress = 80;
            currentStep = 'Extracting API endpoints...';
          } else if (task.result?.workflow_status === 'executing_tests') {
            progress = 90;
            currentStep = 'Running UAT tests...';
          }

          setState(prev => ({ ...prev, progress, currentStep, status: task.status }));
        }
        
        // Stop polling if max attempts reached
        if (pollAttempts >= maxAttempts) {
          clearInterval(pollInterval);
          console.warn('Polling timeout reached');
          setState(prev => ({ 
            ...prev, 
            error: 'Processing timeout - task is taking longer than expected',
            isProcessing: false
          }));
        }
        
      } catch (error) {
        console.error('Error polling for results:', error);
        
        // Stop polling on persistent errors after several attempts
        if (pollAttempts > 5 && pollAttempts % 5 === 0) {
          console.error(`Persistent polling error after ${pollAttempts} attempts:`, error);
        }
        
        // Stop polling if we've had too many consecutive errors
        if (pollAttempts >= maxAttempts) {
          clearInterval(pollInterval);
          setState(prev => ({ 
            ...prev, 
            error: 'Network error - unable to check task status',
            isProcessing: false
          }));
        }
      }
    }, 10000); // 10 seconds as requested

    // Cleanup timeout (redundant with attempt counter but keeping for safety)
    setTimeout(() => {
      clearInterval(pollInterval);
      if (state.isProcessing && pollAttempts < maxAttempts) {
        console.warn('Polling cleanup timeout triggered');
        setState(prev => ({ 
          ...prev, 
          error: 'Processing timeout - please check task status manually',
          isProcessing: false
        }));
      }
    }, 300000); // 5 minutes timeout
  };

  // Download results file
  const downloadFile = async (fileType: string) => {
    if (!state.taskId) return;

    try {
      const response = await fetch(`/agents-catalogue/pdf-api-doc-uat/download/${state.taskId}/${fileType}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${state.bankName}_${fileType}_${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const TabButton: React.FC<{ id: string; label: string; icon: React.ReactNode }> = ({ id, label, icon }) => (
    <button
      onClick={() => setState(prev => ({ ...prev, activeTab: id }))}
      className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
        state.activeTab === id 
          ? 'bg-blue-500 text-white' 
          : 'text-gray-600 hover:bg-gray-100'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        {/* Header */}
        <div className="border-b border-gray-200 p-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center space-x-2">
            <FileText className="w-6 h-6" />
            <span>PDF API Documentation & UAT Testing</span>
          </h1>
          <p className="text-gray-600 mt-2">
            Upload PDF specifications, configure UAT testing, and generate comprehensive API documentation with automated testing.
          </p>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <div className="flex space-x-1 p-4">
            <TabButton id="setup" label="Setup" icon={<Settings className="w-4 h-4" />} />
            <TabButton id="processing" label="Processing" icon={<Clock className="w-4 h-4" />} />
            <TabButton id="results" label="Results" icon={<CheckCircle className="w-4 h-4" />} />
          </div>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Setup Tab */}
          {state.activeTab === 'setup' && (
            <div className="space-y-6">
              {/* PDF File Upload */}
              <FileUploadZone
                label="PDF API Specification"
                description="Upload your bank's API specification document (.pdf)"
                accept=".pdf"
                file={state.pdfFile}
                onFileSelect={handlePdfFileSelect}
                icon={<FileText className="w-8 h-8 mx-auto text-gray-400" />}
                required
              />

              {/* Crypto File Upload */}
              <FileUploadZone
                label="Custom Crypto Specification (Optional)"
                description="Upload custom encryption specifications (.txt, .md, .json)"
                accept=".txt,.md,.json"
                file={state.cryptoFile}
                onFileSelect={handleCryptoFileSelect}
                icon={<Key className="w-8 h-8 mx-auto text-gray-400" />}
              />

              {/* Bank Configuration */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bank Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={state.bankName}
                    onChange={(e) => setState(prev => ({ ...prev, bankName: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    placeholder="e.g., HDFC Bank, Yes Bank, ICICI"
                  />
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="enableEncryption"
                    checked={state.enableEncryption}
                    onChange={(e) => setState(prev => ({ ...prev, enableEncryption: e.target.checked }))}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="enableEncryption" className="text-sm font-medium text-gray-700">
                    Enable Encryption Testing
                  </label>
                </div>
              </div>

              {/* Advanced Settings */}
              <div>
                <button
                  onClick={() => setState(prev => ({ ...prev, showAdvancedSettings: !prev.showAdvancedSettings }))}
                  className="flex items-center space-x-2 text-blue-600 hover:text-blue-800 font-medium"
                >
                  <span>{state.showAdvancedSettings ? '▼' : '▶'}</span>
                  <span>Advanced Settings</span>
                </button>

                {state.showAdvancedSettings && (
                  <div className="mt-4 space-y-4 p-4 bg-gray-50 rounded-lg">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Custom Prompt (Optional)
                      </label>
                      <textarea
                        value={state.customPrompt}
                        onChange={(e) => setState(prev => ({ ...prev, customPrompt: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        rows={3}
                        placeholder="Custom instructions for API documentation generation..."
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Specific APIs to Test (Optional)
                      </label>
                      <input
                        type="text"
                        value={state.apisToTest.join(', ')}
                        onChange={(e) => setState(prev => ({ 
                          ...prev, 
                          apisToTest: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                        placeholder="fund_transfer, balance_inquiry, status_check"
                      />
                      <p className="text-xs text-gray-500 mt-1">Comma-separated list of API names to focus on</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex justify-between items-center pt-4 border-t border-gray-200">
                <div>
                  {state.error && (
                    <div className="flex items-center space-x-2 text-red-600">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-sm">{state.error}</span>
                    </div>
                  )}
                </div>
                
                <button
                  onClick={startUATProcess}
                  disabled={!state.pdfFile || !state.bankName.trim() || state.isProcessing}
                  className="flex items-center space-x-2 bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  <Play className="w-4 h-4" />
                  <span>Start UAT Processing</span>
                </button>
              </div>
            </div>
          )}

          {/* Processing Tab */}
          {state.activeTab === 'processing' && (
            <div className="space-y-6">
              <div className="text-center">
                <Clock className="w-16 h-16 mx-auto text-blue-500 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">Processing Your Request</h3>
                <p className="text-gray-600">{state.currentStep}</p>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${state.progress}%` }}
                ></div>
              </div>
              
              <div className="text-center text-sm text-gray-500">
                {state.progress}% Complete
              </div>

              {state.taskId && (
                <div className="text-center text-xs text-gray-400">
                  Task ID: {state.taskId}
                </div>
              )}
            </div>
          )}

          {/* Results Tab */}
          {state.activeTab === 'results' && (
            <div className="space-y-6">
              {/* Show status information */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <Clock className="w-5 h-5 text-blue-500" />
                  <span className="font-medium">Task Status: {state.status || 'Unknown'}</span>
                </div>
                {state.taskId && (
                  <p className="text-sm text-gray-600">Task ID: {state.taskId}</p>
                )}
                {state.currentStep && (
                  <p className="text-sm text-gray-600">Current Step: {state.currentStep}</p>
                )}
              </div>

              {/* Show failure details when status is failed */}
              {state.status === 'failed' && (
                <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
                  <div className="flex items-center space-x-2 text-red-600 mb-2">
                    <AlertCircle className="w-5 h-5" />
                    <span className="font-medium">Task Failed</span>
                  </div>
                  <p className="text-red-700">{state.error || 'No failure details available'}</p>
                </div>
              )}

              {/* Show success and download buttons only when completed */}
              {state.status === 'completed' && state.results && (
                <div>
                  <div className="flex items-center space-x-2 text-green-600 mb-4">
                    <CheckCircle className="w-5 h-5" />
                    <span className="font-medium">UAT Processing Completed Successfully!</span>
                  </div>

                  {/* Download Buttons - Only show when completed */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                    <button
                      onClick={() => downloadFile('api_documentation')}
                      className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                    >
                      <Download className="w-4 h-4" />
                      <span>API Docs</span>
                    </button>
                    
                    <button
                      onClick={() => downloadFile('uat_results')}
                      className="flex items-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700"
                    >
                      <Download className="w-4 h-4" />
                      <span>UAT Results</span>
                    </button>
                    
                    <button
                      onClick={() => downloadFile('curl_commands')}
                      className="flex items-center space-x-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700"
                    >
                      <Download className="w-4 h-4" />
                      <span>Curl Commands</span>
                    </button>
                    
                    <button
                      onClick={() => downloadFile('integration_code')}
                      className="flex items-center space-x-2 bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700"
                    >
                      <Download className="w-4 h-4" />
                      <span>Integration Code</span>
                    </button>
                  </div>

                  {/* Results Display */}
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h3 className="font-bold text-lg mb-3">Processing Results</h3>
                    <div className="space-y-4">
                      {/* Display results content here */}
                      <pre className="bg-white p-3 rounded border text-sm overflow-auto max-h-96">
                        {JSON.stringify(state.results, null, 2)}
                      </pre>
                    </div>
                  </div>

                  {/* Start New Process */}
                  <div className="pt-4 border-t border-gray-200">
                    <button
                      onClick={() => {
                        setState({
                          pdfFile: null,
                          cryptoFile: null,
                          bankName: '',
                          customPrompt: '',
                          apisToTest: [],
                          enableEncryption: false,
                          isProcessing: false,
                          currentStep: '',
                          progress: 0,
                          status: null,
                          taskId: null,
                          results: null,
                          error: null,
                          activeTab: 'setup',
                          showAdvancedSettings: false
                        });
                        setCryptoFileUploaded(null);
                        setPdfFileUploaded(null);
                      }}
                      className="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700"
                    >
                      Start New UAT Process
                    </button>
                  </div>
                </div>
              )}

              {/* Show processing message when pending/running */}
              {(state.status === 'pending' || state.status === 'running' || state.status === 'created') && (
                <div className="text-center text-blue-600">
                  <Clock className="w-16 h-16 mx-auto text-blue-300 mb-4" />
                  <p className="text-lg font-medium">Processing in progress...</p>
                  <p className="text-sm text-gray-600">Polling every 10 seconds for updates</p>
                </div>
              )}

              {/* Show default message when no status or results */}
              {!state.status && !state.results && (
                <div className="text-center text-gray-500">
                  <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                  <p>No results available. Start a UAT process to see results here.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PDFApiDocUATComponent; 