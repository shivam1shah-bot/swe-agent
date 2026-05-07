/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { ArrowLeft } from 'lucide-react';
import { apiClient } from '@/lib/api';

export const QCCOnboardingPage: React.FC = () => {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    repositoryName: '',
    branchName: '',
    prTitle: 'QCC Onboarding'
  });

  const generateQCCAnalysis = async () => {
    if (!formData.repositoryName.trim()) {
      setError('Please enter a repository name');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    const requestData: any = {
      repo_path: `https://github.com/razorpay/${formData.repositoryName.trim()}`
    };

    if (formData.branchName) {
      requestData.branch_name = formData.branchName;
    }

    if (formData.prTitle) {
      requestData.pr_title = formData.prTitle;
    }

    try {
      // Use the same pattern as other micro frontend services
      const result = await apiClient.executeMicroFrontendService('qcc-onboarding', {
        parameters: requestData
      });

      // Check for successful status and task_id (API returns status, not success)
      if ((result.status === 'queued' || result.status === 'completed') && result.task_id) {
        // Reset form
        setFormData(prev => ({
          ...prev,
          repositoryName: '',
          branchName: ''
        }));
        setSuccess(true);
      } else {
        // Handle different status cases or missing task_id
        const errorMessage = result.message || `Unexpected status: ${result.status}` || 'Unknown error occurred';
        setError(errorMessage);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`QCC analysis failed: ${errorMessage}`);
      console.error('Error submitting QCC analysis job:', err);
    } finally {
      setLoading(false);
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
              <h1 className="text-2xl font-bold text-gray-900">QCC Onboarding</h1>
              <p className="text-gray-600">
                This agent helps users understand and fulfill the necessary conditions for onboarding new services into Quality Code Coverage (QCC).
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
          {/* Repository Input */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle>Repository</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Organization</label>
                  <div className="w-full p-2 border border-gray-200 rounded-md bg-gray-50 text-gray-600">
                    razorpay
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium">Repository Name</label>
                  <Input
                    placeholder="e.g., scrooge, pg-router"
                    value={formData.repositoryName}
                    onChange={(e) => setFormData(prev => ({ ...prev, repositoryName: e.target.value }))}
                  />
                  <div className="text-sm text-gray-500 mt-1">Enter the repository name (without organization prefix)</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* QCC Analysis Options */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>QCC Analysis Options</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Selected Repository</label>
                  <div className="w-full p-2 border border-gray-200 rounded-md bg-gray-50 text-gray-600">
                    {formData.repositoryName ? `razorpay/${formData.repositoryName}` : 'No repository entered'}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium">Branch Name (optional)</label>
                  <Input
                    placeholder="qcc-onboarding-[timestamp]"
                    value={formData.branchName}
                    onChange={(e) => setFormData(prev => ({ ...prev, branchName: e.target.value }))}
                  />
                  <div className="text-sm text-gray-500 mt-1">Leave empty to use auto-generated name</div>
                </div>

                <div>
                  <label className="text-sm font-medium">PR Title</label>
                  <Input
                    placeholder="QCC Onboarding"
                    value={formData.prTitle}
                    onChange={(e) => setFormData(prev => ({ ...prev, prTitle: e.target.value }))}
                  />
                </div>

                {/* Success Display */}
                {success && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="text-green-700 text-sm">
                      QCC analysis has been initiated! You can now view the status in the{' '}
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

                <Button
                  onClick={generateQCCAnalysis}
                  disabled={!formData.repositoryName.trim() || loading}
                  className="w-full"
                >
                  {loading ? 'Analyzing...' : '🎯 Generate QCC Analysis'}
                </Button>
              </CardContent>
            </Card>


          </div>
        </div>
      </div>
    </div>
  );
};

export default QCCOnboardingPage; 