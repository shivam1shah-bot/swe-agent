/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState, useEffect } from 'react'
import { 
  AlertCircle, 
  CheckCircle, 
  Loader2,
  Download,
  Settings,
  Key,
  Clock,
  RefreshCw,
  Cog
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card'
import { Button } from '../../../components/ui/button'
import { Input } from '../../../components/ui/input'
import { Badge } from '../../../components/ui/badge'
import { Alert, AlertDescription } from '../../../components/ui/alert'
import { apiClient } from '../../../lib/api'

interface TaskResult {
  task_id?: string
  status: string
  message: string
  execution_time?: number
  files?: string[]
  agent_result?: any
  workflow_result?: any
  raw_task_response?: any
}

const BankUATAgentComponent: React.FC = () => {
  const [apiDocFile, setApiDocFile] = useState<File | null>(null)
  const [apiDocPath, setApiDocPath] = useState<string>('')
  const [bankName, setBankName] = useState<string>('')
  const [generateEncryptedCurls, setGenerateEncryptedCurls] = useState<boolean>(false)
  const [publicKeyFile, setPublicKeyFile] = useState<File | null>(null)
  const [privateKeyFile, setPrivateKeyFile] = useState<File | null>(null)
  const [publicKeyPath, setPublicKeyPath] = useState<string>('')
  const [privateKeyPath, setPrivateKeyPath] = useState<string>('')
  const [customPrompt, setCustomPrompt] = useState<string>('')
  
  // New fields for template-based workflow
  const [encryptionConfigFile, setEncryptionConfigFile] = useState<File | null>(null)
  const [encryptionTemplate, setEncryptionTemplate] = useState<string>('')
  const [bankPublicCertFile, setBankPublicCertFile] = useState<File | null>(null)
  const [bankPublicCertPath, setBankPublicCertPath] = useState<string>('')
  
  // Additional configuration parameters
  const [uatHost, setUatHost] = useState<string>('')
  const [encryptionType, setEncryptionType] = useState<string>('auto_detect')
  const [enableAiAnalysis, setEnableAiAnalysis] = useState<boolean>(true)
  const [aiConfidenceThreshold, setAiConfidenceThreshold] = useState<number>(0.6)
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(60)
  const [includeResponseAnalysis, setIncludeResponseAnalysis] = useState<boolean>(true)
  
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [isExecuting, setIsExecuting] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [result, setResult] = useState<TaskResult | null>(null)

  // Auto-fade success message after 10 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => {
        setSuccessMessage(null)
      }, 10000) // 10 seconds

      return () => clearTimeout(timer)
    }
  }, [successMessage])

  const handleApiDocUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      setError('File size must be less than 50MB')
      return
    }

    setIsUploading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await apiClient.uploadFile(file, 'bank_document')
      setApiDocPath(response.document_file_path || response.file_path || '')
      setApiDocFile(file)
      setSuccessMessage(`API documentation "${file.name}" uploaded successfully`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setApiDocFile(null)
      setApiDocPath('')
    } finally {
      setIsUploading(false)
    }
  }

  const handleKeyUpload = async (event: React.ChangeEvent<HTMLInputElement>, keyType: 'public' | 'private') => {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.size > 1 * 1024 * 1024) { // 1MB limit for keys
      setError('Key file size must be less than 1MB')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      const response = await apiClient.uploadFile(file, 'bank_crypto')
      if (keyType === 'public') {
        setPublicKeyPath(response.file_path || '')
        setPublicKeyFile(file)
        setSuccessMessage(`Public key "${file.name}" uploaded successfully`)
      } else {
        setPrivateKeyPath(response.file_path || '')
        setPrivateKeyFile(file)
        setSuccessMessage(`Private key "${file.name}" uploaded successfully`)
      }
      
      // Auto-enable encryption when keys are uploaded
      if (!generateEncryptedCurls) {
        setGenerateEncryptedCurls(true)
        setSuccessMessage(prev => prev ? `${prev} - Encryption automatically enabled` : 'Encryption automatically enabled')
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      if (keyType === 'public') {
        setPublicKeyFile(null)
        setPublicKeyPath('')
      } else {
        setPrivateKeyFile(null)
        setPrivateKeyPath('')
      }
    } finally {
      setIsUploading(false)
    }
  }

  const handleEncryptionConfigUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.size > 1 * 1024 * 1024) { // 1MB limit
      setError('Config file size must be less than 1MB')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      // Parse the JSON config to extract template
      const text = await file.text()
      const config = JSON.parse(text)
      
      // Set template if found in config
      if (config.template_name) {
        setEncryptionTemplate(config.template_name)
      }
      
      setEncryptionConfigFile(file)
      setSuccessMessage(`Encryption config "${file.name}" uploaded successfully`)
      
      if (config.template_name) {
        setSuccessMessage(prev => `${prev} - Template "${config.template_name}" auto-detected`)
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse config file - must be valid JSON')
      setEncryptionConfigFile(null)
      setEncryptionTemplate('')
    } finally {
      setIsUploading(false)
    }
  }

  const handleBankCertUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.size > 1 * 1024 * 1024) { // 1MB limit
      setError('Certificate file size must be less than 1MB')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      const response = await apiClient.uploadFile(file, 'bank_crypto')
      setBankPublicCertPath(response.file_path || '')
      setBankPublicCertFile(file)
      setSuccessMessage(`Bank certificate "${file.name}" uploaded successfully`)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setBankPublicCertFile(null)
      setBankPublicCertPath('')
    } finally {
      setIsUploading(false)
    }
  }

  const executeAgent = async () => {
    if (!apiDocFile || !bankName.trim()) {
      setError('Please upload API documentation and enter bank name')
      return
    }

    if (!apiDocPath) {
      setError('API documentation must be uploaded before processing')
      return
    }

    if (isUploading) {
      setError('Please wait for file uploads to complete')
      return
    }

    setIsExecuting(true)
    setError(null)
    setResult(null)

    try {
      const response = await apiClient.triggerBankUATAgent({
        api_doc_path: apiDocPath,
        bank_name: bankName.trim(),
        uat_host: uatHost.trim() || undefined,
        
        // Encryption Configuration - Updated to use three-certificate structure
        generate_encrypted_curls: generateEncryptedCurls,
        bank_public_cert_path: bankPublicCertPath || undefined,  // Bank's public certificate for encrypting requests TO bank
        private_key_path: privateKeyPath || undefined,           // Partner's private key for decrypting responses FROM bank
        partner_public_key_path: publicKeyPath || undefined,     // Partner's public key for bank to encrypt responses TO partner
        encryption_type: encryptionType,
        encryption_template: encryptionTemplate || undefined,
        
        // AI Configuration  
        enable_ai_analysis: enableAiAnalysis,
        ai_confidence_threshold: aiConfidenceThreshold,
        
        // Additional Parameters
        timeout_seconds: timeoutSeconds,
        include_response_analysis: includeResponseAnalysis,
        custom_prompt: customPrompt.trim() || undefined
      })

      console.log('Bank UAT Agent task created:', response)
      setResult({
        task_id: response.task_id || '',
        status: response.status || 'queued',
        message: response.message || 'Task created successfully'
      })

      // Start polling for status updates if we have a task_id
      if (response.task_id) {
        console.log('Starting status polling for task:', response.task_id)
        pollTaskStatus(response.task_id)
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
      setIsExecuting(false)
    }
  }

  // Poll for task status updates
  const pollTaskStatus = async (taskId: string) => {
    let pollAttempts = 0
    const maxAttempts = 60 // 10 minutes at 10-second intervals
    
    const pollInterval = setInterval(async () => {
      pollAttempts++
      
      try {
        console.log(`Polling attempt ${pollAttempts} for Bank UAT Agent task ${taskId}`)
        
        const task = await apiClient.getTask(taskId)
        console.log(`Bank UAT Agent task status update - Attempt ${pollAttempts}:`, task)
        
        // Extract error information from various possible locations in the response
        const latestMessage = task.result?.message || task.result?.error || 
                              (task.status === 'failed' ? 'Task failed without specific error details' : result?.message)
        
        // Update result with new status and message
        setResult(prev => {
          const currentMessage = latestMessage || prev?.message
          console.log(`Message update: "${prev?.message}" -> "${currentMessage}"`)
          
          return prev ? { 
            ...prev, 
            status: task.status, 
            message: currentMessage,
            // Also update the raw task data for debugging
            raw_task_response: task
          } : null
        })

        if (task.status === 'completed') {
          clearInterval(pollInterval)
          console.log('Bank UAT Agent task completed successfully')
          setIsExecuting(false)
          
          // Update with complete result data
          if (task.result) {
            // For bank UAT agent, check nested result for actual service status
            const serviceResult = task.result.result
            const actualStatus = serviceResult?.status || task.result.status || 'completed'
            const actualMessage = serviceResult?.message || task.result.message || 'Task completed successfully'
            
            setResult(prev => prev ? { 
              ...prev, 
              status: actualStatus, 
              message: actualMessage, 
              workflow_result: task.result 
            } : null)
          }
          
        } else if (task.status === 'failed') {
          clearInterval(pollInterval)
          console.log('Bank UAT Agent task failed:', task.result?.error)
          setIsExecuting(false)
          
          // Get the actual error message from the task response
          const errorMessage = task.result?.error || task.result?.message || 'Task failed without specific details'
          console.log('Setting error message:', errorMessage)
          setError(errorMessage)
          
          // Update result with proper failure information
          setResult(prev => prev ? { 
            ...prev, 
            status: 'failed', 
            message: errorMessage 
          } : null)
          
        } else if (['pending', 'running', 'created'].includes(task.status)) {
          // Clear any previous error when task is still processing
          if (error) {
            console.log('Clearing error as task is still processing')
            setError(null)
          }
          // Keep polling for these statuses
          console.log(`Bank UAT Agent task status: ${task.status} - continuing to poll`)
        }
        
        // Stop polling if max attempts reached
        if (pollAttempts >= maxAttempts) {
          clearInterval(pollInterval)
          console.warn('Bank UAT Agent polling timeout reached')
          setIsExecuting(false)
          setError('Task is taking longer than expected (10 minutes) - please check status manually or use the Refresh Status button')
        }
        
      } catch (error) {
        console.error('Error polling Bank UAT Agent task status:', error)
        
        if (pollAttempts >= maxAttempts) {
          clearInterval(pollInterval)
          setIsExecuting(false)
          setError('Network error while checking task status')
        }
      }
    }, 10000) // Poll every 10 seconds
  }

  // Manual refresh of task status (without starting polling)
  const refreshTaskStatus = async () => {
    if (!result?.task_id) return

    try {
      console.log('Manually refreshing task status for:', result.task_id)
      const task = await apiClient.getTask(result.task_id)
      console.log('Manual status refresh result:', task)
      
      // Extract error information from various possible locations in the response
      const latestMessage = task.result?.message || task.result?.error || 
                            (task.status === 'failed' ? 'Task failed without specific error details' : result?.message)
      
      // Update result with new status and message
      setResult(prev => {
        const currentMessage = latestMessage || prev?.message
        console.log(`Manual refresh - Message update: "${prev?.message}" -> "${currentMessage}"`)
        
        return prev ? { 
          ...prev, 
          status: task.status, 
          message: currentMessage,
          // Also update the raw task data for debugging
          raw_task_response: task
        } : null
      })

      if (task.status === 'completed') {
        console.log('Bank UAT Agent task completed successfully (manual refresh)')
        setIsExecuting(false)
        
        // Update with complete result data
        if (task.result) {
          setResult(prev => prev ? { ...prev, status: 'completed', message: 'Task completed successfully', workflow_result: task.result } : null)
        }
        
      } else if (task.status === 'failed') {
        console.log('Bank UAT Agent task failed (manual refresh):', task.result?.error)
        setIsExecuting(false)
        
        // Get the actual error message from the task response
        const errorMessage = task.result?.error || task.result?.message || 'Task failed without specific details'
        console.log('Setting error message (manual refresh):', errorMessage)
        setError(errorMessage)
        
        // Update result with proper failure information
        setResult(prev => prev ? { 
          ...prev, 
          status: 'failed', 
          message: errorMessage 
        } : null)
        
      } else if (['pending', 'running', 'created'].includes(task.status)) {
        // Clear any previous error when task is still processing
        if (error) {
          console.log('Clearing error as task is still processing (manual refresh)')
          setError(null)
        }
        console.log(`Bank UAT Agent task status (manual refresh): ${task.status}`)
      }
      
      setSuccessMessage('Task status refreshed successfully')
      
    } catch (error) {
      console.error('Error manually refreshing task status:', error)
      setError(`Failed to refresh status: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  const downloadFile = async (fileType: string) => {
    if (!result?.task_id) return

    try {
      const blob = await apiClient.downloadBankUATAgentFile(result.task_id, fileType)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `${bankName}_${fileType}_${new Date().toISOString().split('T')[0]}.txt`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      setSuccessMessage(`Successfully downloaded ${fileType}`)
    } catch (error) {
      console.error('Download failed:', error)
      setError(`Download failed: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  const downloadGeneratedConfig = () => {
    // The structure is: result.workflow_result.result.result.configuration (3 levels deep!)
    if (!result?.workflow_result?.result?.result?.configuration) {
      setError('No configuration available for download')
      return
    }

    try {
      const configData = result.workflow_result.result.result.configuration
      const filename = result.workflow_result.result.result.download_instructions?.filename || `${bankName}_encryption_config.json`
      
      const blob = new Blob([JSON.stringify(configData, null, 2)], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      setSuccessMessage('Encryption configuration downloaded successfully')
    } catch (error) {
      console.error('Config download failed:', error)
      setError(`Config download failed: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  const getStatusDisplay = () => {
    if (!result) return null

    const { status } = result
    
    const statusConfig = {
      created: { color: 'bg-blue-100 text-blue-800', icon: Clock, text: 'Created' },
      pending: { color: 'bg-blue-100 text-blue-800', icon: Clock, text: 'Pending' },
      running: { color: 'bg-yellow-100 text-yellow-800', icon: Loader2, text: 'Running' },
      completed: { color: 'bg-green-100 text-green-800', icon: CheckCircle, text: 'Completed' },
      failed: { color: 'bg-red-100 text-red-800', icon: AlertCircle, text: 'Failed' }
    }

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending

    // Check if this is a config generation completion
    const isConfigGeneration = status === 'completed' && result.workflow_result?.result?.result?.workflow_type === 'config_generation'
    const displayText = isConfigGeneration ? 'Config Generated' : config.text
    const displayColor = isConfigGeneration ? 'bg-blue-100 text-blue-800' : config.color
    const DisplayIcon = isConfigGeneration ? Settings : config.icon

    return (
      <div className="flex items-center space-x-2">
        <Badge className={displayColor}>
          <DisplayIcon className={`w-4 h-4 mr-1 ${status === 'running' ? 'animate-spin' : ''}`} />
          {displayText}
        </Badge>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column - Input */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Settings className="w-5 h-5" />
                <span>Bank UAT Agent</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* API Documentation Upload */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  Upload API Documentation *
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                  <input
                    type="file"
                    accept=".pdf,.txt,.docx,.md"
                    onChange={handleApiDocUpload}
                    className="w-full"
                    disabled={isUploading || isExecuting}
                  />
                  <p className="text-sm text-gray-500 mt-2">
                    API documentation file to test against
                  </p>
                </div>
                {apiDocFile && (
                  <p className="text-sm text-green-600 mt-2 flex items-center">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    {apiDocFile.name} uploaded
                  </p>
                )}
              </div>

              {/* Bank Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Bank Name *
                </label>
                <Input
                  type="text"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="e.g., Yes Bank, HDFC, ICICI"
                  className="w-full"
                  disabled={isExecuting}
                  required
                />
              </div>

              {/* Generate Encrypted Curls Toggle */}
              <div>
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium">
                      Generate Encrypted Curl Commands
                    </label>
                    <p className="text-sm text-gray-500 mt-1">
                      {generateEncryptedCurls 
                        ? "Encryption enabled - with template & keys: full execution | without: AI config generation"
                        : "Disabled - will generate AI encryption config for download"
                      }
                      {(publicKeyFile || privateKeyFile || bankPublicCertFile) && !generateEncryptedCurls && (
                        <span className="block text-blue-600 mt-1">
                          ⚠️ Keys uploaded - encryption will be automatically enabled
                        </span>
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setGenerateEncryptedCurls(!generateEncryptedCurls)}
                    disabled={isExecuting}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                      generateEncryptedCurls ? 'bg-blue-600' : 'bg-gray-200'
                    } ${isExecuting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        generateEncryptedCurls ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>



              {/* Encryption Configuration */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Settings className="w-4 h-4" />
                  <span className="text-sm font-medium">Encryption Configuration</span>
                </div>
                
                {/* 2 Column Layout */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Encryption Config Upload */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Encryption Config File (Optional)
                    </label>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                      <input
                        type="file"
                        accept=".json,.config"
                        onChange={handleEncryptionConfigUpload}
                        className="w-full"
                        disabled={isUploading || isExecuting}
                      />
                      <p className="text-sm text-gray-500 mt-2">
                        Previously generated encryption configuration (JSON format)
                      </p>
                    </div>
                    {encryptionConfigFile && (
                      <p className="text-sm text-green-600 mt-2 flex items-center">
                        <CheckCircle className="w-4 h-4 mr-1" />
                        {encryptionConfigFile.name} uploaded
                        {encryptionTemplate && (
                          <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                            Template: {encryptionTemplate}
                          </span>
                        )}
                      </p>
                    )}
                  </div>

                  {/* Template Selection */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Encryption Template (Optional)
                    </label>
                    <select
                      value={encryptionTemplate}
                      onChange={(e) => setEncryptionTemplate(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                      disabled={isExecuting}
                    >
                      <option value="" className="text-gray-500">Select template...</option>
                      <option value="no_encryption" className="text-gray-700">No Encryption</option>
                      <option value="rsa_aes_headers" className="text-gray-700">RSA + AES (Headers)</option>
                      <option value="rsa_aes_body" className="text-gray-700">RSA + AES (Body)</option>
                      <option value="rsa_aes_mixed" className="text-gray-700">RSA + AES (Mixed)</option>
                      <option value="signature_only" className="text-gray-700">Signature Only</option>
                    </select>
                    <p className="text-sm text-gray-500 mt-1">
                      Pre-defined encryption pattern to use
                    </p>
                  </div>
                </div>
              </div>

              {/* Encryption Keys */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Key className="w-4 h-4" />
                  <span className="text-sm font-medium">Encryption Keys (Optional)</span>
                </div>
                
                {/* Info Box explaining the three-certificate structure */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start space-x-2">
                    <AlertCircle className="w-4 h-4 text-blue-600 mt-0.5" />
                    <div className="text-sm text-blue-800">
                      <p className="font-medium mb-1">Three-Certificate Encryption Structure:</p>
                      <ul className="list-disc list-inside space-y-1 text-xs">
                        <li><strong>Bank Public Certificate:</strong> Encrypts requests sent TO the bank</li>
                        <li><strong>Partner Public Key:</strong> Bank uses this to encrypt responses TO you</li>
                        <li><strong>Partner Private Key:</strong> You use this to decrypt responses FROM the bank</li>
                      </ul>
                    </div>
                  </div>
                </div>
                
                {/* Bank Public Certificate */}
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Bank Public Certificate
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                    <input
                      type="file"
                      accept=".pem,.crt,.cer,.cert"
                      onChange={handleBankCertUpload}
                      className="w-full"
                      disabled={isUploading || isExecuting}
                    />
                    <p className="text-sm text-gray-500 mt-2">
                      Bank's public certificate for encrypting requests TO the bank (PEM, CRT, CER)
                    </p>
                  </div>
                  {bankPublicCertFile && (
                    <p className="text-sm text-green-600 mt-2 flex items-center">
                      <CheckCircle className="w-4 h-4 mr-1" />
                      {bankPublicCertFile.name} uploaded
                    </p>
                  )}
                </div>
                
                {/* Key Files Side by Side */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Partner Public Key */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Partner Public Key
                    </label>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                      <input
                        type="file"
                        accept=".pem,.key,.pub,.crt"
                        onChange={(e) => handleKeyUpload(e, 'public')}
                        className="w-full"
                        disabled={isUploading || isExecuting}
                      />
                      <p className="text-sm text-gray-500 mt-2">
                        Your organization's public key for bank to encrypt responses TO you (PEM, KEY, PUB)
                      </p>
                    </div>
                    {publicKeyFile && (
                      <p className="text-sm text-green-600 mt-2 flex items-center">
                        <CheckCircle className="w-4 h-4 mr-1" />
                        {publicKeyFile.name} uploaded
                      </p>
                    )}
                  </div>

                  {/* Partner Private Key */}
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Partner Private Key
                    </label>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                      <input
                        type="file"
                        accept=".pem,.key,.prv"
                        onChange={(e) => handleKeyUpload(e, 'private')}
                        className="w-full"
                        disabled={isUploading || isExecuting}
                      />
                      <p className="text-sm text-gray-500 mt-2">
                        Your organization's private key for decrypting responses FROM the bank (PEM, KEY, PRV)
                      </p>
                    </div>
                    {privateKeyFile && (
                      <p className="text-sm text-green-600 mt-2 flex items-center">
                        <CheckCircle className="w-4 h-4 mr-1" />
                        {privateKeyFile.name} uploaded
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Custom Prompt */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Custom Test Instructions (Optional)
                </label>
                <textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Additional instructions for UAT testing..."
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-foreground placeholder-muted-foreground bg-background"
                  disabled={isExecuting}
                />
              </div>

              {/* Advanced Settings */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Cog className="w-4 h-4" />
                  <span className="text-sm font-medium">Advanced Settings</span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* UAT Host Override */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      UAT Host Override (Optional)
                    </label>
                    <input
                      type="text"
                      value={uatHost}
                      onChange={(e) => setUatHost(e.target.value)}
                      placeholder="https://uat.bank.com"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-foreground placeholder-muted-foreground bg-background"
                      disabled={isExecuting}
                    />
                  </div>

                  {/* Encryption Type */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Encryption Type
                    </label>
                    <select
                      value={encryptionType}
                      onChange={(e) => setEncryptionType(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                      disabled={isExecuting}
                    >
                      <option value="auto_detect">Auto Detect</option>
                      <option value="hybrid">Hybrid (RSA + AES)</option>
                      <option value="none">No Encryption</option>
                    </select>
                  </div>

                  {/* Timeout */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Timeout (seconds)
                    </label>
                    <input
                      type="number"
                      value={timeoutSeconds}
                      onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                      min="10"
                      max="300"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-foreground placeholder-muted-foreground bg-background"
                      disabled={isExecuting}
                    />
                  </div>

                  {/* AI Confidence Threshold */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      AI Confidence Threshold
                    </label>
                    <input
                      type="number"
                      value={aiConfidenceThreshold}
                      onChange={(e) => setAiConfidenceThreshold(Number(e.target.value))}
                      min="0.0"
                      max="1.0"
                      step="0.1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-foreground placeholder-muted-foreground bg-background"
                      disabled={isExecuting}
                    />
                  </div>
                </div>

                {/* Checkboxes */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="enableAiAnalysis"
                      checked={enableAiAnalysis}
                      onChange={(e) => setEnableAiAnalysis(e.target.checked)}
                      className="rounded"
                      disabled={isExecuting}
                    />
                    <label htmlFor="enableAiAnalysis" className="text-sm font-medium text-gray-700">
                      Enable AI Analysis
                    </label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="includeResponseAnalysis"
                      checked={includeResponseAnalysis}
                      onChange={(e) => setIncludeResponseAnalysis(e.target.checked)}
                      className="rounded"
                      disabled={isExecuting}
                    />
                    <label htmlFor="includeResponseAnalysis" className="text-sm font-medium text-gray-700">
                      Include Response Analysis
                    </label>
                  </div>
                </div>
              </div>

              {/* Execute Button */}
              <Button 
                onClick={executeAgent} 
                disabled={isUploading || isExecuting || !apiDocFile || !bankName.trim()}
                className="w-full"
              >
                {isExecuting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Running UAT Tests...
                  </>
                ) : (
                  <>
                    <Settings className="w-4 h-4 mr-2" />
                    Execute UAT Testing
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Output */}
        <div className="space-y-6">
          {/* Success Message - Now in right column */}
          {successMessage && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {successMessage}
              </AlertDescription>
            </Alert>
          )}

          {/* Error Messages - Now in right column */}
          {error && (
            <Alert className="border-red-200 bg-red-50">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {error}
              </AlertDescription>
            </Alert>
          )}

          {/* Status Display */}
          {result && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Execution Results</span>
                  <div className="flex items-center space-x-2">
                    {getStatusDisplay()}
                    <Button
                      onClick={refreshTaskStatus}
                      size="sm"
                      variant="outline"
                      disabled={!result.task_id}
                      className="ml-2"
                    >
                      <RefreshCw className="w-4 h-4 mr-1" />
                      Refresh Status
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Task ID */}
                  {result.task_id && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Task ID</label>
                      <p className="text-sm font-mono bg-gray-100 p-2 rounded">
                        {result.task_id}
                      </p>
                    </div>
                  )}

                  {/* Message */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Message</label>
                    <p className="text-sm text-gray-900">{result.message}</p>
                  </div>

                  {/* Status-specific content */}
                  {(result.status === 'created' || result.status === 'pending' || result.status === 'running') && (
                    <Alert>
                      <Clock className="h-4 w-4" />
                      <AlertDescription>
                        Task is currently {result.status}. Status updates every 10 seconds. 
                        <br />
                        <span className="text-sm text-gray-600">
                          Auto-refresh will continue for up to 10 minutes. Use the Refresh Status button above for manual updates.
                        </span>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Error Message */}
                  {result.status === 'failed' && (
                    <Alert className="border-red-200 bg-red-50">
                      <AlertCircle className="h-4 w-4 text-red-600" />
                      <AlertDescription className="text-red-800">
                        Task Failed: {result.message}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Config Generation Results */}
                  {result.status === 'completed' && result.workflow_result?.result?.result?.workflow_type === 'config_generation' && (
                    <div className="space-y-4">
                      <Alert className="border-blue-200 bg-blue-50">
                        <Settings className="h-4 w-4 text-blue-600" />
                        <AlertDescription className="text-blue-800">
                          Encryption configuration generated successfully. Download the config and use it for future UAT executions.
                        </AlertDescription>
                      </Alert>

                      {/* Configuration Details */}
                      {result.workflow_result?.result?.result?.configuration && (
                        <div className="bg-gray-50 p-4 rounded-lg">
                          <h4 className="text-sm font-medium mb-2">Generated Configuration</h4>
                          <div className="text-sm space-y-1">
                            <div><strong>Template:</strong> {result.workflow_result.result.result.configuration.template_name || 'Custom'}</div>
                            <div><strong>Encryption Type:</strong> {result.workflow_result.result.result.configuration.encryption_type}</div>
                            <div><strong>Placement:</strong> {result.workflow_result.result.result.configuration.placement_strategy || 'Not specified'}</div>
                            <div><strong>AI Confidence:</strong> {result.workflow_result.result.result.configuration.ai_metadata?.confidence_score ? (result.workflow_result.result.result.configuration.ai_metadata.confidence_score * 100).toFixed(1) + '%' : 'N/A'}</div>
                          </div>
                        </div>
                      )}

                      {/* Usage Instructions */}
                      {result.workflow_result?.result?.result?.configuration?.usage_instructions && (
                        <div className="bg-blue-50 p-4 rounded-lg">
                          <h4 className="text-sm font-medium mb-2 text-blue-800">Usage Instructions</h4>
                          <div className="text-sm space-y-1 text-blue-700">
                            <div><strong>Template Parameter:</strong> {result.workflow_result.result.result.configuration.usage_instructions.template_parameter}</div>
                            <div><strong>Required Keys:</strong> {result.workflow_result.result.result.configuration.usage_instructions.required_keys?.join(', ') || 'None'}</div>
                            <div><strong>Encryption Flag:</strong> {result.workflow_result.result.result.configuration.usage_instructions.encryption_flag}</div>
                          </div>
                        </div>
                      )}

                      {/* Download Config Button */}
                      <div className="space-y-2">
                        <Button 
                          onClick={() => downloadGeneratedConfig()}
                          size="sm"
                          className="w-full justify-center bg-blue-600 hover:bg-blue-700 text-white"
                        >
                          <Download className="w-4 h-4 mr-2" />
                          Download Encryption Configuration
                        </Button>
                        
                        {/* Next Steps */}
                        {result.workflow_result?.result?.result?.next_steps && (
                          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                            <h4 className="text-sm font-medium text-yellow-800 mb-2">Next Steps:</h4>
                            <ul className="text-sm text-yellow-700 list-disc list-inside space-y-1">
                              {result.workflow_result.result.result.next_steps.map((step: string, index: number) => (
                                <li key={index}>{step}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Success and Download Options */}
                  {result.status === 'completed' && (
                    <div className="space-y-4">
                      <Alert className="border-green-200 bg-green-50">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        <AlertDescription className="text-green-800">
                          UAT testing completed successfully. Use the download buttons below to get the generated files.
                        </AlertDescription>
                      </Alert>

                      {/* AI Analysis Results */}
                      {result.workflow_result?.ai_analysis_results && (
                        <div className="bg-gray-50 p-4 rounded-lg">
                          <h4 className="text-sm font-medium mb-2">AI Analysis Results</h4>
                          <div className="text-sm space-y-1">
                            <div><strong>Analysis Performed:</strong> {result.workflow_result.ai_analysis_results.analysis_performed ? 'Yes' : 'No'}</div>
                            {result.workflow_result.ai_analysis_results.confidence_score && (
                              <div><strong>Confidence Score:</strong> {(result.workflow_result.ai_analysis_results.confidence_score * 100).toFixed(1)}%</div>
                            )}
                            {result.workflow_result.ai_analysis_results.detected_patterns && (
                              <div><strong>Detected Patterns:</strong> {result.workflow_result.ai_analysis_results.detected_patterns.join(', ')}</div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Download Buttons */}
                      <div className="space-y-2">
                        <label className="block text-sm font-medium mb-2">Generated Files</label>
                        <div className="grid grid-cols-1 gap-2">
                          <Button 
                            onClick={() => downloadFile('uat_results')}
                            size="sm"
                            variant="outline"
                            className="justify-start"
                          >
                            <Download className="w-4 h-4 mr-2" />
                            UAT Results
                          </Button>
                          <Button 
                            onClick={() => downloadFile('curl_commands')}
                            size="sm"
                            variant="outline"
                            className="justify-start"
                          >
                            <Download className="w-4 h-4 mr-2" />
                            CURL Commands
                          </Button>
                          <Button 
                            onClick={() => downloadFile('test_report')}
                            size="sm"
                            variant="outline"
                            className="justify-start"
                          >
                            <Download className="w-4 h-4 mr-2" />
                            Test Report
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Raw Output (for debugging) */}
                  {result.raw_task_response && (
                    <details className="mt-4">
                      <summary className="cursor-pointer text-sm font-medium text-gray-600">
                        View Raw Output Data
                      </summary>
                      <pre className="mt-2 text-xs bg-gray-100 p-3 rounded overflow-auto max-h-48">
                        {JSON.stringify(result.raw_task_response, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* No Results Placeholder */}
          {!result && (
            <Card>
              <CardContent className="p-8 text-center text-gray-500">
                <Settings className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Execute the agent to see UAT results here</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

export default BankUATAgentComponent 