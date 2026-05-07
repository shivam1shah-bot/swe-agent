/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient } from '@/lib/api';
import { AlertCircle, ArrowLeft, CheckCircle, ExternalLink } from 'lucide-react';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import GatewayIntegrationComponent from './GatewayIntegrationComponent';

interface GatewayIntegrationParams {
  gateway_name: string;
  method: string;
  custom_method?: string;
  countries_applicable: string[];
  apis_to_integrate: string[];
  credentials: Array<{ key: string; value: string; }>;
  encryption_algorithm: string;
  custom_encryption?: string;
  api_links: string[];
  additional_test_cases: number;
  custom_instructions: string;
  integration_notes: string;
  max_iterations: number;
  use_switch?: boolean;
}

interface ExecutionResult {
  status: string;
  message: string;
  workflow_type: string;
  task_id: string;
  execution_time: number;
  gateway_name?: string;
  method?: string;
  countries_applicable?: string[];
  summary?: any;
  metadata?: {
    repositories_modified?: number;
    devstack_label?: string;
    iterations_completed?: number;
    e2e_tests_passed?: boolean;
    deployment_successful?: boolean;
    pr_count?: number;
    workflow_completed?: boolean;
  };
  pr_urls?: string[];
  devstack_label?: string;
  next_steps?: string[];
  error?: string;
  failed_steps?: string[];
  current_step?: string;
  suggestions?: string[];
}

const GatewayIntegrations: React.FC = () => {
  const navigate = useNavigate();
  const [isExecuting, setIsExecuting] = useState(false);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExecute = async (params: GatewayIntegrationParams): Promise<ExecutionResult> => {
    setIsExecuting(true);
    setError(null);
    setResult(null);

    try {
      const requestData = {
        parameters: params,
        timeout: 120,
        priority: 'high',
        tags: ['gateway-integration', 'automation', 'langgraph']
      };

      // Use the same pattern as other micro frontend services
      const resultData: ExecutionResult = await apiClient.executeMicroFrontendService('gateway-integrations-common', requestData);
      setResult(resultData);
      return resultData;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`Gateway integration failed: ${errorMessage}`);
      console.error('Error executing gateway integration:', err);
      throw err;
    } finally {
      setIsExecuting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="default" className="bg-green-100 text-green-800 border-green-200">
          <CheckCircle className="w-3 h-3 mr-1" />
          Completed
        </Badge>;
      case 'failed':
        return <Badge variant="destructive" className="bg-red-100 text-red-800 border-red-200">
          <AlertCircle className="w-3 h-3 mr-1" />
          Failed
        </Badge>;
      case 'running':
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800 border-blue-200">
          <div className="w-3 h-3 mr-1 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
          Running
        </Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/agents-catalogue')}
              className="flex items-center space-x-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Agents Catalogue</span>
            </Button>
            <div className="border-l border-gray-300 pl-4">
              <h1 className="text-2xl font-bold text-gray-900">Gateway Integration</h1>
              <p className="text-gray-600">
                Automate the integration of new payment gateways with standardized testing and deployment
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
              Micro Frontend
            </Badge>
            <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
              Experimental
            </Badge>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6">
        <div className="max-w-7xl mx-auto">
          {/* Success/Error Results */}
          {(error || (result && result.status !== 'queued')) && (
            <div className="mb-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    {result ? getStatusBadge(result.status) : <AlertCircle className="w-5 h-5 text-red-500" />}
                    <span>
                      {result ? 'Integration Result' : 'Integration Error'}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                      <p className="text-red-800 font-medium">Error:</p>
                      <p className="text-red-700">{error}</p>
                    </div>
                  )}

                  {result && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <p className="text-gray-900">{result.message}</p>
                        <div className="text-sm text-gray-500">
                          Execution time: {formatDuration(result.execution_time)}
                        </div>
                      </div>



                      {result.status === 'completed' && result.metadata && (
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                          <h4 className="font-medium text-green-800 mb-2">Integration Summary</h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-green-700 font-medium">Repositories Modified</p>
                              <p className="text-green-600">{result.metadata.repositories_modified}</p>
                            </div>
                            <div>
                              <p className="text-green-700 font-medium">Iterations</p>
                              <p className="text-green-600">{result.metadata.iterations_completed}</p>
                            </div>
                            <div>
                              <p className="text-green-700 font-medium">E2E Tests</p>
                              <p className="text-green-600">{result.metadata.e2e_tests_passed ? 'Passed' : 'Failed'}</p>
                            </div>
                            <div>
                              <p className="text-green-700 font-medium">Deployment</p>
                              <p className="text-green-600">{result.metadata.deployment_successful ? 'Successful' : 'Failed'}</p>
                            </div>
                          </div>
                        </div>
                      )}

                      {result.pr_urls && result.pr_urls.length > 0 && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                          <h4 className="font-medium text-blue-800 mb-2">Generated Pull Requests</h4>
                          <div className="space-y-2">
                            {result.pr_urls.map((url, index) => (
                              <div key={index} className="flex items-center space-x-2">
                                <ExternalLink className="w-4 h-4 text-blue-600" />
                                <a
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:underline"
                                >
                                  Pull Request #{index + 1}
                                </a>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {result.devstack_label && (
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                          <h4 className="font-medium text-gray-800 mb-2">DevStack Environment</h4>
                          <p className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                            {result.devstack_label}
                          </p>
                        </div>
                      )}

                      {result.next_steps && result.next_steps.length > 0 && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                          <h4 className="font-medium text-blue-800 mb-2">Next Steps</h4>
                          <ul className="text-sm text-blue-700 space-y-1">
                            {result.next_steps.map((step, index) => (
                              <li key={index}>• {step}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {result.status === 'failed' && result.suggestions && result.suggestions.length > 0 && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                          <h4 className="font-medium text-yellow-800 mb-2">Suggestions</h4>
                          <ul className="text-sm text-yellow-700 space-y-1">
                            {result.suggestions.map((suggestion, index) => (
                              <li key={index}>• {suggestion}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          {/* Gateway Integration Component */}
          <GatewayIntegrationComponent
            onExecute={handleExecute}
            isExecuting={isExecuting}
            result={result}
          />
        </div>
      </div>
    </div>
  );
};

export default GatewayIntegrations;