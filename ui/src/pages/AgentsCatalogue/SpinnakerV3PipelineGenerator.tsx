import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Select } from '../../components/ui/select';
import { ArrowLeft } from 'lucide-react';
import { apiClient } from '../../lib/api';

interface ExecutionRequest {
  parameters: {
    spinnaker_application_name: string;
    namespace_name: string;
    region: string;
    environment_type: string;
    pipeline_environment: string;
    github_repo_name: string;
  };
  timeout?: number;
  priority?: string;
  tags?: string[];
}

interface RegionOption {
  name: string;
  code: string;
}

const SpinnakerV3PipelineGenerator: React.FC = () => {
  const navigate = useNavigate();

  // Form state
  const [spinnakerApplicationName, setSpinnakerApplicationName] = useState('');
  const [namespaceName, setNamespaceName] = useState('');
  const [selectedRegion, setSelectedRegion] = useState('');
  const [environmentType, setEnvironmentType] = useState('');
  const [pipelineEnvironment, setPipelineEnvironment] = useState('prod'); // Default to prod
  const [githubRepoName, setGithubRepoName] = useState('');

  // Execution state
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Available options
  const availableRegions: RegionOption[] = [
    { name: 'Mumbai-RSPL', code: 'mum' },
    { name: 'Ohio', code: 'ohio' },
    { name: 'Mumbai-DR', code: 'mum-dr' },
    { name: 'Hyderabad', code: 'hyd' },
    { name: 'Singapore', code: 'singapore' }
  ];

  const environmentTypes = [
    { label: 'CDE', value: 'cde' },
    { label: 'NonCDE', value: 'noncde' }
  ];

  const pipelineEnvironments = [
    { label: 'Production', value: 'prod' }
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsExecuting(true);
    setError(null);
    setSuccess(false);

    try {
      // Validate required fields
      if (!spinnakerApplicationName.trim()) {
        throw new Error('Spinnaker Application Name is required');
      }
      if (!namespaceName.trim()) {
        throw new Error('Namespace name is required');
      }
      if (!selectedRegion) {
        throw new Error('Region selection is required');
      }
      if (!environmentType) {
        throw new Error('Environment type is required');
      }
      if (!pipelineEnvironment) {
        throw new Error('Pipeline environment is required');
      }
      if (!githubRepoName.trim()) {
        throw new Error('GitHub repo name is required');
      }

      const requestData: ExecutionRequest = {
        parameters: {
          spinnaker_application_name: spinnakerApplicationName.trim(),
          namespace_name: namespaceName.trim(),
          region: selectedRegion,
          environment_type: environmentType,
          pipeline_environment: pipelineEnvironment,
          github_repo_name: githubRepoName.trim(),
        },
        timeout: 1800, // 30 minutes
        priority: 'normal',
        tags: ['spinnaker', 'pipeline-generation', 'devops']
      };

      // Execute the pipeline generation request
      await apiClient.executeMicroFrontendService('spinnaker-v3-pipeline-generator', requestData);

      // Pipeline generation initiated successfully
      setSuccess(true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`Pipeline generation failed: ${errorMessage}`);
      console.error('Error generating pipeline:', err);
    } finally {
      setIsExecuting(false);
    }
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
              <h1 className="text-2xl font-bold text-gray-900">Spinnaker V3 Pipeline Generator</h1>
              <p className="text-gray-600">
                Generate production-ready Spinnaker V3 pipeline configurations
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
              Micro Frontend
            </Badge>
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              Production
            </Badge>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 space-y-6">
        <div className="max-w-4xl mx-auto">
          {/* Configuration Form */}
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Configuration</CardTitle>
              <CardDescription>
                Configure your Spinnaker V3 pipeline parameters
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                                   {/* Service Details */}
                 <div className="space-y-4">
                   <h3 className="text-lg font-medium">Service Details</h3>

                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     <div>
                       <label className="block text-sm font-medium mb-2">
                         Spinnaker Application Name *
                       </label>
                       <Input
                         value={spinnakerApplicationName}
                         onChange={(e) => setSpinnakerApplicationName(e.target.value)}
                         placeholder="my-application"
                         required
                       />
                     </div>
                     <div>
                       <label className="block text-sm font-medium mb-2">
                         Namespace Name *
                       </label>
                       <Input
                         value={namespaceName}
                         onChange={(e) => setNamespaceName(e.target.value)}
                         placeholder="my-namespace"
                         required
                       />
                     </div>
                   </div>

                   <div>
                     <label className="block text-sm font-medium mb-2">
                       GitHub Repo Name *
                     </label>
                     <Input
                       value={githubRepoName}
                       onChange={(e) => setGithubRepoName(e.target.value)}
                       placeholder="my-repo"
                       required
                     />
                     <p className="text-xs text-gray-500 mt-1">
                       Enter just the repository name (e.g., "my-repo"), not the full URL
                     </p>
                   </div>
                 </div>

                {/* Deployment Configuration */}
                <div className="space-y-4 border-t pt-6">
                  <h3 className="text-lg font-medium">Deployment Configuration</h3>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Region *
                      </label>
                      <Select
                        value={selectedRegion}
                        onChange={(e) => setSelectedRegion(e.target.value)}
                        required
                      >
                        <option value="">Select a region</option>
                        {availableRegions.map((region) => (
                          <option key={region.code} value={region.code}>
                            {region.name}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Environment Type *
                      </label>
                      <Select
                        value={environmentType}
                        onChange={(e) => setEnvironmentType(e.target.value)}
                        required
                      >
                        <option value="">Select environment type</option>
                        {environmentTypes.map((type) => (
                          <option key={type.value} value={type.value}>
                            {type.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Pipeline Environment *
                      </label>
                      <Select
                        value={pipelineEnvironment}
                        onChange={(e) => setPipelineEnvironment(e.target.value)}
                        required
                      >
                        <option value="">Select pipeline environment</option>
                        {pipelineEnvironments.map((env) => (
                          <option key={env.value} value={env.value}>
                            {env.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                </div>

                {/* Success Display */}
                {success && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="text-green-700 text-sm">
                      Pipeline generation has been initiated! You can now view the status in the{' '}
                      <button
                        onClick={() => navigate('/tasks')}
                        className="underline hover:text-green-800 font-medium"
                      >
                        Tasks page
                      </button>
                      .
                    </p>
                  </div>
                )}

                {/* Error Display */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-700 text-sm">{error}</p>
                  </div>
                )}

                {/* Submit Button */}
                <Button
                  type="submit"
                  disabled={isExecuting}
                  className="w-full"
                >
                  {isExecuting ? 'Generating Pipeline...' : 'Generate Spinnaker Pipeline'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default SpinnakerV3PipelineGenerator;