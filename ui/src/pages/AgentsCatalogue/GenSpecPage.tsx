/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient } from '@/lib/api';

// Icons (inline SVGs to avoid dependency issues)
const AlertCircle = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
);
const FileText = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
);
const Code = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
);
const Database = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
);
const Zap = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
);
const CheckCircle2 = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
);

interface GenSpecTask {
  prd_document: string;
  project_name: string;
  problem_statement: string;
  architecture_diagram: string;
  api_documentation: string;
  additional_parameters: string;
  mermaid_code: string;
  arch_diagram_text_description: string;
  text_description: string;
  titleConfirmed: string;
  problemStatementConfirmed: string;
  arch_input_method: string;
  api_input_method: string;
  title: string;
}

interface ParsedData {
  prd?: {
    title?: string;
    problem_statement?: string;
    sections?: {
      user_stories?: string;
      requirements?: string;
    };
  },
  nfrlist?: string[];
  evaluated_approaches_timeout?: number;
  evaluated_approaches_chunks?: boolean;
  evaluated_approaches_count?: number
  title?: string;
  problem_statement?: string;
  service_names?: string[];
  output_format?: string;
  architecture?: {
    type?: string;
    content?: string;
    file_name?: string;
    generated_flowchart?: string;
    components?: string[];
    relationships?: string[];
    description?: string;
  }
  api_documentation?: {
    type?: string;
    content?: string;
    file_name?: string;
    structured?: boolean;
    format?: string;
    auto_generate?: boolean;
  }
  additional_parameters?: Record<string, unknown>,
  database?: {
    nfrlist?: string[];
    acid_requirements?: string;
    join_complexity?: string;
    failure_points_details?: string;
    transaction_boundaries_details?: string;
    storage_requirement?: string;
    storage_growth_rate?: string;
    iops_level?: string;
    backup_retention?: string;
    read_replicas?: string;
    include_performance_reqs?: boolean;
    latency_reqs?: string;
    throughput_reqs?: string;
  }
  architecture_diagram?: Record<string, unknown>;
}

interface ProjectData {
  parsed_data: ParsedData;
}

