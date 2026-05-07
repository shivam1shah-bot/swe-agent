/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { apiClient } from '@/lib/api';
import {
  ExpandIcon,
  ExternalLink,
  FileText,
  GitBranch,
  Loader2,
  Plus,
  Settings,
  Upload,
  X,
  Zap,
} from 'lucide-react';
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MermaidDiagram from '@/components/ui/mermaid-diagram';

interface GatewayCredential {
  key: string;
  value: string;
}

interface ApiToIntegrate {
  name: string;
}

interface GatewayIntegrationParams {
  gateway_name: string;
  method: string;
  custom_method?: string;
  countries_applicable: string[];
  apis_to_integrate: string[];
  credentials: GatewayCredential[];
  encryption_algorithm: string;
  custom_encryption?: string;
  api_links: string[];
  additional_test_cases: number;
  custom_instructions: string;
  integration_notes: string;
  max_iterations: number;
  markdown_doc_path?: string;
  reference_gateway?: string;
  use_switch?: boolean;
}

interface GatewayIntegrationComponentProps {
  onExecute: (params: GatewayIntegrationParams) => Promise<any>;
  isExecuting: boolean;
  result?: any;
}

const GatewayIntegrationComponent: React.FC<GatewayIntegrationComponentProps> = ({
  onExecute,
  isExecuting,
  result,
}) => {
  const navigate = useNavigate();

  // Form state
  const [gatewayName, setGatewayName] = useState('');
  const [method, setMethod] = useState('');
  const [customMethod, setCustomMethod] = useState('');
  const [countries, setCountries] = useState<string[]>([]);
  const [apis, setApis] = useState<ApiToIntegrate[]>([{ name: '' }]);
  const [credentials, setCredentials] = useState<GatewayCredential[]>([{ key: '', value: '' }]);
  const [encryptionAlgorithm, setEncryptionAlgorithm] = useState('aes');
  const [customEncryption, setCustomEncryption] = useState('');
  const [apiLinks, setApiLinks] = useState<string[]>([]);
  const [newApiLink, setNewApiLink] = useState('');
  const [additionalTestCases, setAdditionalTestCases] = useState(0);
  const [customInstructions, setCustomInstructions] = useState('');
  const [integrationNotes, setIntegrationNotes] = useState('');
  const [maxIterations, setMaxIterations] = useState(50);
  const [mdcFile, setMdcFile] = useState<File | null>(null);
  const [referenceGateway, setReferenceGateway] = useState('');
  const [useSwitch, setUseSwitch] = useState(false);

  // UI state
  const [activeTab, setActiveTab] = useState('basic');
  const [showWorkflowDialog, setShowWorkflowDialog] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // File upload state
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Workflow diagram state
  const [diagramData, setDiagramData] = useState<string>('');
  const [isDiagramLoading, setIsDiagramLoading] = useState(true);
  const [diagramError, setDiagramError] = useState<string | null>(null);

  // Fetch workflow diagram on component mount
  useEffect(() => {
    const fetchWorkflowDiagram = async () => {
      try {
        setIsDiagramLoading(true);
        setDiagramError(null);
        
        const response = await apiClient.getWorkflowDiagram('gateway-integrations-common');
        
        if (response.success && response.diagram_syntax) {
          setDiagramData(response.diagram_syntax);
        } else {
          setDiagramError('Failed to load workflow diagram');
        }
      } catch (_error) {
        setDiagramError('Failed to load workflow diagram');
      } finally {
        setIsDiagramLoading(false);
      }
    };

    fetchWorkflowDiagram();
  }, []);

  // Constants
  const paymentMethods = [
    { value: 'card', label: 'Card' },
    { value: 'upi', label: 'UPI' },
    { value: 'pos_qr', label: 'POS QR' },
    { value: 'emandate', label: 'EMandate' },
    { value: 'netbanking', label: 'Netbanking' },
    { value: 'wallet', label: 'Wallet' },
    { value: 'paylater', label: 'PayLater' },
    { value: 'optimizer', label: 'Optimizer' },
    { value: 'custom', label: 'Custom Method' },
  ];

  const countryOptions = [
    { value: 'global', label: 'Global (All Countries)' },
    { value: 'IN', label: 'India' },
    { value: 'MY', label: 'Malaysia' },
    { value: 'SG', label: 'Singapore' },
    { value: 'US', label: 'United States' },
    { value: 'AU', label: 'Australia' },
    { value: 'GB', label: 'United Kingdom' },
    { value: 'CA', label: 'Canada' },
  ];

  const encryptionOptions = [
    { value: 'none', label: 'None' },
    { value: 'aes', label: 'AES' },
    { value: 'rsa', label: 'RSA' },
    { value: 'sha256', label: 'SHA-256' },
    { value: 'custom', label: 'Custom' },
  ];

  // Handlers
  const addApiField = () => {
    setApis([...apis, { name: '' }]);
  };

  const removeApiField = (index: number) => {
    setApis(apis.filter((_, i) => i !== index));
  };

  const updateApiField = (index: number, value: string) => {
    const newApis = [...apis];
    newApis[index].name = value;
    setApis(newApis);
  };

  const addCredentialField = () => {
    setCredentials([...credentials, { key: '', value: '' }]);
  };

  const removeCredentialField = (index: number) => {
    setCredentials(credentials.filter((_, i) => i !== index));
  };

  const updateCredentialField = (index: number, field: 'key' | 'value', value: string) => {
    const newCredentials = [...credentials];
    newCredentials[index][field] = value;
    setCredentials(newCredentials);
  };

  const addApiLink = () => {
    if (newApiLink.trim()) {
      setApiLinks([...apiLinks, newApiLink.trim()]);
      setNewApiLink('');
    }
  };

  const removeApiLink = (index: number) => {
    setApiLinks(apiLinks.filter((_, i) => i !== index));
  };

  // New handlers for file upload and reference gateway
  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!(file.name.endsWith('.mdc') || file.name.endsWith('.md'))) {
      alert('Please select a valid .mdc or .md file');
      return;
    }

    // Just store the file locally, don't upload yet
    setMdcFile(file);
    setUploadedFilePath(null); // Clear any previous upload path
    setUploadError(null); // Clear any previous upload error
  };

  const removeFile = () => {
    setMdcFile(null);
    setUploadedFilePath(null);
    setUploadError(null);
    // Clear the file input
    const fileInput = document.getElementById('mdc-upload') as HTMLInputElement;
    if (fileInput) {
      fileInput.value = '';
    }
  };

  // Upload file when starting integration
  const uploadFileIfNeeded = async (): Promise<string | null> => {
    if (!mdcFile) return null;

    setIsUploading(true);
    setUploadError(null);

    try {
      const uploadResponse = await apiClient.uploadFile(mdcFile);

      if (uploadResponse.success && uploadResponse.file_path) {
        setUploadedFilePath(uploadResponse.file_path);
        return uploadResponse.file_path;
      } else {
        throw new Error(uploadResponse.message || 'Upload failed');
      }
    } catch (_error) {
      console.error('File upload error:', _error);
      setUploadError(_error instanceof Error ? _error.message : 'Failed to upload file');
      throw _error;
    } finally {
      setIsUploading(false);
    }
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!gatewayName.trim()) {
      errors.gateway_name = 'Gateway name is required';
    }

    if (!method) {
      errors.method = 'Payment method is required';
    }

    if (method === 'custom' && !customMethod.trim()) {
      errors.custom_method = 'Custom method name is required';
    }

    if (countries.length === 0) {
      errors.countries = 'At least one country must be selected';
    }

    if (encryptionAlgorithm === 'custom' && !customEncryption.trim()) {
      errors.custom_encryption = 'Custom encryption algorithm is required';
    }

    if (maxIterations < 1 || maxIterations > 100) {
      errors.max_iterations = 'Max iterations must be between 1 and 100';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    let filePath: string | undefined = uploadedFilePath || undefined;

    // Upload file if one is selected but not yet uploaded
    if (mdcFile && !uploadedFilePath) {
      try {
        filePath = (await uploadFileIfNeeded()) || undefined;
      } catch (_error) {
        // File upload failed, don't proceed with integration
        return;
      }
    }

    const params: GatewayIntegrationParams = {
      gateway_name: gatewayName.trim(),
      method: method === 'custom' ? customMethod.trim() : method,
      custom_method: method === 'custom' ? customMethod.trim() : undefined,
      countries_applicable: countries,
      apis_to_integrate: apis.filter(api => api.name.trim()).map(api => api.name.trim()),
      credentials: credentials.filter(cred => cred.key.trim() && cred.value.trim()),
      encryption_algorithm: encryptionAlgorithm === 'custom' ? customEncryption.trim() : encryptionAlgorithm,
      custom_encryption: encryptionAlgorithm === 'custom' ? customEncryption.trim() : undefined,
      api_links: apiLinks,
      additional_test_cases: additionalTestCases,
      custom_instructions: customInstructions.trim(),
      integration_notes: integrationNotes.trim(),
      max_iterations: maxIterations,
      markdown_doc_path: filePath,
      reference_gateway: referenceGateway.trim() || undefined,
      use_switch: useSwitch,
    };

    try {
      await onExecute(params);
    } catch (_error) {
      console.error('Integration failed:', _error);
    }
  };

  const handleCountryChange = (countryValue: string) => {
    if (countries.includes(countryValue)) {
      setCountries(countries.filter(c => c !== countryValue));
    } else {
      setCountries([...countries, countryValue]);
    }
  };

  // Simple tab component
  const TabButton = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 ${active
        ? 'border-blue-500 text-blue-600 bg-blue-50'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Main Form - Full Width */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Gateway Integration Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Tab Navigation */}
            <div className="flex border-b border-gray-200 mb-6">
              <TabButton
                label="Basic Details"
                active={activeTab === 'basic'}
                onClick={() => setActiveTab('basic')}
              />
              <TabButton
                label="Advanced Settings"
                active={activeTab === 'advanced'}
                onClick={() => setActiveTab('advanced')}
              />
              <TabButton
                label="Custom Instructions"
                active={activeTab === 'custom'}
                onClick={() => setActiveTab('custom')}
              />
            </div>

            {/* Basic Details Tab */}
            {activeTab === 'basic' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Gateway Name <span className="text-red-500">*</span></label>
                  <Input
                    placeholder="e.g. Stripe, PayPal, Airwallex"
                    value={gatewayName}
                    onChange={(e) => setGatewayName(e.target.value)}
                    className={formErrors.gateway_name ? 'border-red-500' : ''}
                  />
                  {formErrors.gateway_name && (
                    <p className="text-sm text-red-500">{formErrors.gateway_name}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Payment Method <span className="text-red-500">*</span></label>
                  <Select
                    value={method}
                    onChange={(e) => setMethod(e.target.value)}
                    className={formErrors.method ? 'border-red-500' : ''}
                  >
                    <option value="" disabled>Select payment method</option>
                    {paymentMethods.map((pm) => (
                      <option key={pm.value} value={pm.value}>
                        {pm.label}
                      </option>
                    ))}
                  </Select>
                  {formErrors.method && (
                    <p className="text-sm text-red-500">{formErrors.method}</p>
                  )}

                  {method === 'custom' && (
                    <div className="mt-2">
                      <Input
                        placeholder="Enter custom payment method"
                        value={customMethod}
                        onChange={(e) => setCustomMethod(e.target.value)}
                        className={formErrors.custom_method ? 'border-red-500' : ''}
                      />
                      {formErrors.custom_method && (
                        <p className="text-sm text-red-500">{formErrors.custom_method}</p>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Countries Applicable <span className="text-red-500">*</span></label>
                  <div className="space-y-2 max-h-48 overflow-y-auto border rounded-md p-3">
                    {countryOptions.map((country) => (
                      <label key={country.value} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={countries.includes(country.value)}
                          onChange={() => handleCountryChange(country.value)}
                          className="rounded border-gray-300"
                        />
                        <span className="text-sm">{country.label}</span>
                      </label>
                    ))}
                  </div>
                  {formErrors.countries && (
                    <p className="text-sm text-red-500">{formErrors.countries}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">APIs to Integrate</label>
                  <div className="space-y-2">
                    {apis.map((api, index) => (
                      <div key={index} className="flex gap-2">
                        <Input
                          placeholder="e.g. Pay Init, Pay Verify, Refund"
                          value={api.name}
                          onChange={(e) => updateApiField(index, e.target.value)}
                          className="flex-1"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeApiField(index)}
                          disabled={apis.length === 1}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addApiField}
                      className="flex items-center gap-1"
                    >
                      <Plus className="w-4 h-4" />
                      Add API
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Advanced Settings Tab */}
            {activeTab === 'advanced' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Reference Gateway</label>
                  <Input
                    placeholder="e.g. Stripe, PayPal (optional - use as template)"
                    value={referenceGateway}
                    onChange={(e) => setReferenceGateway(e.target.value)}
                  />
                  <p className="text-xs text-gray-500">
                    Optional: Specify a reference gateway to use as a template for this integration
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Upload Documentation (.mdc or .md file)</label>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <input
                        type="file"
                        accept=".mdc,.md,text/markdown,text/plain"
                        onChange={handleFileSelection}
                        className="hidden"
                        id="mdc-upload"
                        disabled={isUploading}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => document.getElementById('mdc-upload')?.click()}
                        className="flex items-center gap-2"
                        disabled={isUploading}
                      >
                        {isUploading ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Uploading...
                          </>
                        ) : (
                          <>
                            <Upload className="w-4 h-4" />
                            Upload Documentation
                          </>
                        )}
                      </Button>
                      {mdcFile && !uploadError && (
                        <div className="flex items-center gap-2 bg-blue-50 px-3 py-1 rounded">
                          <FileText className="w-4 h-4 text-blue-600" />
                          <span className="text-sm text-blue-700">
                            {mdcFile.name}
                            {uploadedFilePath ? ' (uploaded)' : ''}
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={removeFile}
                            disabled={isUploading}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                    {uploadError && (
                      <div className="flex items-center gap-2 bg-red-50 px-3 py-1 rounded">
                        <X className="w-4 h-4 text-red-600" />
                        <span className="text-sm text-red-700">Upload failed: {uploadError}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setUploadError(null)}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    )}
                    <p className="text-xs text-gray-500">
                      Upload gateway documentation in .mdc or .md format (optional)
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Gateway Credentials (Key-Value Pairs)</label>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {credentials.map((cred, index) => (
                      <div key={index} className="flex gap-2">
                        <Input
                          placeholder="Key"
                          value={cred.key}
                          onChange={(e) => updateCredentialField(index, 'key', e.target.value)}
                          className="flex-1"
                        />
                        <Input
                          placeholder="Value"
                          value={cred.value}
                          onChange={(e) => updateCredentialField(index, 'value', e.target.value)}
                          className="flex-1"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeCredentialField(index)}
                          disabled={credentials.length === 1}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addCredentialField}
                      className="flex items-center gap-1"
                    >
                      <Plus className="w-4 h-4" />
                      Add Credential
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Encryption/Decryption Algorithm</label>
                  <Select value={encryptionAlgorithm} onChange={(e) => setEncryptionAlgorithm(e.target.value)}>
                    {encryptionOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>

                  {encryptionAlgorithm === 'custom' && (
                    <div className="mt-2">
                      <Input
                        placeholder="Specify custom encryption algorithm"
                        value={customEncryption}
                        onChange={(e) => setCustomEncryption(e.target.value)}
                        className={formErrors.custom_encryption ? 'border-red-500' : ''}
                      />
                      {formErrors.custom_encryption && (
                        <p className="text-sm text-red-500">{formErrors.custom_encryption}</p>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">API Documentation Links</label>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Add API documentation link"
                      value={newApiLink}
                      onChange={(e) => setNewApiLink(e.target.value)}
                      className="flex-1"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addApiLink}
                      disabled={!newApiLink.trim()}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>

                  {apiLinks.length > 0 && (
                    <div className="space-y-2 max-h-32 overflow-y-auto">
                      {apiLinks.map((link, index) => (
                        <div key={index} className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                          <ExternalLink className="w-4 h-4 text-gray-500" />
                          <a
                            href={link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline flex-1 truncate"
                          >
                            {link}
                          </a>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => removeApiLink(index)}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Additional Test Cases</label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={additionalTestCases}
                    onChange={(e) => setAdditionalTestCases(parseInt(e.target.value) || 0)}
                    min="0"
                    max="10"
                  />
                  <p className="text-xs text-gray-500">Number of additional test cases to include</p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Iterations</label>
                  <Input
                    type="number"
                    placeholder="50"
                    value={maxIterations}
                    onChange={(e) => setMaxIterations(parseInt(e.target.value) || 50)}
                    min="1"
                    max="100"
                    className={formErrors.max_iterations ? 'border-red-500' : ''}
                  />
                  {formErrors.max_iterations && (
                    <p className="text-sm text-red-500">{formErrors.max_iterations}</p>
                  )}
                  <p className="text-xs text-gray-500">Maximum number of workflow iterations (1-100)</p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Use Switch</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="use-switch"
                      checked={useSwitch}
                      onChange={(e) => setUseSwitch(e.target.checked)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label htmlFor="use-switch" className="text-sm text-gray-700">
                      Enable switch for this integration.
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* Custom Instructions Tab */}
            {activeTab === 'custom' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Custom Integration Instructions</label>
                  <textarea
                    className="w-full p-3 border border-gray-300 rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    rows={8}
                    placeholder="Enter any custom instructions or specific requirements for this gateway integration that don't fit in the standard fields. For example, special handling of responses, custom headers, retry strategies, etc."
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Integration Notes</label>
                  <textarea
                    className="w-full p-3 border border-gray-300 rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    rows={4}
                    placeholder="Additional notes or considerations for the integration team"
                    value={integrationNotes}
                    onChange={(e) => setIntegrationNotes(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* Success Message */}
            {result?.status === 'queued' && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                <p className="text-green-700 text-sm">
                  Gateway integration initiated! Monitor progress in the{' '}
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

            <div className="mt-6">
              <Button
                onClick={handleSubmit}
                disabled={isExecuting || isUploading}
                className="w-full"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Uploading file...
                  </>
                ) : isExecuting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Processing Integration...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 mr-2" />
                    Start Integration
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Workflow Diagram Section */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="w-5 h-5" />
              LangGraph Workflow Diagram
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-4">
              <Dialog open={showWorkflowDialog} onOpenChange={setShowWorkflowDialog}>
                <Button variant="outline" size="sm" onClick={() => setShowWorkflowDialog(true)}>
                  <ExpandIcon className="w-4 h-4 mr-2" />
                  View Full Diagram
                </Button>
                <DialogContent className="max-w-4xl">
                  <DialogHeader>
                    <DialogTitle>Gateway Integration Workflow</DialogTitle>
                  </DialogHeader>
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <MermaidDiagram
                      content={diagramData}
                      isLoading={isDiagramLoading}
                      error={diagramError}
                      className="min-h-[600px]"
                    />
                  </div>
                </DialogContent>
              </Dialog>
            </div>

            <div className="bg-gray-50 rounded-lg p-4 mb-4">
              <MermaidDiagram
                content={diagramData}
                isLoading={isDiagramLoading}
                error={diagramError}
                className="min-h-[400px]"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default GatewayIntegrationComponent;