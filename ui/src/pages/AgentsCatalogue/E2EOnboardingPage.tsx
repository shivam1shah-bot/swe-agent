/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select } from '../../components/ui/select';
import { Badge } from '../../components/ui/badge';
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  Database,
  Navigation,
  Settings,
  Workflow,
} from 'lucide-react';
import { apiClient } from '@/lib/api';

const DB_VERSION_BY_TYPE: Record<string, string> = {
  postgres: '13.4',
  mysql: '8.0',
};

interface EphemeralDbConfig {
  db1_name: string;
  db1_username: string;
  requests_cpu: string;
  requests_memory: string;
  type: string;
  version: string;
  db1_seeding: boolean;
  dns_policy: string;
  attach_volume: boolean;
  node_selector: string;
}

interface DatabaseEnvKeys {
  url: string;
  name: string;
  username: string;
  password: string;
}

interface DbMigrationConfig {
  db_image_prefix: string;
  migration_cmd: string;
}

interface SecretsConfig {
  name: string;
  type: string;
}

interface ChartOverrides {
  image_pull_policy: string;
  replicas: {
    key: string;
    value: string;
  };
  node_selector: {
    key: string;
    value: string;
  };
}

interface E2ETestOrchestratorParams {
  config_overrides: string;
}

interface BranchNames {
  goutils: string;
}

interface GoUtilsConfig {
  mode: string;
}

interface E2EFormData {
  service_name: string;
  service_url: string;
  namespace: string;
  commit_id: string;
  use_ephemeral_db: boolean;
  ephemeral_db_config: EphemeralDbConfig;
  database_env_keys: DatabaseEnvKeys;
  db_migration: DbMigrationConfig;
  secrets: SecretsConfig;
  chart_overrides: ChartOverrides;
  branch_names: BranchNames;
  goutils_config: GoUtilsConfig;
  e2e_test_orchestrator_params: E2ETestOrchestratorParams;
}

