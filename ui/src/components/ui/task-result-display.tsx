/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState } from 'react'
import {
  CheckCircle2,
  AlertCircle,
  FileText,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Zap,
  Clock
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './card'
import { Badge } from './badge'
import { Button } from './button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'
import { Alert, AlertDescription } from './alert'

interface TaskResult {
  status: string
  message: string
  execution_time?: number
  files?: Array<{
    name: string
    path: string
    size?: number
    content?: string
  }>
  pr_url?: string
  metadata?: Record<string, any>
  agent_result?: Record<string, any>
  errors?: string[]
  warnings?: string[]
}

interface TaskResultDisplayProps {
  result: TaskResult | null
  showRawData?: boolean
  createdAt?: string
  updatedAt?: string
  taskStatus?: string
}

const ResultStatusBanner: React.FC<{ status: string; message: string }> = ({ status, message }) => {
  const normalizedStatus = status?.toLowerCase() || 'unknown'
  const isSuccess = normalizedStatus === 'completed' || normalizedStatus === 'success'
  const isError = normalizedStatus === 'failed' || normalizedStatus === 'error'
  
  return (
    <Alert className={`${isSuccess ? 'border-green-200 bg-green-50' : isError ? 'border-red-200 bg-red-50' : 'border-blue-200 bg-blue-50'} w-full`}>
      <div className="flex items-start gap-3">
        {isSuccess ? (
          <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
        ) : isError ? (
          <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
        ) : (
          <Clock className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
        )}
        <AlertDescription className={`font-medium ${isSuccess ? 'text-green-800' : isError ? 'text-red-800' : 'text-blue-800'} break-words`}> 
          {message}
        </AlertDescription>
      </div>
    </Alert>
  )
}

const ExecutionSummary: React.FC<{ 
  result: TaskResult
  createdAt?: string
  updatedAt?: string 
  taskStatus?: string
}> = ({ result, createdAt, taskStatus }) => {
  const calculateExecutionTime = () => {
    try {
      const completedAt = result.metadata?.completed_at
      
      if (createdAt && completedAt) {
        const created = new Date(createdAt).getTime()
        const completed = new Date(completedAt).getTime()
        const diffSec = (completed - created) / 1000
        
        if (diffSec < 60) {
          return `${diffSec.toFixed(1)}s`
        } else if (diffSec < 3600) {
          const minutes = Math.floor(diffSec / 60)
          const seconds = Math.floor(diffSec % 60)
          return `${minutes}m ${seconds}s`
        } else {
          const hours = Math.floor(diffSec / 3600)
          const minutes = Math.floor((diffSec % 3600) / 60)
          return `${hours}h ${minutes}m`
        }
      }
    } catch (e) {
      console.error('Error calculating execution time:', e)
    }
    
    return 'N/A'
  }

  const executionTime = calculateExecutionTime()
  const resolvedStatus = taskStatus || result.status
  const statusValue = resolvedStatus
    ? resolvedStatus.charAt(0).toUpperCase() + resolvedStatus.slice(1)
    : 'Unknown'

  return (
    <div className="grid w-full grid-cols-1 gap-4 my-6 md:grid-cols-2">
      <Card className="w-full">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <Zap className="h-5 w-5 text-gray-600 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm text-gray-600">Status</p>
              <p className="text-lg font-semibold truncate">{statusValue}</p>
            </div>
          </div>
        </CardContent>
      </Card>
      
      <Card className="w-full">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-gray-600 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm text-gray-600">Execution Time</p>
              <p className="text-lg font-semibold truncate">{executionTime}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

const FilesSection: React.FC<{ 
  files: Array<{ name: string; path: string; size?: number; content?: string }>
  taskResult?: any
}> = ({ files, taskResult }) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [expandedFiles, setExpandedFiles] = useState<Set<number>>(new Set())

  const getFileContent = (file: any): string => {
    // If file already has content, use it
    if (file.content) {
      return file.content
    }

    // For markdown files, try to extract content from task result
    if (file.name.endsWith('.md') && taskResult?.agent_result?.spec_data?.sections) {
      const sections = taskResult.agent_result.spec_data.sections
      const title = taskResult.agent_result.spec_data.title || 'Technical Specification'
      
      let markdownContent = `# ${title}\n\n`
      
      sections.forEach((section: any) => {
        if (section.title && section.content) {
          markdownContent += `## ${section.title}\n\n${section.content}\n\n`
        }
      })
      
      return markdownContent
    }

    return 'No content available'
  }

  const convertToHtml = (markdownContent: string): string => {
    // First, handle lists properly
    const html = markdownContent
      // Convert bullet points and numbered lists
      .replace(/^(\* |- |\d+\. )(.*$)/gm, '<li>$2</li>')
      // Wrap consecutive list items in ul tags
      .replace(/(<li>.*<\/li>\n?)+/g, (match) => {
        return '<ul>' + match.replace(/\n/g, '') + '</ul>'
      })
      // Convert headings
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^#### (.*$)/gm, '<h4>$1</h4>')
      // Convert bold and italic
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Convert code
      .replace(/`(.*?)`/g, '<code>$1</code>')
      // Convert line breaks to paragraphs
      .replace(/\n\n/g, '</p><p>')
      // Wrap remaining lines in paragraphs
      .replace(/^(.+)$/gm, '<p>$1</p>')
      // Clean up paragraph tags around headings and lists
      .replace(/<p><h([1-6])>/g, '<h$1>')
      .replace(/<\/h([1-6])><\/p>/g, '</h$1>')
      .replace(/<p><ul>/g, '<ul>')
      .replace(/<\/ul><\/p>/g, '</ul>')
      .replace(/<p><li>/g, '<li>')
      .replace(/<\/li><\/p>/g, '</li>')
      // Remove empty paragraphs
      .replace(/<p><\/p>/g, '')
      // Clean up multiple consecutive ul tags
      .replace(/<\/ul>\s*<ul>/g, '')
    
    return html
  }

  const copyToClipboard = async (content: string, index: number) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch (_err) {
      console.error('Failed to copy:', _err)
    }
  }

  const copyForGoogleDocs = async (file: any, index: number) => {
    const content = getFileContent(file)
    if (content === 'No content available') return

    // Create a temporary div to convert HTML to formatted text
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = convertToHtml(content)
    
    // Create a rich text format that Google Docs can understand
    const richText = tempDiv.innerText
    
    // Try to copy as rich text first, fallback to plain text
    try {
      // Create a blob with HTML content
      const blob = new Blob([convertToHtml(content)], { type: 'text/html' })
      const clipboardItem = new ClipboardItem({ 'text/html': blob, 'text/plain': new Blob([richText], { type: 'text/plain' }) })
      await navigator.clipboard.write([clipboardItem])
    } catch (_err) {
      // Fallback to plain text
      await navigator.clipboard.writeText(richText)
    }
    
    setCopiedIndex(index)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  // Check if this is a genspec task
  const isGenSpecTask = (file: any): boolean => {
    return file.name.endsWith('.md') && taskResult?.agent_result?.spec_data?.sections !== undefined
  }

  const toggleFileExpansion = (index: number) => {
    const newExpanded = new Set(expandedFiles)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedFiles(newExpanded)
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold flex items-center space-x-2">
        <FileText className="h-5 w-5 flex-shrink-0" />
        <span>Generated Files ({files.length})</span>
      </h3>
      
      <div className="space-y-3">
        {files.map((file, index) => (
          <Card key={index}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center space-x-3 min-w-0 flex-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleFileExpansion(index)}
                    className="h-6 w-6 p-0 flex-shrink-0"
                  >
                    {expandedFiles.has(index) ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </Button>
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-sm truncate">{file.name}</CardTitle>
                    <p className="text-xs text-gray-500 truncate">{file.path}</p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2 flex-shrink-0">
                  {file.size && (
                    <Badge variant="outline" className="text-xs">
                      {(file.size / 1024).toFixed(1)} KB
                    </Badge>
                  )}
                  {isGenSpecTask(file) && getFileContent(file) !== 'No content available' ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyForGoogleDocs(file, index)}
                      className="h-6 w-6 p-0"
                      title="Copy for Google Docs"
                    >
                      {copiedIndex === index ? (
                        <Check className="h-3 w-3 text-green-500" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  ) : file.content ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(file.content!, index)}
                      className="h-6 w-6 p-0"
                    >
                      {copiedIndex === index ? (
                        <Check className="h-3 w-3 text-green-500" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  ) : null}
                </div>
              </div>
            </CardHeader>
            
            {expandedFiles.has(index) && (isGenSpecTask(file) ? getFileContent(file) !== 'No content available' : file.content) && (
              <CardContent>
                <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-auto">
                  <pre className="text-xs font-mono whitespace-pre-wrap break-words">
                    {isGenSpecTask(file) ? getFileContent(file) : file.content}
                  </pre>
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}

export const TaskResultDisplay: React.FC<TaskResultDisplayProps> = ({
  result,
  showRawData = false,
  createdAt,
  updatedAt,
  taskStatus
}) => {
  if (!result) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Result Available</h3>
          <p className="text-gray-600">This task hasn't produced any results yet.</p>
        </CardContent>
      </Card>
    )
  }

  // Handle nested result structure from agents catalogue
  const actualResult = (result as any).result || result

  return (
    <div className="flex flex-col w-full gap-4">
      <ResultStatusBanner 
        status={taskStatus || actualResult.status || result.status || 'unknown'} 
        message={actualResult.message || result.message || 'No message available'} 
      />
      
      <ExecutionSummary 
        result={actualResult} 
        createdAt={createdAt} 
        updatedAt={updatedAt} 
        taskStatus={taskStatus || actualResult.status || result.status}
      />
      
      <Tabs defaultValue="overview" className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          {actualResult.files && actualResult.files.length > 0 && (
            <TabsTrigger value="files">Files ({actualResult.files.length})</TabsTrigger>
          )}
          {showRawData && (
            <TabsTrigger value="raw">Raw Data</TabsTrigger>
          )}
        </TabsList>
        
        <TabsContent value="overview" className="flex flex-col w-full gap-4 mt-4">
          {actualResult.agent_result?.result?.content && (
            <Card className="w-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <FileText className="h-5 w-5 flex-shrink-0" />
                  <span>Agent Result</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="p-6 bg-gray-50 rounded-lg">
                  <pre className="w-full text-sm font-mono whitespace-pre-wrap break-words">
                    {actualResult.agent_result.result.content}
                  </pre>
                </div>
              </CardContent>
            </Card>
          )}
          
          {actualResult.errors && actualResult.errors.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg text-red-600 flex items-center space-x-2">
                  <AlertCircle className="h-5 w-5 flex-shrink-0" />
                  <span>Errors ({actualResult.errors.length})</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {actualResult.errors.map((error: any, index: number) => (
                    <li key={index} className="text-sm text-red-700 bg-red-50 p-2 rounded break-words">
                      {error}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          
          {actualResult.warnings && actualResult.warnings.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg text-yellow-600 flex items-center space-x-2">
                  <AlertCircle className="h-5 w-5 flex-shrink-0" />
                  <span>Warnings ({actualResult.warnings.length})</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {actualResult.warnings.map((warning: any, index: number) => (
                    <li key={index} className="text-sm text-yellow-700 bg-yellow-50 p-2 rounded break-words">
                      {warning}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        
        {actualResult.files && actualResult.files.length > 0 && (
          <TabsContent value="files" className="mt-4">
            <FilesSection files={actualResult.files} taskResult={actualResult} />
          </TabsContent>
        )}
        
        {showRawData && (
          <TabsContent value="raw" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Raw Result Data</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-50 rounded-lg p-4 max-h-[600px] overflow-auto">
                  <pre className="text-xs font-mono whitespace-pre">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

export default TaskResultDisplay