export function GenSpecPage() {
  const [task, setTask] = useState<GenSpecTask>({
    prd_document: '',
    project_name: '',
    problem_statement: '',
    architecture_diagram: '',
    api_documentation: '',
    additional_parameters: '',
    mermaid_code: '',
    arch_diagram_text_description: '',
    text_description: '',
    titleConfirmed: '',
    problemStatementConfirmed: '',
    arch_input_method: '',
    api_input_method: '',
    title: '',
  });
  const [file] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasPRD, setHasPRD] = useState<boolean | null>(null);
  const [projectData, setProjectData] = useState<ProjectData>({
    parsed_data: {
      evaluated_approaches_count: 1,
      nfrlist: [],
      output_format: 'both',
      evaluated_approaches_timeout: 3600,
      evaluated_approaches_chunks: true,
    },
  });
  const [, setAPIDocFileContent] = useState<string | null>(null);

  // Check for parsed Google Doc data on component mount
  useEffect(() => {
    const parsedData = sessionStorage.getItem('parsedGoogleDocData');
    if (parsedData) {
      try {
        let parsedPRDData = JSON.parse(parsedData);
        
        if (parsedPRDData?.parsed_data && typeof parsedPRDData.parsed_data === 'object') {
          parsedPRDData = parsedPRDData.parsed_data;
        }
        
        setProjectData((prevData: any) => ({
          ...prevData,
          parsed_data: {
            ...prevData.parsed_data,
            prd: parsedPRDData,
          },
        }));
        
        const title = parsedPRDData?.title || parsedPRDData?.parsed_data?.title;
        const problemStatement = parsedPRDData?.sections?.problem_statement 
          || parsedPRDData?.sections?.raw_content 
          || parsedPRDData?.problem_statement
          || parsedPRDData?.parsed_data?.sections?.problem_statement;
        const currentArchitecture = parsedPRDData?.architecture?.content 
          || parsedPRDData?.sections?.current_architecture
          || parsedPRDData?.parsed_data?.architecture?.content;
        
        if (title && title.trim() !== '') {
          setTask((prevTask) => ({ ...prevTask, title }));
          setProjectData((prevData: ProjectData) => ({
            ...prevData,
            parsed_data: {
              ...prevData.parsed_data,
              title: title,
            },
          }));
        }
      
        if (problemStatement && problemStatement.trim() !== '') {
          setTask((prevTask) => ({ ...prevTask, problem_statement: problemStatement }));
          setProjectData((prevData: ProjectData) => ({
            ...prevData,
            parsed_data: {
              ...prevData.parsed_data,
              problem_statement: problemStatement,
            },
          }));
        }

        if (currentArchitecture) {
          setImageData(currentArchitecture);
          setProjectData((prevData: ProjectData) => ({
            ...prevData,
            parsed_data: {
              ...prevData.parsed_data,
              architecture: {
                type: 'image',
                content: currentArchitecture,
                file_name: 'architecture_diagram.png',
              },
            },
          }));
        }
        
        sessionStorage.removeItem('parsedGoogleDocData');
      } catch (error) {
        console.error('Error parsing stored Google Doc data:', error);
        sessionStorage.removeItem('parsedGoogleDocData');
      }
    }
  }, []);

  const [archInputMethod, setArchInputMethod] = useState('');
  const [apiDocMethod, setApiDocMethod] = useState('');
  const [includeDbSchema, setIncludeDbSchema] = useState(false);
  const [prdInputMethod, setPrdInputMethod] = useState('');
  const [specStatus, setSpecStatus] = useState('pending');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imageData, setImageData] = useState<string | null>(null);
  const [isImageConfirmed, setIsImageConfirmed] = useState<boolean>(false);
  const [prdUrlError, setPrdUrlError] = useState<string | null>(null);

  const saveMermaidDiagram = (mermaidCode: string) => {
    const architectureData = {
      type: "mermaid",
      content: mermaidCode,
      file_name: "architecture_diagram.mmd"
    };
    setProjectData({ ...projectData, 
      parsed_data: {
        ...projectData.parsed_data,
        architecture: architectureData
      }
    });
  };

  const generateFlowchart = async (textDescription: string) => {
    try {
      const response = await apiClient.analyzeTextArchitecture(textDescription);
      const flowchartResult = response.data;
      const architectureData = {
        type: "text_with_flowchart",
        content: textDescription,
        file_name: "architecture_description.txt",
        generated_flowchart: flowchartResult.mermaid_diagram,
        components: flowchartResult.components,
        relationships: flowchartResult.relationships,
        description: flowchartResult.description
      };
      setProjectData({ ...projectData, 
        parsed_data: {
          ...projectData.parsed_data,
          architecture: architectureData
        }
      });
    } catch (error) {
      console.error("Could not generate flowchart:", error);
      const architectureData = {
        type: "text",
        content: textDescription,
        file_name: "architecture_description.txt"
      };
      setProjectData({ ...projectData, 
        parsed_data: {
          ...projectData.parsed_data,
          architecture: architectureData
        }
      });
    }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      const filePath = selectedFile.name.toLowerCase();
      const ext = filePath.substring(filePath.lastIndexOf('.'));
      if (['.png', '.jpg', '.jpeg', '.gif'].includes(ext)) {
        const parsedDiagram = await parseFile("", selectedFile, "image");
        setProjectData((prevData: any) => ({
          ...prevData,
          parsed_data: {
            ...prevData.parsed_data,
            architecture: parsedDiagram,
          },
        }));
      } else {
        console.error('Please select a valid image file.');
      }
    } else {
      console.error('No file selected.');
    }
  };

  const parseFile = async (googleDocLink: string, file: File | null, type: string) => {
    if (googleDocLink) {
      try {
        sessionStorage.setItem('pendingGoogleDocUrl', googleDocLink);
        const authResponse = await apiClient.getAuthUrl();
        const responseData = authResponse?.data as any;
        const authUrl: string | undefined = 
          responseData?.auth_url 
          || responseData?.metadata?.auth_url 
          || responseData?.agent_result?.auth_url
          || (authResponse as any)?.auth_url;
        
        if (!authUrl || authUrl.trim() === '') {
          throw new Error('Invalid response from getAuthUrl: auth_url not found');
        }
        
        window.location.href = authUrl;
        return null;
      } catch (error) {
        console.error('Error in Google Doc parsing:', error);
        alert('Failed to initiate Google authentication. Please check the console for details.');
        throw error;
      }
    }
    else if (file) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('input_type', type);
      formData.append('filename', file.name);
      const response = await apiClient.parseContent(formData);
      return response.data;
    }
  };

  const handleAPIDocFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const fileContent = e.target?.result as string;
        setAPIDocFileContent(fileContent);
        handleApiDocumentation('file', fileContent);
      };
      reader.readAsText(selectedFile);
    } else {
      console.error('Please select a valid file.');
    }
  };

  const handleApiDocumentation = (apiInputMethod: string, fileContent: string | null = null) => {
    if (apiInputMethod === 'auto') {
      setProjectData((prevData: any) => ({
        ...prevData,
        parsed_data: {
          ...prevData.parsed_data,
          api_documentation: {
            type: 'auto_generated',
            content: 'API documentation will be auto-generated based on problem statement, architecture, and evaluated approaches.',
            file_name: 'api_documentation_auto.txt',
            structured: true,
            format: 'structured_endpoints',
            auto_generate: true,
          },
        },
      })); 
      return;
    } else if(apiInputMethod === 'none') {
      setProjectData((prevData: any) => ({
        ...prevData,
        parsed_data: {
          ...prevData.parsed_data,
          api_documentation: {
            type: 'none',
            content: '',
            file_name: '',
            structured: false,
            format: '',
            auto_generate: false,
          },
        },
      }));
      return;
    } else if(apiInputMethod === 'file' && fileContent) {
      setProjectData((prevData: any) => ({
        ...prevData,
        parsed_data: {
          ...prevData.parsed_data,
          api_documentation: {
            type: 'user_provided',
            content: fileContent,
            file_name: file ? file.name : '',
            structured: false,
            format: 'text',
            auto_generate: false,
          },
        },
      }));
    }
  };

  const handleAdditionalParamsChange = (key: string, value: any) => {
    setProjectData((prevData: ProjectData) => ({
      ...prevData,
      parsed_data: {
        ...prevData.parsed_data,
        [key]: value,
      },
    }));
  };

  const handleDBDataParamsChange = (key: string, value: any) => {
    setProjectData((prevData: ProjectData) => ({
      ...prevData,
      parsed_data: { ...prevData.parsed_data, 
        database: {
          ...prevData.parsed_data.database,
          [key]: value,
        },
      },
    }));
  };

  const confirmAndGenerate = async () => {
    const confirm = window.confirm("Do you want to generate the specification with these details?");
    if (confirm) {
      try {
        setSpecStatus('processing');
        setError(null);
        
        if (!projectData.parsed_data.title || !projectData.parsed_data.problem_statement) {
          throw new Error('Project title and problem statement are required');
        }

        const response = await apiClient.executeGenSpecTask(projectData.parsed_data as any);
        
        if (response.task_id) {
          setSpecStatus('queued');
          console.log('Task queued with ID:', response.task_id);
          return {
            status: 'success',
            message: `Task queued successfully. Task ID: ${response.task_id}`,
            task_id: response.task_id
          };
        } else {
          setSpecStatus('ready');
          console.log('Specification generated synchronously');
          return {
            status: 'success',
            message: response.message || 'Specification generated successfully',
            task_id: null
          };
        }
      } catch (error) {
        console.error('Error executing GenSpec task:', error);
        setSpecStatus('failed');
        setError(error instanceof Error ? error.message : 'Failed to generate specification');
        return {
          status: 'error',
          message: error instanceof Error ? error.message : 'Failed to generate specification',
        };
      }
    } else {
      return {
        status: 'cancelled',
        message: 'Task cancelled by user',
      };
    }
  };

  const handleArchInputChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setArchInputMethod(event.target.value);
  };

  const handleApiDocChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const method = event.target.value;
    setApiDocMethod(method);

    if (method === 'auto') {
      handleApiDocumentation('auto');
    } else if (method === 'none') {
      handleApiDocumentation('none');
    }
  };

  const handleDbSchemaChange = (checked: boolean) => {
    setIncludeDbSchema(checked);
  };

  const handlePRDFileChange = async () => {
    if (selectedFile) {
      const filePath = selectedFile.name.toLowerCase();
      const ext = filePath.substring(filePath.lastIndexOf('.'));
      if (['.md'].includes(ext)) {
        const parsedPRDFileData = await parseFile("", selectedFile, "prd");
        setProjectData((prevData: any) => ({
          ...prevData,
          parsed_data: {
            ...prevData.parsed_data,
            prd: parsedPRDFileData,
          },
        }));
        const title = parsedPRDFileData?.title;
        const problemStatement = parsedPRDFileData?.sections?.problem_statement;
        const currentArchitecture = parsedPRDFileData?.architecture?.content || parsedPRDFileData?.sections?.current_architecture;
        if (title && title.trim() !== '') {
          setTask((prevTask) => ({ ...prevTask, title }));
          setProjectData((prevData: ProjectData) => ({
            ...prevData,
            parsed_data: {
              ...prevData.parsed_data,
              title: title,
            },
          }));
        }
      
        if (problemStatement && problemStatement.trim() !== '') {
          setTask((prevTask) => ({ ...prevTask, problem_statement: problemStatement }));
          setProjectData((prevData: ProjectData) => ({
            ...prevData,
            parsed_data: {
              ...prevData.parsed_data,
              problem_statement: problemStatement,
            },
          }));
        }

        if (currentArchitecture) {
          setImageData(currentArchitecture);
          setProjectData((prevData: ProjectData) => ({
            ...prevData,
            parsed_data: {
              ...prevData.parsed_data,
              architecture: {
                type: 'image',
                content: currentArchitecture,
                file_name: 'architecture_diagram.png',
              },
            },
          }));
        }
      }
    } else {
      console.error('Please select a valid file.');
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setSelectedFile(file || null);
  };

  const validateGoogleDocUrl = (url: string): { isValid: boolean; error?: string } => {
    if (!url.trim()) {
      return { isValid: false, error: 'Please enter a Google Doc URL' };
    }

    try {
      const urlObj = new URL(url);
      
      if (!urlObj.hostname.includes('docs.google.com')) {
        return { 
          isValid: false, 
          error: 'URL must be from docs.google.com (e.g., https://docs.google.com/document/d/...)'
        };
      }

      if (!urlObj.pathname.includes('/document/')) {
        return { 
          isValid: false, 
          error: 'URL must be a Google Document (not Sheets or Slides)'
        };
      }

      const docIdMatch = urlObj.pathname.match(/\/d\/([a-zA-Z0-9-_]+)/);
      if (!docIdMatch || !docIdMatch[1]) {
        return { 
          isValid: false, 
          error: 'Invalid Google Doc URL format. Expected format: https://docs.google.com/document/d/DOCUMENT_ID/...'
        };
      }

      return { isValid: true };

    } catch (_e) {
      return { 
        isValid: false, 
        error: 'Invalid URL format. Please enter a valid Google Doc URL'
      };
    }
  };

  const handlePrdInputChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setPrdInputMethod(event.target.value);
    setPrdUrlError(null);
  };

  const handlePRDUrlChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const googleDocUrl = event.target.value;
    setTask({ ...task, prd_document: googleDocUrl });
    
    setPrdUrlError(null);

    if (googleDocUrl.trim()) {
      const validation = validateGoogleDocUrl(googleDocUrl);
      
      if (!validation.isValid) {
        setPrdUrlError(validation.error || 'Invalid Google Doc URL');
        return;
      }

      try {
        sessionStorage.removeItem('usedAuthCodes');
        sessionStorage.removeItem('parsedGoogleDocData');
        await parseFile(googleDocUrl, null, "prd");
      } catch (error) {
        console.error('Error parsing Google Doc URL:', error);
        
        const errorMessage = error instanceof Error ? error.message : 'Failed to parse Google Doc';
        if (errorMessage.includes('redirect') || errorMessage.includes('OAuth') || errorMessage.includes('location')) {
          return;
        }
        
        alert(`Error parsing Google Doc: ${errorMessage}`);
        
        setProjectData((prevData: any) => ({
          ...prevData,
          parsed_data: {
            ...prevData.parsed_data,
            prd: null,
          },
        }));
      }
    }
  };

  const handlePRDCheckboxChange = (checked: boolean) => {
    setHasPRD(checked);
  };

  const handleImageConfirmation = () => {
    setIsImageConfirmed(true);
    setProjectData((prevData) => ({
      ...prevData,
      parsed_data: {
        ...prevData.parsed_data,
        current_architecture: imageData,
      },
    }));
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">GenSpec</h1>
        <p className="text-gray-600 dark:text-gray-400">Generate comprehensive technical specifications for your project</p>
      </div>

      <Tabs defaultValue="basics" className="w-full">
        <TabsList className="grid w-full grid-cols-4 mb-6">
          <TabsTrigger value="basics" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Basics
          </TabsTrigger>
          <TabsTrigger value="architecture" className="flex items-center gap-2">
            <Code className="h-4 w-4" />
            Architecture
          </TabsTrigger>
          <TabsTrigger value="advanced" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Advanced
          </TabsTrigger>
          <TabsTrigger value="database" className="flex items-center gap-2">
            <Database className="h-4 w-4" />
            Database
          </TabsTrigger>
        </TabsList>

        {/* BASICS TAB */}
        <TabsContent value="basics" className="space-y-6">
          {/* PRD Section */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-600" />
              Product Requirements Document (PRD)
            </h3>
            
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="hasPRD" 
                  checked={hasPRD || false}
                  onCheckedChange={handlePRDCheckboxChange}
                />
                <Label htmlFor="hasPRD" className="text-sm font-medium cursor-pointer">
                  I have an existing PRD document
                </Label>
              </div>

              {hasPRD && (
                <div className="space-y-4 pl-6 border-l-2 border-blue-200">
                  <div className="space-y-2">
                    <Label htmlFor="prdMethod">How would you like to provide the PRD?</Label>
                    <select 
                      id="prdMethod"
                      className="w-full px-3 py-2 border rounded-md"
                      value={prdInputMethod}
                      onChange={handlePrdInputChange}
                    >
                      <option value="">Select an option</option>
                      <option value="file">Upload File (.md)</option>
                      <option value="url">Google Doc URL</option>
                    </select>
                  </div>

                  {prdInputMethod === 'file' && (
                    <div className="space-y-2">
                      <Input type="file" accept=".md" onChange={handleFileSelect} />
                      <Button onClick={handlePRDFileChange} className="w-full">Upload File</Button>
                    </div>
                  )}

                  {prdInputMethod === 'url' && (
                    <div className="space-y-2">
                      <Input 
                        type="text" 
                        placeholder="https://docs.google.com/document/d/..." 
                        onChange={handlePRDUrlChange}
                        className={prdUrlError ? "border-red-500" : ""}
                      />
                      {prdUrlError && (
                        <div className="flex items-center gap-2 p-3 text-sm text-red-800 bg-red-50 border border-red-200 rounded-md">
                          <AlertCircle className="h-4 w-4" />
                          {prdUrlError}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Project Details */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Project Details</h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Project Title *</Label>
                <Input
                  id="title"
                  placeholder="e.g., Payment Gateway Integration"
                  value={task.title}
                  onChange={(e) => {
                    const newTitle = e.target.value
                    setTask({ ...task, title: e.target.value })
                    setProjectData((prevData: ProjectData) => ({
                      ...prevData,
                      parsed_data: {
                        ...prevData.parsed_data,
                        title: newTitle,
                      },
                    }));
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="problemStatement">Problem Statement *</Label>
                <Textarea
                  id="problemStatement"
                  placeholder="Describe the problem you're trying to solve..."
                  rows={6}
                  value={task.problem_statement}
                  onChange={(e) => {
                    const newProblemStatement = e.target.value;
                    setTask({ ...task, problem_statement: newProblemStatement });
                    setProjectData((prevData: ProjectData) => ({
                      ...prevData,
                      parsed_data: {
                        ...prevData.parsed_data,
                        problem_statement: newProblemStatement,
                      },
                    }));
                  }}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="serviceNames">Razorpay Services Context (Optional)</Label>
                <select
                  id="serviceNames"
                  multiple
                  className="w-full px-3 py-2 border rounded-md min-h-[150px]"
                  value={projectData.parsed_data.service_names || []}
                  onChange={(e) => {
                    const selectedOptions = Array.from(e.target.selectedOptions, option => option.value);
                    setProjectData((prevData: ProjectData) => ({
                      ...prevData,
                      parsed_data: {
                        ...prevData.parsed_data,
                        service_names: selectedOptions,
                      },
                    }));
                  }}
                >
                  <option value="banking-bridge">Banking Bridge - Banking Bridge Service</option>
                  <option value="merchant_invoice">Merchant Invoice - Invoice Generation & Management</option>
                  <option value="scrooge">Scrooge - Pricing & Fee Calculation Engine</option>
                  <option value="payments-card">Payments Card - Card Processing Service</option>
                  <option value="settlements">Settlements - Settlement Management</option>
                  <option value="reporting">Reporting - Report Generation Service</option>
                  <option value="mozart">Mozart - Legacy Gateway Integration Management Service</option>
                  <option value="terminals">Terminals - Terminal Management Service</option>
                  <option value="integrations-go">Integrations Go - Gateway Integration Management Service</option>
                </select>
                <p className="text-sm text-gray-500">
                  Hold <kbd className="px-1.5 py-0.5 text-xs bg-gray-100 border rounded">Ctrl/Cmd</kbd> to select multiple services
                </p>
              </div>
            </div>
          </Card>
        </TabsContent>

        {/* ARCHITECTURE TAB */}
        <TabsContent value="architecture" className="space-y-6">
          {imageData && (
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Architecture Diagram Preview</h3>
              <img src={imageData || ''} alt="Architecture Diagram" className="max-w-full h-auto rounded-lg border" />
              <Button onClick={handleImageConfirmation} className="w-full mt-4">
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Confirm Diagram
              </Button>
            </Card>
          )}

          {!isImageConfirmed && (
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Architecture Diagram</h3>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="archMethod">How would you like to provide the architecture?</Label>
                  <select 
                    id="archMethod"
                    className="w-full px-3 py-2 border rounded-md"
                    value={archInputMethod}
                    onChange={handleArchInputChange}
                  >
                    <option value="">Select an option</option>
                    <option value="image">Image file (PNG/JPG)</option>
                    <option value="mermaid">Mermaid diagram code</option>
                    <option value="text">Text description (auto-generates flowchart)</option>
                    <option value="none">No architecture diagram</option>
                  </select>
                </div>

                {archInputMethod === 'image' && (
                  <div className="space-y-2">
                    <Label>Upload Architecture Image</Label>
                    <Input type="file" accept="image/png,image/jpeg" onChange={handleFileChange} />
                  </div>
                )}

                {archInputMethod === 'mermaid' && (
                  <div className="space-y-2">
                    <Label>Mermaid Diagram Code</Label>
                    <Textarea
                      placeholder="graph TD&#10;  A[Client] --> B[Server]&#10;  B --> C[Database]"
                      rows={10}
                      value={task.mermaid_code}
                      onChange={(e) => {
                        const mermaidCode = e.target.value;
                        setTask({ ...task, mermaid_code: mermaidCode });
                        saveMermaidDiagram(mermaidCode);
                      }}
                      className="font-mono text-sm"
                    />
                  </div>
                )}

                {archInputMethod === 'text' && (
                  <div className="space-y-2">
                    <Label>Architecture Description</Label>
                    <Textarea
                      placeholder="Describe your architecture (e.g., 'The system consists of a React frontend, Node.js backend, and PostgreSQL database...')"
                      rows={8}
                      value={task.arch_diagram_text_description}
                      onChange={(e) => {
                        const textDescription = e.target.value;
                        setTask({ ...task, text_description: textDescription });
                        generateFlowchart(textDescription);
                      }}
                    />
                  </div>
                )}
              </div>
            </Card>
          )}

          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">API Documentation</h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="apiDocMethod">How would you like to provide API documentation?</Label>
                <select 
                  id="apiDocMethod"
                  className="w-full px-3 py-2 border rounded-md"
                  value={apiDocMethod}
                  onChange={handleApiDocChange}
                >
                  <option value="">Select an option</option>
                  <option value="file">Upload file</option>
                  <option value="auto">Auto-generate based on inputs</option>
                  <option value="none">No API documentation needed</option>
                </select>
              </div>

              {apiDocMethod === 'file' && (
                <div className="space-y-2">
                  <Label>Upload API Documentation</Label>
                  <Input type="file" onChange={handleAPIDocFileChange} />
                </div>
              )}

              {apiDocMethod === 'auto' && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-sm text-blue-800">
                  API documentation will be automatically generated based on your problem statement and architecture.
                </div>
              )}
            </div>
          </Card>
        </TabsContent>

        {/* ADVANCED TAB */}
        <TabsContent value="advanced" className="space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Specification Options</h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="approachCount">Number of Approaches to Evaluate</Label>
                <select 
                  id="approachCount"
                  className="w-full px-3 py-2 border rounded-md"
                  value={projectData.parsed_data.evaluated_approaches_count}
                  onChange={(e) => handleAdditionalParamsChange('evaluated_approaches_count', e.target.value)}
                >
                  <option value="1">1 Approach</option>
                  <option value="2">2 Approaches</option>
                  <option value="3">3 Approaches</option>
                  <option value="4">4 Approaches</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="nfrs">Non-Functional Requirements</Label>
                <select 
                  id="nfrs"
                  multiple
                  className="w-full px-3 py-2 border rounded-md min-h-[200px]"
                  onChange={(e) => handleAdditionalParamsChange('nfrlist', e.target.value)}
                >
                  <option value="Scalability">Scalability</option>
                  <option value="Availability">Availability</option>
                  <option value="Security">Security</option>
                  <option value="Compliance">Compliance</option>
                  <option value="Reliability">Reliability</option>
                  <option value="Infrastructure Cost">Infrastructure Cost</option>
                  <option value="Performance">Performance</option>
                  <option value="Maintainability">Maintainability</option>
                  <option value="Observability">Observability</option>
                  <option value="Data Management">Data Management</option>
                </select>
                <p className="text-sm text-gray-500">
                  Hold <kbd className="px-1.5 py-0.5 text-xs bg-gray-100 border rounded">Ctrl/Cmd</kbd> to select multiple NFRs
                </p>
              </div>
            </div>
          </Card>
        </TabsContent>

        {/* DATABASE TAB */}
        <TabsContent value="database" className="space-y-6">
          <Card className="p-6">
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="includeDb" 
                  checked={includeDbSchema}
                  onCheckedChange={handleDbSchemaChange}
                />
                <Label htmlFor="includeDb" className="text-sm font-medium cursor-pointer">
                  Include database and schema considerations in the specification
                </Label>
              </div>

              {includeDbSchema && (
                <div className="space-y-4 pl-6 border-l-2 border-purple-200">
                  <div className="space-y-2">
                    <Label htmlFor="workloadType">Workload Type</Label>
                    <select 
                      id="workloadType"
                      className="w-full px-3 py-2 border rounded-md"
                      onChange={(e) => handleDBDataParamsChange('workload_type', e.target.value)}
                    >
                      <option value="Mostly Reads">Mostly Reads</option>
                      <option value="Mostly Writes">Mostly Writes</option>
                      <option value="Balanced">Balanced</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="acidReq">ACID Compliance Required?</Label>
                    <select 
                      id="acidReq"
                      className="w-full px-3 py-2 border rounded-md"
                      onChange={(e) => handleDBDataParamsChange('acid_requirements', e.target.value)}
                    >
                      <option value="Yes">Yes</option>
                      <option value="No">No</option>
                      <option value="Depends on the use-case">Depends on the use-case</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="joinComplexity">Complex JOINs Required?</Label>
                    <select 
                      id="joinComplexity"
                      className="w-full px-3 py-2 border rounded-md"
                      onChange={(e) => handleDBDataParamsChange('join_complexity', e.target.value)}
                    >
                      <option value="Yes, multiple tables often need to be joined">Yes, multiple tables often need to be joined</option>
                      <option value="No, data is mostly self-contained or denormalized">No, data is mostly self-contained or denormalized</option>
                      <option value="Not sure">Not sure</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="failurePoints">Failure Points Details</Label>
                    <Textarea
                      id="failurePoints"
                      placeholder="Describe specific areas where failure points should be highlighted..."
                      rows={3}
                      onChange={(e) => handleDBDataParamsChange('failure_points_details', e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="txBoundaries">Transaction Boundaries Details</Label>
                    <Textarea
                      id="txBoundaries"
                      placeholder="Describe transaction boundaries that need careful handling..."
                      rows={3}
                      onChange={(e) => handleDBDataParamsChange('transaction_boundaries_details', e.target.value)}
                    />
                  </div>
                </div>
              )}
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Generate Button */}
      <Card className="p-6 mt-6">
        <Button 
          className="w-full h-12 text-lg"
          onClick={confirmAndGenerate}
          disabled={specStatus === 'processing'}
        >
          {specStatus === 'processing' ? (
            <>Generating Specification...</>
          ) : (
            <>
              <Zap className="mr-2 h-5 w-5" />
              Generate Specification
            </>
          )}
        </Button>

        {specStatus === 'processing' && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md text-center">
            <div className="flex items-center justify-center gap-2 text-blue-800">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              Task is being processed in the background. Please wait...
            </div>
          </div>
        )}

        {specStatus === 'queued' && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md text-center">
            <div className="flex items-center justify-center gap-2 text-green-800">
              <CheckCircle2 className="h-5 w-5" />
              Task has been queued successfully! Check the Tasks tab to monitor progress.
            </div>
          </div>
        )}

        {specStatus === 'failed' && error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <div className="flex items-center gap-2 text-red-800">
              <AlertCircle className="h-5 w-5" />
              <span className="font-semibold">Error:</span> {error}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
