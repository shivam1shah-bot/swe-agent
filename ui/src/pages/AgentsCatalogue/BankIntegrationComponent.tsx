/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Select } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle, XCircle, GitBranch, Code, Database, Workflow, Upload, FileText } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface BankIntegrationFormData {
  bank_name: string;
  version: string;
  branch_name?: string;
  enable_integrations_go: boolean;
  enable_fts: boolean;
  enable_payouts: boolean;
  enable_xbalance: boolean;
  enable_terminals: boolean;
  enable_kube_manifests: boolean;
  max_iterations: number;
  max_retries: number;
  bank_doc?: File;
}

export default function BankIntegrationComponent() {
  const [formData, setFormData] = useState<BankIntegrationFormData>({
    bank_name: '',
    version: 'v3',
    branch_name: '',
    enable_integrations_go: true,
    enable_fts: true,
    enable_payouts: true,
    enable_xbalance: true,
    enable_terminals: true,
    enable_kube_manifests: true,
    max_iterations: 50,
    max_retries: 3,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const handleInputChange = (field: keyof BankIntegrationFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.name.toLowerCase().endsWith('.md')) {
        setError('Please upload a .md (Markdown) file');
        return;
      }
      
      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setError('File size must be less than 5MB');
        return;
      }
      
      setUploadedFile(file);
      setError(null);
    }
  };

  const removeFile = () => {
    setUploadedFile(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.bank_name.trim()) {
      setError('Bank name is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.triggerBankIntegration({
        ...formData,
        bank_doc: uploadedFile
      });
      setResult(response);
    } catch (err: any) {
      setError(err.message || 'Failed to start bank integration');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getEnabledServicesCount = () => {
    return [
      formData.enable_integrations_go,
      formData.enable_fts,
      formData.enable_payouts,
      formData.enable_xbalance,
      formData.enable_terminals,
      formData.enable_kube_manifests
    ].filter(Boolean).length;
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Bank Integration Generator</h1>
        <p className="text-gray-600">
          Automate bank integration across multiple services: integrations-go, FTS, Payouts, X-Balance, Terminals, and Kube-manifests
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Form */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code className="w-5 h-5" />
                Bank Integration Configuration
              </CardTitle>
              <CardDescription>
                Configure the bank integration parameters and select target services
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Bank Details */}
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="bank_name">Bank Name *</Label>
                    <Input
                      id="bank_name"
                      placeholder="Enter bank name (e.g., sbi, icici, hdfc)"
                      value={formData.bank_name}
                      onChange={(e) => handleInputChange('bank_name', e.target.value)}
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="version">Version</Label>
                      <Select 
                        value={formData.version} 
                        onChange={(e) => handleInputChange('version', e.target.value)}
                      >
                        <option value="v1">v1</option>
                        <option value="v2">v2</option>
                        <option value="v3">v3</option>
                      </Select>
                    </div>

                    <div>
                      <Label htmlFor="branch_name">Custom Branch Name (Optional)</Label>
                      <Input
                        id="branch_name"
                        placeholder="Auto-generated if empty"
                        value={formData.branch_name}
                        onChange={(e) => handleInputChange('branch_name', e.target.value)}
                      />
                    </div>
                  </div>
                </div>

                {/* Bank Documentation Upload */}
                <div className="space-y-4">
                  <Label className="text-base font-semibold">Bank Documentation</Label>
                  <div className="space-y-3">
                    {!uploadedFile ? (
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                        <input
                          type="file"
                          accept=".md"
                          onChange={handleFileUpload}
                          className="hidden"
                          id="bank-doc-upload"
                        />
                        <label
                          htmlFor="bank-doc-upload"
                          className="cursor-pointer flex flex-col items-center space-y-2"
                        >
                          <Upload className="w-8 h-8 text-gray-400" />
                          <div className="text-sm text-gray-600">
                            <span className="font-medium text-blue-600 hover:text-blue-500">
                              Click to upload
                            </span>
                            {' '}or drag and drop
                          </div>
                          <div className="text-xs text-gray-500">
                            Markdown files (.md) only, up to 5MB
                          </div>
                        </label>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
                        <div className="flex items-center space-x-3">
                          <FileText className="w-5 h-5 text-blue-600" />
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {uploadedFile.name}
                            </div>
                            <div className="text-xs text-gray-500">
                              {(uploadedFile.size / 1024).toFixed(1)} KB
                            </div>
                          </div>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={removeFile}
                          className="text-red-600 hover:text-red-700"
                        >
                          Remove
                        </Button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Service Selection */}
                <div className="space-y-4">
                  <Label className="text-base font-semibold">Target Services ({getEnabledServicesCount()} selected)</Label>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="integrations_go"
                        checked={formData.enable_integrations_go}
                        onChange={(e) => handleInputChange('enable_integrations_go', e.target.checked)}
                      />
                      <Label htmlFor="integrations_go" className="flex items-center gap-2">
                        <GitBranch className="w-4 h-4" />
                        Integrations-Go
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="fts"
                        checked={formData.enable_fts}
                        onChange={(e) => handleInputChange('enable_fts', e.target.checked)}
                      />
                      <Label htmlFor="fts" className="flex items-center gap-2">
                        <Database className="w-4 h-4" />
                        FTS (Fund Transfer)
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="payouts"
                        checked={formData.enable_payouts}
                        onChange={(e) => handleInputChange('enable_payouts', e.target.checked)}
                      />
                      <Label htmlFor="payouts" className="flex items-center gap-2">
                        <Workflow className="w-4 h-4" />
                        Payouts
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="xbalance"
                        checked={formData.enable_xbalance}
                        onChange={(e) => handleInputChange('enable_xbalance', e.target.checked)}
                      />
                      <Label htmlFor="xbalance" className="flex items-center gap-2">
                        <Database className="w-4 h-4" />
                        X-Balance
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="terminals"
                        checked={formData.enable_terminals}
                        onChange={(e) => handleInputChange('enable_terminals', e.target.checked)}
                      />
                      <Label htmlFor="terminals" className="flex items-center gap-2">
                        <Code className="w-4 h-4" />
                        Terminals
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Checkbox 
                        id="kube_manifests"
                        checked={formData.enable_kube_manifests}
                        onChange={(e) => handleInputChange('enable_kube_manifests', e.target.checked)}
                      />
                      <Label htmlFor="kube_manifests" className="flex items-center gap-2">
                        <Code className="w-4 h-4" />
                        Kube-manifests
                      </Label>
                    </div>
                  </div>
                </div>

                {/* Advanced Options */}
                <div className="space-y-4">
                  <Label className="text-base font-semibold">Advanced Options</Label>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="max_iterations">Max Iterations</Label>
                      <Input
                        id="max_iterations"
                        type="number"
                        min="1"
                        max="100"
                        value={formData.max_iterations}
                        onChange={(e) => handleInputChange('max_iterations', parseInt(e.target.value))}
                      />
                    </div>

                    <div>
                      <Label htmlFor="max_retries">Max Retries</Label>
                      <Input
                        id="max_retries"
                        type="number"
                        min="1"
                        max="10"
                        value={formData.max_retries}
                        onChange={(e) => handleInputChange('max_retries', parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                </div>

                {/* Submit Button */}
                <Button 
                  type="submit" 
                  className="w-full" 
                  disabled={isSubmitting || getEnabledServicesCount() === 0}
                  size="lg"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Starting Integration...
                    </>
                  ) : (
                    `Start Bank Integration (${getEnabledServicesCount()} services)`
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Service Overview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Service Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className={`flex items-center gap-2 ${formData.enable_integrations_go ? 'text-green-600' : 'text-gray-400'}`}>
                <div className={`w-2 h-2 rounded-full ${formData.enable_integrations_go ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm">Integrations-Go</span>
              </div>
              <div className={`flex items-center gap-2 ${formData.enable_fts ? 'text-green-600' : 'text-gray-400'}`}>
                <div className={`w-2 h-2 rounded-full ${formData.enable_fts ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm">Fund Transfer Service</span>
              </div>
              <div className={`flex items-center gap-2 ${formData.enable_payouts ? 'text-green-600' : 'text-gray-400'}`}>
                <div className={`w-2 h-2 rounded-full ${formData.enable_payouts ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm">Payouts Service</span>
              </div>
              <div className={`flex items-center gap-2 ${formData.enable_xbalance ? 'text-green-600' : 'text-gray-400'}`}>
                <div className={`w-2 h-2 rounded-full ${formData.enable_xbalance ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm">X-Balance Service</span>
              </div>
              <div className={`flex items-center gap-2 ${formData.enable_terminals ? 'text-green-600' : 'text-gray-400'}`}>
                <div className={`w-2 h-2 rounded-full ${formData.enable_terminals ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm">Terminals Service</span>
              </div>
              <div className={`flex items-center gap-2 ${formData.enable_kube_manifests ? 'text-green-600' : 'text-gray-400'}`}>
                <div className={`w-2 h-2 rounded-full ${formData.enable_kube_manifests ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm">Kube-manifests Service</span>
              </div>
            </CardContent>
          </Card>

          {/* Error Display */}
          {error && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Result Display */}
          {result && (
            <Alert variant={result.status === 'queued' ? 'default' : result.status === 'completed' ? 'default' : 'destructive'}>
              {result.status === 'queued' && <CheckCircle className="h-4 w-4" />}
              {result.status === 'completed' && <CheckCircle className="h-4 w-4" />}
              {result.status === 'failed' && <XCircle className="h-4 w-4" />}
              <AlertDescription>
                <div className="space-y-2">
                  <p className="font-semibold">{result.message}</p>
                  {result.task_id && (
                    <p className="text-sm">Task ID: {result.task_id}</p>
                  )}
                  {result.pr_urls && result.pr_urls.length > 0 && (
                    <div>
                      <p className="text-sm font-semibold">Pull Requests:</p>
                      {result.pr_urls.map((url: string, index: number) => (
                        <a 
                          key={index}
                          href={url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 text-sm block"
                        >
                          PR #{index + 1}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* Help Text */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">How it works</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-600 space-y-2">
              <p>1. Configure bank details and target services</p>
              <p>2. AI agents generate code across all services</p>
              <p>3. Code is validated and tested automatically</p>
              <p>4. Pull requests are created for review</p>
              <p>5. Monitor progress via task status updates</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
