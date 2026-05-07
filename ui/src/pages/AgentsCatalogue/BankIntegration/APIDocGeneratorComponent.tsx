/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState, useEffect } from 'react'
import { 
  FileText, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Loader2, 
  Download
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

const APIDocGeneratorComponent: React.FC = () => {
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [documentFilePath, setDocumentFilePath] = useState<string>('')
  const [bankName, setBankName] = useState('')
  const [apisToFocus, setApisToFocus] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')
  
  const [isUploading, setIsUploading] = useState(false)
  const [isExecuting, setIsExecuting] = useState(false)
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

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type (accept PDF, TXT, DOCX)
    const allowedTypes = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    if (!allowedTypes.includes(file.type)) {
      setError('Please upload a PDF, TXT, or DOCX file')
      return
    }

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      setError('File size must be less than 50MB')
      return
    }

    setIsUploading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await apiClient.uploadFile(file, 'document')
      setDocumentFilePath(response.document_file_path || response.file_path || '')
      setDocumentFile(file)
      setSuccessMessage(`File "${file.name}" uploaded successfully`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setDocumentFile(null)
      setDocumentFilePath('')
    } finally {
      setIsUploading(false)
    }
  }



  const executeAgent = async () => {
    if (!documentFile || !bankName.trim()) {
      setError('Please upload a document and enter bank name')
      return
    }

    if (!documentFilePath) {
      setError('Document must be uploaded before processing')
      return
    }

    if (isUploading) {
      setError('Please wait for the file upload to complete')
      return
    }

    setIsExecuting(true)
    setError(null)
    setResult(null)

    try {
      const response = await apiClient.triggerAPIDocGenerator({
        document_file_path: documentFilePath,
        bank_name: bankName.trim(),
        apis_to_focus: apisToFocus.trim() || 'all APIs',
        custom_prompt: customPrompt.trim() || undefined
      })

      console.log('API Doc Generator task created:', response)
      setResult({
        task_id: response.task_id || '',
        status: response.status || 'queued',
        message: 'Task created successfully'
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
    const maxAttempts = 30 // 5 minutes at 10-second intervals
    
    const pollInterval = setInterval(async () => {
      pollAttempts++
      
      try {
        console.log(`Polling attempt ${pollAttempts} for API Doc Generator task ${taskId}`)
        
        const task = await apiClient.getTask(taskId)
        console.log(`API Doc Generator task status update - Attempt ${pollAttempts}:`, task)
        
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
          console.log('API Doc Generator task completed successfully')
          setIsExecuting(false)
          
          // Update with complete result data
          if (task.result) {
            setResult(prev => prev ? { ...prev, status: 'completed', message: 'Task completed successfully', workflow_result: task.result } : null)
          }
          
        } else if (task.status === 'failed') {
          clearInterval(pollInterval)
          console.log('API Doc Generator task failed:', task.result?.error)
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
          console.log(`API Doc Generator task status: ${task.status} - continuing to poll`)
        }
        
        // Stop polling if max attempts reached
        if (pollAttempts >= maxAttempts) {
          clearInterval(pollInterval)
          console.warn('API Doc Generator polling timeout reached')
          setIsExecuting(false)
          setError('Task is taking longer than expected - please check status manually')
        }
        
      } catch (error) {
        console.error('Error polling API Doc Generator task status:', error)
        
        if (pollAttempts >= maxAttempts) {
          clearInterval(pollInterval)
          setIsExecuting(false)
          setError('Network error while checking task status')
        }
      }
    }, 10000) // Poll every 10 seconds
  }

  const downloadFile = async (fileType: string) => {
    if (!result?.task_id) return

    try {
      const blob = await apiClient.downloadApiDocGeneratorFile(result.task_id, fileType)
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
    const IconComponent = config.icon

    return (
      <div className="flex items-center space-x-2">
        <Badge className={config.color}>
          <IconComponent className={`w-4 h-4 mr-1 ${status === 'running' ? 'animate-spin' : ''}`} />
          {config.text}
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
                <FileText className="w-5 h-5" />
                <span>API Documentation Generator</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  Upload Bank Specification Document *
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                  <input
                    type="file"
                    accept=".pdf,.txt,.docx"
                    onChange={handleFileUpload}
                    className="w-full"
                    disabled={isUploading || isExecuting}
                  />
                  <p className="text-sm text-gray-500 mt-2">
                    Supports PDF, TXT, and DOCX files (max 50MB)
                  </p>
                </div>
                {documentFile && (
                  <p className="text-sm text-green-600 mt-2 flex items-center">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    {documentFile.name} uploaded
                  </p>
                )}
              </div>

              {/* Bank Name */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  Bank Name *
                </label>
                <Input
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="e.g., Yes Bank, HDFC Bank"
                  disabled={isExecuting}
                />
              </div>

              {/* APIs to Focus */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  APIs to Focus On
                </label>
                <Input
                  value={apisToFocus}
                  onChange={(e) => setApisToFocus(e.target.value)}
                  placeholder="e.g., payment, transfer, balance inquiry (leave empty for all APIs)"
                  disabled={isExecuting}
                />
              </div>

              {/* Custom Instructions */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Custom Instructions (Optional)
                </label>
                <textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-foreground placeholder-muted-foreground bg-background"
                  rows={4}
                  placeholder="Provide specific instructions for documentation generation..."
                />
              </div>

              {/* Execute Button */}
              <Button 
                onClick={executeAgent} 
                disabled={isUploading || isExecuting || !documentFile || !bankName.trim()}
                className="w-full"
              >
                {isExecuting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating Documentation...
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4 mr-2" />
                    Generate API Documentation
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
                  {getStatusDisplay()}
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

                  {/* Success and Download Options */}
                  {result.status === 'completed' && (
                    <div className="space-y-4">
                      <Alert className="border-green-200 bg-green-50">
                        <CheckCircle className="h-4 w-4 text-green-600" />
                        <AlertDescription className="text-green-800">
                          Documentation generated successfully. Use the download buttons below to get the generated files.
                        </AlertDescription>
                      </Alert>

                      {/* Download Buttons */}
                      <div className="space-y-2">
                        <label className="block text-sm font-medium mb-2">Generated Files</label>
                        <div className="grid grid-cols-1 gap-2">
                          <Button 
                            onClick={() => downloadFile('api_documentation')}
                            size="sm"
                            variant="outline"
                            className="justify-start"
                          >
                            <Download className="w-4 h-4 mr-2" />
                            API Documentation
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
                <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Execute the agent to see results here</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

export default APIDocGeneratorComponent 