/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { ArrowLeft } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { getApiBaseUrl } from '@/lib/environment';

interface Repository {
  id: string;
  name: string;
  description?: string;
  full_name: string;
  clone_url: string;
}



export const RepoContextGeneratorPage: React.FC = () => {
  const navigate = useNavigate();

  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedOrg, setSelectedOrg] = useState('razorpay');
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    branchName: '',
    prTitle: 'AI Documentation',
    documentationType: 'comprehensive',
    includeExamples: true,
    includeDiagrams: true,
    maxIterations: 3
  });

  // Load repositories on component mount
  useEffect(() => {
    loadRepositories(selectedOrg);
  }, [selectedOrg]);



  const loadRepositories = async (org: string) => {
    setLoading(true);
    try {
      // Use API base URL with fetch for GitHub repositories (no specific API client method exists)
      const response = await fetch(`${getApiBaseUrl()}/api/github/repos/${org}`);
      const data: any = await response.json();

      if (data && data.items) {
        const repos = data.items.map((repo: any) => ({
          id: repo.id,
          name: repo.name,
          description: repo.description,
          full_name: repo.full_name,
          clone_url: repo.clone_url
        }));
        setRepositories(repos);
      }
    } catch (error) {
      console.error('Error loading repositories:', error);
    } finally {
      setLoading(false);
    }
  };



  const generateDocumentation = async () => {
    if (!selectedRepo) {
      alert('Please select a repository first');
      return;
    }

    setLoading(true);

    const requestData: any = {
      repo_path: selectedRepo.clone_url,
      documentation_type: formData.documentationType,
      include_examples: formData.includeExamples,
      include_diagrams: formData.includeDiagrams,
      max_iterations: formData.maxIterations
    };

    if (formData.branchName) {
      requestData.branch_name = formData.branchName;
    }

    if (formData.prTitle) {
      requestData.pr_title = formData.prTitle;
    }

    try {
      // Use the same pattern as other micro frontend services
      const result = await apiClient.executeMicroFrontendService('repo-context-generator', {
        parameters: requestData
      });

      if (result.success && result.task_id) {
        // Reset form
        setFormData(prev => ({
          ...prev,
          branchName: '',
          prTitle: 'AI Documentation'
        }));
      } else {
        alert('Error: ' + (result.error || 'Unknown error occurred'));
      }
    } catch (error) {
      console.error('Error submitting job:', error);
      alert('Failed to submit documentation job');
    } finally {
      setLoading(false);
    }
  };

  const filteredRepositories = repositories.filter(repo =>
    repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    repo.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );



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
              <h1 className="text-2xl font-bold text-gray-900">Repo Context Generator</h1>
              <p className="text-gray-600">
                Scans code repositories to generate docs and context. Enabling AI agents, IDEs to work better with the repository.
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
      <div className="container mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Repository Selection */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>Select Repository</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">Organization</label>
                <select
                  className="w-full p-2 border border-gray-300 rounded-md"
                  value={selectedOrg}
                  onChange={(e) => setSelectedOrg(e.target.value)}
                >
                  <option value="razorpay">razorpay</option>
                </select>
              </div>

              <div>
                <Input
                  placeholder="Search repositories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="max-h-96 overflow-y-auto space-y-2">
                {loading ? (
                  <div className="text-center py-4">Loading...</div>
                ) : (
                  filteredRepositories.map(repo => (
                    <Card
                      key={repo.id}
                      className={`cursor-pointer transition-all hover:shadow-md ${
                        selectedRepo?.id === repo.id ? 'ring-2 ring-blue-500' : ''
                      }`}
                      onClick={() => setSelectedRepo(repo)}
                    >
                      <CardContent className="p-3">
                        <div className="font-medium">{repo.name}</div>
                        <div className="text-sm text-gray-600 mt-1">
                          {repo.description || 'No description'}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">
                          {repo.full_name}
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Documentation Options & Jobs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Documentation Options */}
          <Card>
            <CardHeader>
              <CardTitle>Documentation Options</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                                           <div>
                <label className="text-sm font-medium">Documentation Version</label>
                <div className="w-full p-2 border border-gray-200 rounded-md bg-gray-50 text-gray-600">
                  v1
                </div>
              </div>

              <div>
                <label className="text-sm font-medium">Branch Name (optional)</label>
                <Input
                  placeholder="swe-agent/repo-context-generator-[timestamp]"
                  value={formData.branchName}
                  onChange={(e) => setFormData(prev => ({ ...prev, branchName: e.target.value }))}
                />
                <div className="text-sm text-gray-500 mt-1">Leave empty to use auto-generated name</div>
              </div>

              <div>
                <label className="text-sm font-medium">PR Title</label>
                <Input
                  placeholder="AI Documentation"
                  value={formData.prTitle}
                  onChange={(e) => setFormData(prev => ({ ...prev, prTitle: e.target.value }))}
                />
              </div>

              <div className="flex items-center space-x-4">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.includeExamples}
                    onChange={(e) => setFormData(prev => ({ ...prev, includeExamples: e.target.checked }))}
                  />
                  <span className="text-sm">Include Examples</span>
                </label>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.includeDiagrams}
                    onChange={(e) => setFormData(prev => ({ ...prev, includeDiagrams: e.target.checked }))}
                  />
                  <span className="text-sm">Include Diagrams</span>
                </label>
              </div>

              <div className="relative">
                <Button
                  onClick={generateDocumentation}
                  disabled={true}
                  className="w-full cursor-not-allowed"
                  title="Coming soon"
                >
                  ✨ Generate Context
                </Button>
                <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 bg-black bg-opacity-75 rounded-md transition-opacity">
                  <span className="text-white text-sm">Coming soon</span>
                </div>
              </div>
            </CardContent>
          </Card>




        </div>
      </div>
    </div>
  </div>
  );
};

export default RepoContextGeneratorPage;