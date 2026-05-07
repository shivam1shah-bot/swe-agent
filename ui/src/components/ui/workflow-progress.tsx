/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React from 'react'
import { CheckCircle2, Clock, AlertCircle, Loader } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './card'
import { Badge } from './badge'
import { Progress } from './progress'

interface WorkflowStage {
  name: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  order: number
  progress?: number
}

interface StageHistoryEntry {
  stage: string
  status: string
  timestamp: number
  details?: Record<string, any>
}

interface WorkflowProgressProps {
  currentStage?: string
  overallProgress: number
  totalStages: number
  completedStages: number
  workflowStages: Record<string, WorkflowStage>
  stageHistory: StageHistoryEntry[]
  showHistory?: boolean
  compact?: boolean
}

const getStageIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    case 'in_progress':
      return <Loader className="h-4 w-4 text-blue-500 animate-spin" />
    case 'failed':
      return <AlertCircle className="h-4 w-4 text-red-500" />
    default:
      return <Clock className="h-4 w-4 text-gray-400" />
  }
}

const getStageColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'bg-green-500'
    case 'in_progress':
      return 'bg-blue-500'
    case 'failed':
      return 'bg-red-500'
    default:
      return 'bg-gray-300'
  }
}

const formatTimestamp = (timestamp: number): string => {
  return new Date(timestamp).toLocaleString()
}

const WorkflowStageItem: React.FC<{
  stage: WorkflowStage
  isLast: boolean
  compact?: boolean
}> = ({ stage, isLast, compact }) => (
  <div className="flex items-center space-x-3">
    <div className="flex flex-col items-center">
      <div className={`w-3 h-3 rounded-full flex-shrink-0 ${getStageColor(stage.status)}`} />
      {!isLast && <div className="w-px h-8 bg-gray-300 mt-2" />}
    </div>
    
    <div className="flex-1 min-w-0">
      <div className="flex items-center space-x-2">
        {getStageIcon(stage.status)}
        <span className={`text-sm font-medium ${compact ? 'truncate' : ''}`}>
          {stage.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
        </span>
        <Badge 
          variant={stage.status === 'completed' ? 'default' : 'secondary'}
          className="text-xs"
        >
          {stage.status}
        </Badge>
      </div>
      
      {stage.progress !== undefined && stage.status === 'in_progress' && !compact && (
        <div className="mt-1">
          <Progress value={stage.progress} className="h-1" />
          <span className="text-xs text-gray-500">{stage.progress}%</span>
        </div>
      )}
    </div>
  </div>
)

export const WorkflowProgress: React.FC<WorkflowProgressProps> = ({
  currentStage,
  overallProgress,
  totalStages,
  completedStages,
  workflowStages,
  stageHistory,
  showHistory = false,
  compact = false
}) => {
  // Sort stages by order
  const sortedStages = Object.values(workflowStages).sort((a, b) => a.order - b.order)
  
  // Get stage status from history
  const getStageStatus = (stageName: string): string => {
    const historyEntry = stageHistory.find(entry => entry.stage === stageName)
    return historyEntry?.status || 'pending'
  }
  
  // Merge stage data with history status
  const enrichedStages: WorkflowStage[] = sortedStages.map(stage => ({
    ...stage,
    status: getStageStatus(stage.name) as any
  }))

  if (compact) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium">Progress</span>
            <Badge variant="outline">{completedStages}/{totalStages}</Badge>
          </div>
          <span className="text-sm text-gray-600">{overallProgress}%</span>
        </div>
        
        <Progress value={overallProgress} className="h-2" />
        
        {currentStage && (
          <div className="flex items-center space-x-2 text-sm">
            <Loader className="h-3 w-3 animate-spin text-blue-500" />
            <span className="text-gray-600">
              {currentStage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </span>
          </div>
        )}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Workflow Progress</CardTitle>
          <div className="flex items-center space-x-4">
            <Badge variant="outline">
              {completedStages}/{totalStages} stages
            </Badge>
            <span className="text-sm font-medium">{overallProgress}%</span>
          </div>
        </div>
        <Progress value={overallProgress} className="h-2" />
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Stage Timeline */}
        <div className="space-y-4">
          <h4 className="font-medium text-sm text-gray-700">Current Progress</h4>
          <div className="space-y-4">
            {enrichedStages.map((stage, index) => (
              <WorkflowStageItem
                key={stage.name}
                stage={stage}
                isLast={index === enrichedStages.length - 1}
                compact={false}
              />
            ))}
          </div>
        </div>
        
        {/* Stage History */}
        {showHistory && stageHistory.length > 0 && (
          <div className="space-y-4 border-t pt-4">
            <h4 className="font-medium text-sm text-gray-700">Stage History</h4>
            <div className="space-y-3">
              {stageHistory
                .sort((a, b) => b.timestamp - a.timestamp)
                .map((entry) => (
                  <div key={`${entry.stage}-${entry.timestamp}`} className="flex items-center justify-between text-sm">
                    <div className="flex items-center space-x-3">
                      {getStageIcon(entry.status)}
                      <span className="font-medium">
                        {entry.stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {entry.status}
                      </Badge>
                    </div>
                    <span className="text-gray-500 text-xs">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default WorkflowProgress 