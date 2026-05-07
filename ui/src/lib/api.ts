/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { getAuthHeader, handleUnauthorized } from './auth'
import { getApiBaseUrl, getApiTimeout, shouldLogApiRequests } from './environment'
import type {
  PulseOverview,
  PulseQueryParams,
  PulsePaginatedResponse,
  PulseRepo,
  PulseCommit,
  PulsePromptDetail,
  PulsePerson,
} from '@/types/pulse'

// Generic API client
class ApiClient {
  private get baseUrl(): string {
    return getApiBaseUrl()
  }

  private get timeout(): number {
    return getApiTimeout()
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`

    // Get auth header for all requests
    const authHeader = await getAuthHeader()

    const defaultHeaders:Record<string, string> = {
      ...authHeader,  // Include auth header (JWT or Basic)
    }
    if (!(options.body instanceof FormData)) {
      defaultHeaders['Content-Type'] = 'application/json';
    }

    const timeoutSignal = AbortSignal.timeout(this.timeout)
    const config: RequestInit = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
      signal: options.signal
        ? AbortSignal.any([options.signal, timeoutSignal])
        : timeoutSignal,
    }

    try {
      if (shouldLogApiRequests()) {
        console.log(`[API] ${options.method || 'GET'} ${url}`)
      }

      const response = await fetch(url, config)

      // Handle 401 Unauthorized - redirect to login
      if (response.status === 401) {
        handleUnauthorized()
        throw new Error('Unauthorized - redirecting to login')
      }

      const payload = await response.json().catch(() => ({}))

      // If backend returns a structured failed status, surface it to callers
      if (response.ok) {
        return payload
      }

      // Prefer backend message when available (FastAPI errors come as { detail: { error: "..." } } or { detail: "..." })
      const message = (payload && (payload.detail?.error || payload.detail || payload.message || payload.error)) || `HTTP error! status: ${response.status}`
      throw new Error(message)
    } catch (error) {
      if (shouldLogApiRequests()) {
        console.error('API request failed:', error)
      }
      throw error
    }
  }

  // Generic public GET — used by pages that need one-off endpoints
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint)
  }

  // Agents Catalogue API methods
  async getAgentsCatalogueItems(params: {
    page?: number
    per_page?: number
    search?: string
    type?: string
    lifecycle?: string
  } = {}): Promise<AgentsCatalogueResponse> {
    const queryParams = new URLSearchParams()

    if (params.page) queryParams.set('page', params.page.toString())
    if (params.per_page) queryParams.set('per_page', params.per_page.toString())
    if (params.search) queryParams.set('search', params.search)
    if (params.type) queryParams.set('type', params.type)
    if (params.lifecycle) queryParams.set('lifecycle', params.lifecycle)

    const endpoint = `/api/v1/agents-catalogue/items${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return this.request(endpoint)
  }

  async getAgentsCatalogueItem(itemId: string) {
    return this.request(`/api/v1/agents-catalogue/items/${itemId}`)
  }

  async getWorkflowDiagram(serviceType: string): Promise<WorkflowDiagramResponse> {
    return this.request(`/api/v1/agents-catalogue/workflow-diagram/${serviceType}`)
  }

  async createAgentsCatalogueItem(item: {
    name: string
    description: string
    type: string
    owners: string[]
    tags?: string[]
    lifecycle?: string
  }) {
    return this.request(`/api/v1/agents-catalogue/items`, {
      method: 'POST',
      body: JSON.stringify(item),
    })
  }

  async updateAgentsCatalogueItem(itemId: string, item: Partial<{
    name: string
    description: string
    type: string
    owners: string[]
    tags: string[]
    lifecycle: string
  }>) {
    return this.request(`/api/v1/agents-catalogue/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    })
  }

  async deleteAgentsCatalogueItem(itemId: string) {
    return this.request(`/api/v1/agents-catalogue/items/${itemId}`, {
      method: 'DELETE',
    })
  }

  async getAgentsCatalogueConfig() {
    return this.request('/api/v1/agents-catalogue/config')
  }

  async executeMicroFrontendService(
      serviceName: string = '',
      data: any = {},
      timeout: any = 1800,
      priority: any = 'normal',
      tags: any = []
  ): Promise<any> {
    return this.request(`/api/v1/agents-catalogue/micro-frontend/${serviceName}`, {
      method: 'POST',
      body: JSON.stringify({
        parameters: data,
        timeout: timeout,
        priority: priority,
        tags: tags,
      }),
    })
  }

  // Tasks API methods
  async getTasks(params: {
    status?: string
    user_email?: string
    connector?: string
    page?: number
    page_size?: number
  } = {}): Promise<Task[]> {
    const queryParams = new URLSearchParams()

    if (params.status) queryParams.set('status', params.status)
    if (params.user_email) queryParams.set('user_email', params.user_email)
    if (params.connector) queryParams.set('connector', params.connector)
    if (params.page) queryParams.set('page', params.page.toString())
    if (params.page_size) queryParams.set('page_size', params.page_size.toString())

    const endpoint = `/api/v1/tasks${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return this.request(endpoint)
  }

  async getCurrentUser(): Promise<{ username: string; email?: string; role?: string }> {
    return this.request('/api/v1/auth/me')
  }

  async getSchedules(): Promise<Schedule[]> {
    return this.request('/api/v1/schedules')
  }

  async updateSchedule(id: string, data: Partial<{ enabled: boolean; cron_expression: string; name: string }>): Promise<Schedule> {
    return this.request(`/api/v1/schedules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteSchedule(id: string): Promise<void> {
    return this.request(`/api/v1/schedules/${id}`, { method: 'DELETE' })
  }

  async triggerSchedule(id: string): Promise<{ schedule_id: string; status: string }> {
    return this.request(`/api/v1/schedules/${id}/trigger`, { method: 'POST' })
  }
  
  async getTaskUsers(): Promise<{ email: string; task_count: number }[]> {
    return this.request('/api/v1/tasks/users')
  }

  async getTask(taskId: string): Promise<Task> {
    return this.request(`/api/v1/tasks/${taskId}`)
  }

  async createTask(taskData: CreateTaskRequest): Promise<Task> {
    return this.request('/api/v1/tasks', {
      method: 'POST',
      body: JSON.stringify(taskData),
    })
  }

  async updateTaskStatus(taskId: string, statusData: UpdateTaskStatusRequest): Promise<Task> {
    return this.request(`/api/v1/tasks/${taskId}/status`, {
      method: 'PUT',
      body: JSON.stringify(statusData),
    })
  }

  async getTaskStatistics(): Promise<TaskStats> {
    return this.request('/api/v1/tasks/stats')
  }

  async createBatchTasks(batchData: BatchTaskCreateRequest): Promise<BatchTaskCreateResponse> {
    return this.request('/api/v1/tasks/batch', {
      method: 'POST',
      body: JSON.stringify(batchData),
    })
  }

  // createWorkflowTask method removed - workflow system deleted

  // Health API methods
  async getHealthStatus() {
    return this.request('/api/v1/health')
  }

  async getAuthMe() {
    return this.request('/api/v1/auth/me')
  }

  async getHealthMetrics() {
    return this.request('/api/v1/health/metrics')
  }

  async getAuthStatus(): Promise<{ auth_enabled: boolean }> {
    return this.request('/api/v1/auth/status')
  }

  // Workflow API methods removed - workflow system deleted

  async getAgentsStatus() {
    return this.request('/api/v1/health/agents')
  }

  async getMcpServersStatus() {
    return this.request('/api/v1/health/mcp-servers')
  }

  // Autonomous Agent API methods
  async triggerAutonomousAgent(
    prompt: string,
    repository_url?: string,
    branch?: string,
    skills: string[] = []
  ): Promise<{ task_id?: string; status: string }> {
    const body: any = { prompt, skills }
    if (repository_url) body.repository_url = repository_url
    if (branch) body.branch = branch
    return this.request('/api/v1/agents/run', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async triggerAutonomousAgentBatch(
    prompt: string,
    repositories: Array<{ repository_url: string; branch?: string }>,
    skills: string[] = []
  ): Promise<{ task_id?: string; status: string }> {
    return this.request('/api/v1/agents/batch', {
      method: 'POST',
      body: JSON.stringify({ prompt, repositories, skills }),
    })
  }

  async listAgentSkills(): Promise<Array<{ name: string; description: string }>> {
    return this.request('/api/v1/agent-skills/global/list')
  }

  async listPlugins(): Promise<Plugin[]> {
    return this.request('/api/v1/plugins-catalogue/list')
  }

  async refreshPlugins(): Promise<{ refreshed: boolean; count: number }> {
    return this.request('/api/v1/plugins-catalogue/refresh', { method: 'POST' })
  }

  async getPluginAgents(pluginDir: string): Promise<PluginAgent[]> {
    return this.request(`/api/v1/plugins-catalogue/${encodeURIComponent(pluginDir)}/agents`)
  }

  async getMcpServerTools(serverId: string): Promise<{ server_id: string; tools: Array<{ name: string; full_name: string }>; count: number }> {
    return this.request(`/api/v1/health/mcp-servers/${encodeURIComponent(serverId)}/tools`)
  }

  async triggerMultiRepoAgent(
    prompt: string,
    repositories: Array<{ repository_url: string; branch?: string }>,
    skills: string[] = []
  ): Promise<{ task_id?: string; status: string }> {
    return this.request('/api/v1/agents/multi-repo', {
      method: 'POST',
      body: JSON.stringify({ prompt, repositories, skills }),
    })
  }

  async triggerCleanSlateAgent(
    prompt: string,
    skills: string[] = [],
    slackChannel?: string
  ): Promise<{ task_id?: string; status: string }> {
    return this.request('/api/v1/agents/run', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        skills,
        ...(slackChannel ? { slack_channel: slackChannel.trim().replace(/^#/, '') } : {}),
      }),
    })
  }

  async createSchedule(data: {
    name: string
    skill_name: string
    cron_expression: string
    parameters: Record<string, any>
  }): Promise<{ id: string; name: string; cron_expression: string; enabled: boolean }> {
    return this.request('/api/v1/schedules', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // API Doc Generator methods
  async triggerAPIDocGenerator(parameters: {
    document_file_path: string;
    bank_name: string;
    apis_to_focus: string;
    custom_prompt?: string;
    output_format?: string;
    include_examples?: boolean;
    enhance_context?: boolean;
  }): Promise<{ task_id: string; status: string }> {
    return this.executeMicroFrontendService(
      'api-doc-generator',
      parameters,
      120,
      'normal',
      ['api-doc-generator', 'documentation']
    )
  }



  // Bank UAT Agent methods
  async triggerBankUATAgent(data: {
    api_doc_path: string;
    bank_name: string;
    uat_host?: string;
    generate_encrypted_curls?: boolean;
    // New three-certificate structure
    bank_public_cert_path?: string;     // Bank's public certificate for encrypting requests TO bank
    private_key_path?: string;          // Partner's private key for decrypting responses FROM bank
    partner_public_key_path?: string;   // Partner's public key for bank to encrypt responses TO partner
    // Legacy parameter for backward compatibility
    public_key_path?: string;           // @deprecated - use bank_public_cert_path instead
    encryption_type?: string;
    encryption_template?: string;
    enable_ai_analysis?: boolean;
    ai_confidence_threshold?: number;
    manual_config_override?: Record<string, any>;
    test_scenarios?: string[];
    timeout_seconds?: number;
    include_response_analysis?: boolean;
    custom_headers?: Record<string, string>;
    custom_prompt?: string;
  }): Promise<{ task_id: string; status: string; message?: string }> {
    return this.executeMicroFrontendService(
      'bank-uat-agent',
      data,
      120,
      'normal',
      ['bank-uat-agent', 'testing']
    )
  }

  // File download methods for agents
  async downloadApiDocGeneratorFile(taskId: string, fileType: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/v1/agents-catalogue/micro-frontend/api-doc-generator/download/${taskId}/${fileType}`, {
      headers: await getAuthHeader(),
    })

    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`)
    }

    return response.blob()
  }

  async downloadBankUATAgentFile(taskId: string, fileType: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/v1/agents-catalogue/micro-frontend/bank-uat-agent/download/${taskId}/${fileType}`, {
      headers: await getAuthHeader(),
    })

    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`)
    }

    return response.blob()
  }

  // Generic download method for any agent
  async downloadAgentFile(itemType: string, usecaseName: string, taskId: string, fileType: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/v1/agents-catalogue/${itemType}/${usecaseName}/download/${taskId}/${fileType}`, {
      headers: await getAuthHeader(),
    })

    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`)
    }

    return response.blob()
  }



  async getEncryptionStatus(): Promise<{
    rsa_available: boolean;
    aes_available: boolean;
    hybrid_available: boolean;
    supported_types: string[];
    version: string;
  }> {
    return this.request('/api/v1/agents-catalogue/bank-uat-agent/encryption-status')
  }

  // Bank Integration API methods
  async triggerBankIntegration(params: {
    bank_name: string;
    version?: string;
    branch_name?: string;
    enable_integrations_go?: boolean;
    enable_fts?: boolean;
    enable_payouts?: boolean;
    enable_xbalance?: boolean;
    enable_terminals?: boolean;
    enable_kube_manifests?: boolean;
    max_iterations?: number;
    max_retries?: number;
    bank_doc?: File | null;
  }): Promise<{ task_id?: string; status: string; message: string }> {
    const parameters = {
      bank_name: params.bank_name,
      version: params.version || 'v3',
      branch_name: params.branch_name,
      enable_integrations_go: params.enable_integrations_go ?? true,
      enable_fts: params.enable_fts ?? true,
      enable_payouts: params.enable_payouts ?? true,
      enable_xbalance: params.enable_xbalance ?? true,
      enable_terminals: params.enable_terminals ?? true,
      enable_kube_manifests: params.enable_kube_manifests ?? true,
      max_iterations: params.max_iterations || 50,
      max_retries: params.max_retries || 3,
    }

    // Always send as JSON - file is kept in frontend for showcase only
    return this.request('/api/v1/agents-catalogue/api/bank-integration', {
      method: 'POST',
      body: JSON.stringify({ parameters }),
    })
  }

  async getAgentBehavior(taskId: string): Promise<AgentBehaviorResponse> {
    return this.request(`/api/agent-behavior/${taskId}`)
  }

  async killTask(taskId: string): Promise<{ message: string }> {
    // Use the task status update endpoint to cancel the task
    await this.updateTaskStatus(taskId, {
      status: 'cancelled',
      message: 'Task cancelled by user',
      progress: 100
    })

    return { message: 'Task cancelled successfully' }
  }



  // File upload method
  async uploadFile(file: File, fileType: string = "document"): Promise<{
    success: boolean;
    message: string;
    file_path?: string;
    original_filename?: string;
    saved_filename?: string;
    file_size?: number;
    file_type?: string;
    content_type?: string;
    upload_timestamp?: number;
    pdf_file_path?: string;
    crypto_file_path?: string;
    document_file_path?: string;
  }> {
    const url = `${this.baseUrl}/api/v1/files/upload-file`

    // Get auth header for the request
    const authHeader = await getAuthHeader()

    // Create FormData for file upload
    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_type', fileType)

    const config: RequestInit = {
      method: 'POST',
      headers: {
        // Don't set Content-Type - let browser set it with boundary for FormData
        ...authHeader,
      },
      body: formData,
      signal: AbortSignal.timeout(this.timeout),
    }

    try {
      if (shouldLogApiRequests()) {
        console.log(`[API] POST ${url} - File upload: ${file.name} (type: ${fileType})`)
      }

      const response = await fetch(url, config)

      if (!response.ok) {
        // Try to get detailed error information
        const errorData = await response.json().catch(() => ({}))
        const errorMessage = errorData.detail?.error || errorData.detail || `HTTP error! status: ${response.status}`
        throw new Error(errorMessage)
      }

      return await response.json()
    } catch (error) {
      if (shouldLogApiRequests()) {
        console.error('File upload failed:', error)
      }
      throw error
    }
  }

  async getTaskExecutionLogs(taskId: string): Promise<TaskExecutionLogs> {
    return this.request(`/api/v1/tasks/${taskId}/execution-logs`)
  }

  // AI Usage Stats API method
  async getAIUsageStats(): Promise<any> {
    return this.request('/api/v1/code-review/ai-usage-stats')
  }

  // Repository Metrics API methods
  async getRepositoryMetrics(repository: string, date: string): Promise<RepositoryMetricsResponse> {
    return this.request(`/api/v1/code-review/repository-metrics/${repository}/${date}`)
  }

  async storeRepositoryMetrics(repository: string, date: string, metrics: RepositoryMetricsData): Promise<RepositoryMetricsResponse> {
    return this.request('/api/v1/code-review/repository-metrics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repository, date, metrics })
    })
  }

  async getAutonomousAgentTasks(): Promise<Task[]> {
    const tasks = await this.getTasks({ status: 'running,pending' })

    // Filter for autonomous agent tasks only
    return tasks.filter(task => {
      return (
        (task.parameters &&
          typeof task.parameters === 'object' &&
          'workflow_id' in task.parameters &&
          task.parameters.workflow_id === "autonomous_agent") ||
        (task.name && task.name.toLowerCase().includes('autonomous agent'))
      )
    })
  }

  async executeGenSpecTask(parameters: any = {}): Promise<any> {
    // GenSpec tasks can take longer, use 1800 seconds (30 minutes) max timeout
    return this.executeMicroFrontendService('genspec-agent', parameters, 1800)
  }

  async getAuthUrl(): Promise<{ data: any }> {
    const response = await this.executeMicroFrontendService('genspec-agent', {
      operation: 'get_auth_url'
    }, 60) // Pass 60 seconds (API minimum)
    return { data: response }
  }

  async exchangeCodeAndParseContent(code: string, prdDocument: string): Promise<{data: any}> {
    try {
      const response = await this.executeMicroFrontendService('genspec-agent', {
        operation: 'exchange_code_and_parse',
        code,
        prdDocument
      }, 60) // Pass 60 seconds
      return { data: response };
    } catch (error) {
      console.error('Error exchanging code and parsing content:', error);
      throw error;
    }
  };

  async parseContent(formData: FormData): Promise<{ data: any }> {
    // Use the files router endpoint for parsing content
    const response = await this.request('/api/v1/files/parse-content', {
      method: 'POST',
      body: formData,
    }) as any;
    // Extract data from response structure
    const data = response.data || response;
    return { data };
  }

  async analyzeTextArchitecture(textDescription: string): Promise<{ data: any }> {
    const response = await this.executeMicroFrontendService('genspec-agent', {
      operation: 'analyze_text_architecture',
      text_description: textDescription
    }, 60) // Pass 60 seconds for analysis
    return { data: response };
  }

  // ─── Pulse (AI Usage Analytics) API methods ───

  private buildPulseQuery(params: PulseQueryParams): string {
    const qp = new URLSearchParams()
    if (params.days) qp.set('days', params.days.toString())
    if (params.sort) qp.set('sort', params.sort)
    if (params.repo) qp.set('repo', params.repo)
    if (params.email) qp.set('email', params.email)
    if (params.limit) qp.set('limit', params.limit.toString())
    if (params.offset !== undefined) qp.set('offset', params.offset.toString())
    const qs = qp.toString()
    return qs ? `?${qs}` : ''
  }

  async getPulseOverview(days?: number | null, signal?: AbortSignal): Promise<PulseOverview> {
    return this.request(`/api/v1/pulse/overview${this.buildPulseQuery({ days })}`, { signal })
  }

  async getPulseRepos(params: PulseQueryParams = {}, signal?: AbortSignal): Promise<PulsePaginatedResponse<PulseRepo>> {
    return this.request(`/api/v1/pulse/repos${this.buildPulseQuery(params)}`, { signal })
  }

  async getPulseCommits(params: PulseQueryParams = {}, signal?: AbortSignal): Promise<PulsePaginatedResponse<PulseCommit>> {
    return this.request(`/api/v1/pulse/commits${this.buildPulseQuery(params)}`, { signal })
  }

  async getPulsePrompts(params: PulseQueryParams = {}, signal?: AbortSignal): Promise<PulsePaginatedResponse<PulsePromptDetail>> {
    return this.request(`/api/v1/pulse/prompts${this.buildPulseQuery(params)}`, { signal })
  }

  async getPulsePeople(params: PulseQueryParams = {}, signal?: AbortSignal): Promise<PulsePaginatedResponse<PulsePerson>> {
    return this.request(`/api/v1/pulse/people${this.buildPulseQuery(params)}`, { signal })
  }

}

// Export singleton instance
export const apiClient = new ApiClient()

// Task-related types
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Schedule {
  id: string
  name: string
  skill_name: string
  cron_expression: string
  parameters: Record<string, any>
  enabled: boolean
  last_run_at: number | null
  created_at: number
  updated_at: number
}

export interface Task {
  id: string
  name: string
  description?: string
  status: TaskStatus
  created_at: string
  updated_at: string
  progress?: number
  parameters?: Record<string, any>
  metadata?: Record<string, any>
  result?: any
}

export interface TaskConnectorInfo {
  name?: string        // slack | dashboard | devrev
  user_email?: string
  source_id?: string   // ticket ID, channel, etc.
}

export function getTaskConnector(task: Task): TaskConnectorInfo {
  return (task.metadata?.connector || {}) as TaskConnectorInfo
}

export interface CreateTaskRequest {
  name: string
  description?: string
  parameters?: Record<string, any>
}

export interface UpdateTaskStatusRequest {
  status: TaskStatus
  message?: string
  progress?: number
}

export interface TaskStats {
  total_tasks: number
  by_status: Record<string, number>
}

export interface BatchTaskCreateRequest {
  tasks: CreateTaskRequest[]
}

export interface BatchTaskCreateResponse {
  total_created: number
  total_errors: number
  created_tasks: Task[]
  errors: Array<{
    index: number
    task_name: string
    error: string
  }>
}

// Export existing types
export interface AgentsCatalogueItem {
  id: string
  name: string
  description: string
  type: string
  type_display: string
  lifecycle: string
  owners: string[]
  tags: string[]
  created_at: number
  updated_at: number
}

export interface AgentsCatalogueConfig {
  available_tags: string[]
  available_types: { value: string; label: string }[]
  available_lifecycles: string[]
  default_owner: string
}

export interface AgentsCatalogueResponse {
  items: AgentsCatalogueItem[]
  pagination: {
    page: number
    per_page: number
    total_pages: number
    total_items: number
    has_next: boolean
    has_prev: boolean
  }
  filters: {
    search?: string
    type?: string
    lifecycle?: string
  }
}

export interface AgentsCataloguePagination {
  page: number
  per_page: number
  total_pages: number
  total_items: number
  has_next: boolean
  has_prev: boolean
}

export interface CreateAgentsCatalogueItemData {
  name: string
  description: string
  type: string
  lifecycle: string
  owners: string[]
  tags: string[]
}

export interface WorkflowDiagramResponse {
  success: boolean
  service_type: string
  diagram_syntax: string
  diagram_type: string
  generated_at: number
}



// Autonomous Agent types
export interface AgentBehaviorItem {
  timestamp: number
  formatted_time: string
  action: string
  description: string
  details?: any
}

export interface AgentBehaviorResponse {
  behavior: AgentBehaviorItem[]
}

// Health and System Status types
export interface HealthStatus {
  status: string
  timestamp: number
  checks: {
    database?: {
      status: string
      message: string
      response_time_ms?: number
    }
    services?: {
      status: string
      message: string
      response_time_ms?: number
    }
    configuration?: {
      status: string
      message: string
    }
  }
  response_time_ms?: number
}

export interface HealthMetrics {
  timestamp: number
  database: {
    status: string
    connection_pool?: any
    response_time_ms?: number
    error?: string
  }
  services: {
    task_service: {
      status: string
      response_time_ms?: number
      error?: string
    }
  }
  system: {
    uptime_seconds: number
  }
}

// Workflow-related types removed - workflow system deleted

// Repository Metrics types
export interface RepositoryMetadata {
  date: string
  repository: string
  generated_at: string
  version: string
}

export interface CommentCategories {
  [category: string]: number
}

export interface SeverityDistribution {
  high: number
  low: number
}

export interface RepositoryStats {
  total_comments: number
  prs_reviewed: number
  comment_categories: CommentCategories
  severity_distribution: SeverityDistribution
}

export interface IssueDetectionAccuracy {
  precision: number
  recall: number
  f1_score: number
}

export interface CategoryAcceptanceRates {
  [category: string]: number
}

export interface EffectivenessMetrics {
  comment_acceptance_rate: number
  issue_detection_accuracy: IssueDetectionAccuracy
  false_positive_rate: number
  false_negatives_rate: number
  category_acceptance_rates: CategoryAcceptanceRates
}

export interface CriticalIssuesMetrics {
  total_critical_issues_caught: number
  critical_issue_accepted_rate: number
  category_breakdown: Record<string, number>
  category_catch_rates: Record<string, number>
}

export interface ProductivityMetrics {
  review_turnaround_time_minutes: number
  human_review_comment_percent: number
  human_comments_count: number
  time_saved_minutes: number
  feedback_quality_rate: number
}

export interface ProcessingLatency {
  small_prs_median_minutes: number
  medium_prs_median_minutes: number
  large_prs_median_minutes: number
}

export interface TechnicalMetrics {
  system_uptime_percent: number
  processing_latency: ProcessingLatency
}

export interface RepositoryMetricsData {
  metadata: RepositoryMetadata
  stats: RepositoryStats
  effectiveness: EffectivenessMetrics
  critical_issues: CriticalIssuesMetrics
  productivity: ProductivityMetrics
  technical: TechnicalMetrics
}

export interface RepositoryMetricsResponse {
  success: boolean
  repository: string
  date: string
  metrics?: RepositoryMetricsData
  cached?: boolean
  message?: string
}

export interface SystemOverviewData {
  healthStatus: HealthStatus
  taskStats: TaskStats
  systemMetrics: HealthMetrics
}

// Agents and MCP Servers types
export interface Agent {
  name: string
  type: string
  status: string
  description: string
}

export interface AgentsStatusResponse {
  agents: Agent[]
  total_count: number
  active_count: number
  timestamp: number
}

export interface McpServer {
  name: string
  type: string
  status: string
  description: string
}

export interface McpServersStatusResponse {
  servers: McpServer[]
  total_count: number
  available_count: number
  unavailable_count: number
  unknown_count: number
  timestamp: number
}

export interface Plugin {
  name: string
  plugin_dir: string
  description: string
  version?: string
  keywords?: string[]
  homepage?: string
  mcp_servers?: boolean
  agent_count: number
  agents: string[]
  command_count: number
  skill_count: number
  has_hooks: boolean
  has_mcp: boolean
  has_lsp: boolean
}

export interface PluginAgent {
  slug: string
  name: string
  description: string
  fields: Record<string, string | string[]>  // scalar or list frontmatter values
}

export interface ExecutionLogEntry {
  log_index: number
  timestamp?: string
  content: string
  status: string
}

export interface TaskExecutionLogs {
  task_id: string
  total_logs: number
  last_logs: ExecutionLogEntry[]
  file_status: string
  last_updated?: string
}

