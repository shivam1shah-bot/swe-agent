import React from 'react'
import { useParams } from 'react-router-dom'
import SpinnakerV3PipelineGenerator from './SpinnakerV3PipelineGenerator'
import GatewayIntegrations from './GatewayIntegrations'
import RepoContextGeneratorPage from './RepoContextGeneratorPage'
import QCCOnboardingPage from './QCCOnboardingPage'
import { GenSpecPage } from './GenSpecPage';

import E2EOnboardingPage from './E2EOnboardingPage'
import BankIntegrationComponent from './BankIntegrationComponent'
import APIDocGeneratorComponent from './BankIntegration/APIDocGeneratorComponent'
import BankUATAgentComponent from './BankIntegration/BankUATAgentComponent'
import PDFApiDocUATComponent from './BankIntegration/PDFApiDocUATComponent'
import PDFApiDocUATMicroFrontend from './BankIntegration/PDFApiDocUATMicroFrontend'

// Component Registry - Maps agent types and names to React components
export const COMPONENT_REGISTRY = {
  'micro-frontend': {
    'spinnaker-v3-pipeline-generator': SpinnakerV3PipelineGenerator,
    'gateway-integrations-common': GatewayIntegrations,
    'repo-context-generator': RepoContextGeneratorPage,
    'qcc-onboarding': QCCOnboardingPage,
    'genspec-agent': GenSpecPage,  // Added GenSpec agent

    'api-doc-generator': APIDocGeneratorComponent,
    'bank-uat-agent': BankUATAgentComponent,
    'pdf-api-doc-uat': PDFApiDocUATComponent,
    'pdf-api-doc-uat-storage': PDFApiDocUATMicroFrontend,
    'e2e-onboarding': E2EOnboardingPage,
    'bank-integration': BankIntegrationComponent,
  },
  // Add more types as needed
  // 'api': {
  //   'some-api-component': SomeApiComponent,
  // },
} as const

// 404 Component
const NotFoundPage: React.FC = () => {
  const { type, name } = useParams<{ type: string; name: string }>()

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="text-6xl mb-4">🤖</div>
      <h1 className="text-2xl font-bold mb-2">Agent Not Found</h1>
      <p className="text-muted-foreground mb-4">
        The agent "{name}" of type "{type}" is not available or hasn't been implemented yet.
      </p>
      <div className="bg-muted p-4 rounded-lg">
        <p className="text-sm text-muted-foreground">
          <strong>Requested:</strong> /agents-catalogue/{type}/{name}
        </p>
      </div>
      <button
        onClick={() => window.history.back()}
        className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
      >
        Go Back
      </button>
    </div>
  )
}

// Dynamic Route Component
export const DynamicAgentComponent: React.FC = () => {
  const { type, name } = useParams<{ type: string; name: string }>()
  

  if (!type || !name) {
    return <NotFoundPage />
  }

  // Look up the component in the registry
  const typeRegistry = COMPONENT_REGISTRY[type as keyof typeof COMPONENT_REGISTRY]
  if (!typeRegistry) {
    return <NotFoundPage />
  }

  const Component = typeRegistry[name as keyof typeof typeRegistry]
  if (!Component) {
    return <NotFoundPage />
  }

  return (
    <div className="p-8">
      <Component />
    </div>
  )
}

// Export types for type safety
export type AgentType = keyof typeof COMPONENT_REGISTRY
export type AgentName<T extends AgentType> = keyof typeof COMPONENT_REGISTRY[T]