interface StepDefinition {
  id: StepId;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

type StepId = 'service' | 'kubemanifest' | 'goutils' | 'orchestrator';

const STEPS: StepDefinition[] = [
  {
    id: 'service',
    title: 'Service Under Test',
    description: 'Primary service information and documentation pointers.',
    icon: Settings,
  },
  {
    id: 'kubemanifest',
    title: 'Kubemanifests',
    description: 'Database, secrets, and kubemanifest branch configuration.',
    icon: Database,
  },
  {
    id: 'goutils',
    title: 'Go-Utils',
    description: 'Branch selection for Go-Utils changes.',
    icon: ChevronRight,
  },
  {
    id: 'orchestrator',
    title: 'E2E Test Orchestrator',
    description: 'Deployment overrides and scheduling controls for orchestrated runs.',
    icon: Workflow,
  },
];

const createDefaultEphemeralConfig = (): EphemeralDbConfig => ({
  db1_name: '',
  db1_username: '',
  requests_cpu: '50m',
  requests_memory: '50Mi',
  type: 'postgres',
  version: DB_VERSION_BY_TYPE.postgres,
  db1_seeding: false,
  dns_policy: 'ClusterFirst',
  attach_volume: false,
  node_selector: 'node.kubernetes.io/worker-database',
});

const createEmptyEphemeralConfig = (): EphemeralDbConfig => ({
  db1_name: '',
  db1_username: '',
  requests_cpu: '50m',
  requests_memory: '50Mi',
  type: '',
  version: '',
  db1_seeding: false,
  dns_policy: 'ClusterFirst',
  attach_volume: false,
  node_selector: 'node.kubernetes.io/worker-database',
});

const createDefaultDatabaseEnvKeys = (): DatabaseEnvKeys => ({
  url: '',
  name: '',
  username: '',
  password: '',
});

const createDefaultDbMigration = (): DbMigrationConfig => ({
  db_image_prefix: '',
  migration_cmd: 'up',
});

const initialFormData: E2EFormData = {
  service_name: '',
  service_url: '',
  namespace: '',
  commit_id: '',
  use_ephemeral_db: true,
  ephemeral_db_config: createDefaultEphemeralConfig(),
  database_env_keys: createDefaultDatabaseEnvKeys(),
  db_migration: createDefaultDbMigration(),
  secrets: {
    name: '',
    type: 'ephemeral',
  },
  chart_overrides: {
    image_pull_policy: 'Always',
    replicas: {
      key: 'replicas',
      value: '2',
    },
    node_selector: {
      key: 'nodeSelector',
      value: 'node.kubernetes.io/worker-tests-app',
    },
  },
  branch_names: {
    goutils: '',
  },
  goutils_config: {
    mode: '',
  },
  e2e_test_orchestrator_params: {
    config_overrides: '{}',
  },
};

export const E2EOnboardingPage: React.FC = () => {
  const navigate = useNavigate();

  const [expandedStep, setExpandedStep] = useState<StepId | null>('service');
  const [formData, setFormData] = useState<E2EFormData>(initialFormData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [redirectPending, setRedirectPending] = useState(false);

  const isFilled = (value: string) => value.trim().length > 0;

  const stepCompletion = useMemo(() => {
    const serviceComplete =
      isFilled(formData.service_url) &&
      isFilled(formData.commit_id);

    const ephemeralComplete = !formData.use_ephemeral_db
      ? true
      : isFilled(formData.ephemeral_db_config.db1_name) &&
        isFilled(formData.ephemeral_db_config.db1_username) &&
        isFilled(formData.ephemeral_db_config.type) &&
        isFilled(formData.ephemeral_db_config.version);

    const kubemanifestComplete =
      ephemeralComplete &&
      isFilled(formData.service_name) &&
      isFilled(formData.namespace) &&
      isFilled(formData.secrets.name) &&
      isFilled(formData.secrets.type);

    const goutilsComplete =
      isFilled(formData.branch_names.goutils) && isFilled(formData.goutils_config.mode);

    const orchestratorComplete =
      isFilled(formData.chart_overrides.image_pull_policy) &&
      isFilled(formData.chart_overrides.replicas.key) &&
      isFilled(formData.chart_overrides.replicas.value) &&
      isFilled(formData.chart_overrides.node_selector.key) &&
      isFilled(formData.chart_overrides.node_selector.value);

    return {
      service: serviceComplete,
      kubemanifest: kubemanifestComplete,
      goutils: goutilsComplete,
      orchestrator: orchestratorComplete,
    } satisfies Record<StepId, boolean>;
  }, [formData]);

  const allStepsCompleted = useMemo(() => Object.values(stepCompletion).every(Boolean), [stepCompletion]);

  const updateFormField = (field: string, value: any) => {
    if (field === 'use_ephemeral_db') {
      setFormData((prev) => {
        if (value) {
          return {
            ...prev,
            use_ephemeral_db: true,
            ephemeral_db_config: createDefaultEphemeralConfig(),
            database_env_keys: createDefaultDatabaseEnvKeys(),
            db_migration: createDefaultDbMigration(),
          };
        }

        return {
          ...prev,
          use_ephemeral_db: false,
          ephemeral_db_config: createEmptyEphemeralConfig(),
          database_env_keys: createDefaultDatabaseEnvKeys(),
          db_migration: createDefaultDbMigration(),
        };
      });
      return;
    }

    setFormData((prev) => {
      const newData = { ...prev } as any;

      const path = field.split('.');
      let target = newData;
      for (let i = 0; i < path.length - 1; i += 1) {
        const key = path[i];
        if (typeof target[key] !== 'object' || target[key] === null) {
          target[key] = {};
        }
        target = target[key];
      }
      target[path[path.length - 1]] = value;
      return newData;
    });
  };

  const executeE2EOnboarding = async () => {
    if (!stepCompletion.service || !stepCompletion.kubemanifest || !stepCompletion.goutils || !stepCompletion.orchestrator) {
      setError('Please complete the Service Under Test, Kubemanifests, Go-Utils, and E2E Test Orchestrator sections before submitting.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);
    setTaskId(null);

    try {
      const { service_name, service_url, namespace, commit_id, use_ephemeral_db, ephemeral_db_config, database_env_keys, db_migration, secrets, chart_overrides, branch_names, goutils_config, e2e_test_orchestrator_params } = formData

      const payload: Record<string, any> = {
        service_name,
        service_url,
        namespace,
        commit_id,
        use_ephemeral_db,
        secrets,
        chart_overrides,
        branch_names,
        goutils_config,
        e2e_test_orchestrator_params,
      }

      if (use_ephemeral_db) {
        payload.ephemeral_db_config = ephemeral_db_config
        payload.database_env_keys = database_env_keys
        payload.db_migration = db_migration
      }

      const result = await apiClient.executeMicroFrontendService(
          'e2e-onboarding', payload, 1800, 'normal', ['e2e', 'onboarding']);

      if (result.status === 'queued' || result.status === 'completed') {
        if (result.task_id) {
          setTaskId(result.task_id);
        }
        setSuccess(true);
        setRedirectPending(true);
        setTimeout(() => {
          setRedirectPending(false);
          navigate('/agents-catalogue');
        }, 2500);
      } else {
        const message = result.message || `Unexpected status: ${result.status}` || 'Unknown error occurred';
        setError(message);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`E2E onboarding failed: ${message}`);
      console.error('Error submitting E2E onboarding job:', err);
    } finally {
      setLoading(false);
    }
  };

  const renderStepContent = (stepId: StepId) => {
    if (stepId === 'service') {
      return (
        <div className="space-y-4 text-gray-800 dark:text-slate-200">
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Service Repository URL</label>
            <Input
              placeholder="https://github.com/razorpay/service-name"
              value={formData.service_url}
              onChange={(e) => updateFormField('service_url', e.target.value)}
              className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Commit ID</label>
            <Input
              placeholder="commit-id-of-the-service"
              value={formData.commit_id}
              onChange={(e) => updateFormField('commit_id', e.target.value)}
              className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </div>
        </div>
      );
    }

    if (stepId === 'kubemanifest') {
      return (
        <div className="space-y-6 text-gray-800 dark:text-slate-200">
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={formData.use_ephemeral_db}
              onChange={(e) => updateFormField('use_ephemeral_db', e.target.checked)}
              className="h-4 w-4"
            />
            <span className="text-sm font-medium text-gray-700 dark:text-slate-300">Use Ephemeral Database</span>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Service Name</label>
              <Input
                placeholder="e.g., your-service-name"
                value={formData.service_name}
                onChange={(e) => updateFormField('service_name', e.target.value)}
                className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Namespace</label>
              <Input
                placeholder="your-service-namespace"
                value={formData.namespace}
                onChange={(e) => updateFormField('namespace', e.target.value)}
                className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
            </div>
          </div>

          {formData.use_ephemeral_db && (
            <div className="space-y-6 border-l-2 border-blue-200 pl-6 dark:border-blue-500/40">
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Database Name</label>
                  <Input
                    placeholder="my_onboarding_db"
                    value={formData.ephemeral_db_config.db1_name}
                    onChange={(e) => updateFormField('ephemeral_db_config.db1_name', e.target.value)}
                    className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Database Username</label>
                  <Input
                    placeholder="onboarding_user"
                    value={formData.ephemeral_db_config.db1_username}
                    onChange={(e) => updateFormField('ephemeral_db_config.db1_username', e.target.value)}
                    className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">CPU Requests</label>
                  <Input
                    placeholder="50m"
                    value={formData.ephemeral_db_config.requests_cpu}
                    readOnly
                    className="cursor-not-allowed dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Memory Requests</label>
                  <Input
                    placeholder="50Mi"
                    value={formData.ephemeral_db_config.requests_memory}
                    readOnly
                    className="cursor-not-allowed dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Database Type</label>
                  <Select
                    value={formData.ephemeral_db_config.type}
                    onChange={(e) => {
                      const selectedType = e.target.value;
                      updateFormField('ephemeral_db_config.type', selectedType);
                      const derivedVersion = DB_VERSION_BY_TYPE[selectedType] ?? '';
                      updateFormField('ephemeral_db_config.version', derivedVersion);
                    }}
                    className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                  >
                    <option value="">Select database type</option>
                    <option value="postgres">Postgres</option>
                    <option value="mysql">MySQL</option>
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Version</label>
                  <Input
                    placeholder="version"
                    value={formData.ephemeral_db_config.version}
                    readOnly
                    className="dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="flex items-center justify-between rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
                  <span>Enable DB Seeding</span>
                  <span className="text-xs font-medium uppercase text-gray-600 dark:text-slate-200">false</span>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
                  <span>Attach Persistent Volume</span>
                  <span className="text-xs font-medium uppercase text-gray-600 dark:text-slate-200">false</span>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">DNS Policy</label>
                  <Input
                    placeholder="ClusterFirst"
                    value={formData.ephemeral_db_config.dns_policy}
                    readOnly
                    className="cursor-not-allowed dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-slate-300">Node Selector</label>
                  <Input
                    placeholder="node.kubernetes.io/worker-database"
                    value={formData.ephemeral_db_config.node_selector}
                    onChange={(e) => updateFormField('ephemeral_db_config.node_selector', e.target.value)}
                    className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300">Database Environment Keys</h4>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div>
                    <label className="text-sm text-gray-700 dark:text-slate-300">URL Key</label>
                    <Input
                      value={formData.database_env_keys.url}
                      onChange={(e) => updateFormField('database_env_keys.url', e.target.value)}
                      className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-700 dark:text-slate-300">Name Key</label>
                    <Input
                      value={formData.database_env_keys.name}
                      onChange={(e) => updateFormField('database_env_keys.name', e.target.value)}
                      className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-700 dark:text-slate-300">Username Key</label>
                    <Input
                      value={formData.database_env_keys.username}
                      onChange={(e) => updateFormField('database_env_keys.username', e.target.value)}
                      className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-700 dark:text-slate-300">Password Key</label>
                    <Input
                      value={formData.database_env_keys.password}
                      onChange={(e) => updateFormField('database_env_keys.password', e.target.value)}
                      className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300">Database Migration</h4>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div>
                    <label className="text-sm text-gray-700 dark:text-slate-300">Migration Image Prefix</label>
                    <Input
                      placeholder="service-images-for-migration"
                      value={formData.db_migration.db_image_prefix}
                      onChange={(e) => updateFormField('db_migration.db_image_prefix', e.target.value)}
                      className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-700 dark:text-slate-300">Migration Command</label>
                    <Input
                      placeholder="up/down"
                      value={formData.db_migration.migration_cmd}
                      onChange={(e) => updateFormField('db_migration.migration_cmd', e.target.value)}
                      className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300">Kubernetes Secrets</h4>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <label className="text-sm text-gray-700 dark:text-slate-300">Secret Name</label>
                <Input
                  placeholder="your-service-secrets"
                  value={formData.secrets.name}
                  onChange={(e) => updateFormField('secrets.name', e.target.value)}
                  className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                />
              </div>
              <div>
                <label className="text-sm text-gray-700 dark:text-slate-300">Secret Type</label>
                <Select
                  value={formData.secrets.type}
                  onChange={(e) => updateFormField('secrets.type', e.target.value)}
                  className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                >
                  <option value="">Select secret type</option>
                  <option value="ephemeral">Ephemeral</option>
                  <option value="static">Static</option>
                </Select>
              </div>
            </div>
          </div>

        </div>
      );
    }

    if (stepId === 'goutils') {
      return (
        <div className="space-y-4 text-gray-800 dark:text-slate-200">
          <div>
            <label className="text-sm text-gray-700 dark:text-slate-300">Goutils Branch</label>
            <Input
              placeholder="itf/v0.1.44"
              value={formData.branch_names.goutils}
              onChange={(e) => updateFormField('branch_names.goutils', e.target.value)}
              className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="text-sm text-gray-700 dark:text-slate-300">Goutils Mode</label>
            <Input
              placeholder="live"
              value={formData.goutils_config.mode}
              onChange={(e) => updateFormField('goutils_config.mode', e.target.value)}
              className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </div>
        </div>
      );
    }

    if (stepId === 'orchestrator') {
      return (
        <div className="space-y-6 text-gray-800 dark:text-slate-200">
          <div className="space-y-2">
            <p className="text-sm text-gray-600 dark:text-slate-300">
              Configure deployment overrides for the orchestrator so it can scale test workloads appropriately and target
              the right nodes during execution.
            </p>
            <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 p-4 text-xs text-gray-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
              Tip: Align these overrides with your staging workload defaults. The orchestrator will apply them to every run.
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div>
              <label className="text-sm text-gray-700 dark:text-slate-300">Image Pull Policy</label>
              <Input
                value={formData.chart_overrides.image_pull_policy}
                readOnly
                className="cursor-not-allowed dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="text-sm text-gray-700 dark:text-slate-300">Replicas Key</label>
              <Input
                value={formData.chart_overrides.replicas.key}
                onChange={(e) => updateFormField('chart_overrides.replicas.key', e.target.value)}
                className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
              <label className="mt-2 block text-sm text-gray-700 dark:text-slate-300">Replicas Value</label>
              <Input
                value={formData.chart_overrides.replicas.value}
                onChange={(e) => updateFormField('chart_overrides.replicas.value', e.target.value)}
                className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="text-sm text-gray-700 dark:text-slate-300">Node Selector Key</label>
              <Input
                value={formData.chart_overrides.node_selector.key}
                onChange={(e) => updateFormField('chart_overrides.node_selector.key', e.target.value)}
                className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
              <label className="mt-2 block text-sm text-gray-700 dark:text-slate-300">Node Selector Value</label>
              <Input
                value={formData.chart_overrides.node_selector.value}
                onChange={(e) => updateFormField('chart_overrides.node_selector.value', e.target.value)}
                className="dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300">Argo Workflow Configuration</h4>
            <div className="space-y-2">
              <label className="text-sm text-gray-700 dark:text-slate-300">Config Overrides (JSON)</label>
              <textarea
                value={formData.e2e_test_orchestrator_params.config_overrides}
                onChange={(e) => updateFormField('e2e_test_orchestrator_params.config_overrides', e.target.value)}
                className="min-h-[120px] w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                placeholder="{}"
              />
              <p className="text-xs text-gray-500 dark:text-slate-400">
                Overrides passed to the orchestrator config (JSON string). Ensure the payload is valid JSON before submitting.
              </p>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-4 text-gray-800 dark:text-slate-200">
        <p className="text-sm text-gray-600 dark:text-slate-300">
          Provide documentation and references that the testing workflow should follow. These values help the automation
          locate the correct guides and templates while executing the onboarding steps.
        </p>
        <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 p-4 text-xs text-gray-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
          Tip: include any additional instructions directly in the referenced documentation so the agent can follow them during execution.
        </div>
      </div>
    );
  };

  const toggleStep = (stepId: StepId) => {
    setExpandedStep((prev) => (prev === stepId ? null : stepId));
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <div className="border-b border-gray-200 bg-white/80 px-6 py-8 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
        <div className="mx-auto flex w-full max-w-4xl flex-col space-y-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold text-gray-900 dark:text-white">E2E Onboarding</h1>
            <p className="text-sm text-gray-500 dark:text-slate-400">
              Fill each step below to provision automation-ready configuration.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-200">
              Workflow
            </Badge>
            <Badge variant="outline" className="border-green-200 bg-green-50 text-green-700 dark:border-green-500/30 dark:bg-green-500/10 dark:text-green-200">
              Production Ready
            </Badge>
          </div>
        </div>
      </div>

      <main className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6">
        {STEPS.map((step) => {
          const Icon = step.icon;
          const expanded = expandedStep === step.id;
          const completed = stepCompletion[step.id];

          return (
            <Card key={step.id} className="border border-gray-200 dark:border-slate-800 dark:bg-slate-900/70">
              <button
                type="button"
                onClick={() => toggleStep(step.id)}
                className={`flex w-full items-center justify-between rounded-md px-4 py-4 text-left transition ${
                  expanded ? 'bg-blue-600/10 dark:bg-blue-500/10' : 'hover:bg-gray-100 dark:hover:bg-slate-800'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <span className="rounded-md bg-white p-2 text-blue-600 shadow-sm dark:bg-slate-800 dark:text-blue-300">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-gray-900 dark:text-slate-100">{step.title}</span>
                    <span className="text-xs text-gray-500 dark:text-slate-400">{step.description}</span>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  {completed ? (
                    <span className="flex items-center space-x-1 text-xs font-medium text-green-600 dark:text-green-300">
                      <CheckCircle2 className="h-4 w-4" />
                      <span>Completed</span>
                    </span>
                  ) : (
                    <span className="flex items-center space-x-1 text-xs font-medium text-gray-400 dark:text-slate-500">
                      <Circle className="h-4 w-4" />
                      <span>Pending</span>
                    </span>
                  )}
                  <ChevronDown className={`h-4 w-4 text-gray-500 transition-transform dark:text-slate-400 ${expanded ? 'rotate-180' : ''}`} />
                </div>
              </button>

              {expanded && (
                <CardContent className="space-y-6 border-t border-gray-200 px-4 py-6 dark:border-slate-800">
                  {renderStepContent(step.id)}
                </CardContent>
              )}
            </Card>
          );
        })}

        <Card className="border border-gray-200 dark:border-slate-800 dark:bg-slate-900/70">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-gray-900 dark:text-white">
              <Navigation className="h-5 w-5 text-blue-600 dark:text-blue-300" />
              <span>Submission</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-gray-700 dark:text-slate-200">
            {success && taskId && (
              <div className="rounded-md border border-green-200 bg-green-50 p-4 dark:border-green-500/40 dark:bg-green-500/10">
                <p className="text-sm font-medium text-green-700 dark:text-green-300">
                  🎉 E2E onboarding workflow queued for {formData.service_name || 'the service'} successfully.
                </p>
                <p className="text-xs text-green-600 dark:text-green-200">
                  Task ID: {taskId}. {redirectPending ? 'Redirecting to catalogue…' : 'Track progress in the '}
                  {!redirectPending && (
                    <button
                      type="button"
                      onClick={() => navigate('/tasks')}
                      className="font-medium underline hover:text-green-800 dark:hover:text-green-100"
                    >
                      Tasks page
                    </button>
                  )}
                  {redirectPending ? '' : '.'}
                </p>
              </div>
            )}

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 p-4 dark:border-red-500/40 dark:bg-red-500/10">
                <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            )}

            <div className="flex flex-col space-y-3 text-sm text-gray-600 dark:text-slate-300">
              <span className="font-medium text-gray-800 dark:text-slate-100">Checklist</span>
              <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                {STEPS.map((step) => {
                  const done = stepCompletion[step.id];
                  return (
                    <span key={step.id} className="flex items-center space-x-2">
                      {done ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500 dark:text-green-300" />
                      ) : (
                        <Circle className="h-4 w-4 text-gray-300 dark:text-slate-700" />
                      )}
                      <span>{step.title}</span>
                    </span>
                  );
                })}
              </div>
            </div>

            <Button
              onClick={executeE2EOnboarding}
              disabled={loading || success || !allStepsCompleted}
              size="lg"
              className="w-full"
            >
              {success ? '✅ Queued Successfully' : loading ? '🔄 Starting E2E Onboarding...' : '🚀 Start E2E Onboarding'}
              {!success && <ChevronRight className="ml-2 h-4 w-4" />}
            </Button>

            <p className="text-center text-xs text-gray-500 dark:text-slate-400">
              Need a refresher? Review the full process at{' '}
              <a
                href="https://idocs.razorpay.com/qa/itf/end-to-end-testing/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200"
              >
                ITF End-to-End Testing docs
              </a>
              .
            </p>

            <p className="text-center text-xs text-gray-500 dark:text-slate-400">
              Typical end-to-end onboarding runs take between 25 and 40 minutes to process every repository.
            </p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default E2EOnboardingPage;
