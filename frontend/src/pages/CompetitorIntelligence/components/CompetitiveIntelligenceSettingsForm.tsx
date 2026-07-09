/**
 * CompetitiveIntelligenceSettingsForm
 *
 * Shared form component for Competitive Intelligence Agent configuration.
 * Used by both CompetitiveIntelligenceSetupModal and AgentSettingsTab.
 *
 * Settings:
 * - Schedule mode (manual/scheduled) and frequency
 * - Advanced: separate schedules for discovery vs analysis
 * - Alerts for competitor changes
 *
 * Idea generation is configured on SynthesisConfig in the Synthesis Hub,
 * not here.
 */

import { useState, useEffect } from 'react';
import { CompetitiveAgentConfig, ScheduleFrequency } from '../../../types';
import { formatDateTime } from '../../../utils/date';

export interface SettingsFormData {
  competitor_discovery_mode?: 'manual' | 'scheduled';
  competitor_discovery_schedule?: ScheduleFrequency;
  deep_analysis_mode?: 'manual' | 'scheduled';
  deep_analysis_schedule?: ScheduleFrequency;
  alert_on_new_competitors?: boolean;
  alert_on_disappeared_competitors?: boolean;
}

interface Props {
  config: CompetitiveAgentConfig | null;
  onChange: (data: SettingsFormData) => void;
  /** Show last run timestamps (typically for settings tab, not modal) */
  showLastRunInfo?: boolean;
}

export default function CompetitiveIntelligenceSettingsForm({ config, onChange, showLastRunInfo = false }: Props) {
  // Form state - tracks pending changes
  const [formData, setFormData] = useState<SettingsFormData>({});

  // Advanced scheduling UI state
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Initialize advanced view if separate schedules are in use
  useEffect(() => {
    if (config?.competitor_discovery_schedule !== config?.deep_analysis_schedule &&
        config?.competitor_discovery_mode === 'scheduled' &&
        config?.deep_analysis_mode === 'scheduled') {
      setShowAdvanced(true);
    }
  }, [config]);

  // Helper to get current value (pending change or saved)
  const getValue = <K extends keyof CompetitiveAgentConfig>(field: K): CompetitiveAgentConfig[K] => {
    if (field in formData) {
      return formData[field as keyof SettingsFormData] as CompetitiveAgentConfig[K];
    }
    return config?.[field] as CompetitiveAgentConfig[K];
  };

  const handleChange = (field: keyof SettingsFormData, value: unknown) => {
    const newFormData = { ...formData, [field]: value };
    setFormData(newFormData);
    onChange(newFormData);
  };

  // Handle unified mode change - sync both discovery and analysis modes
  const handleModeChange = (mode: 'manual' | 'scheduled') => {
    const newFormData = {
      ...formData,
      deep_analysis_mode: mode,
      competitor_discovery_mode: mode,
    };
    setFormData(newFormData);
    onChange(newFormData);
  };

  // Handle unified schedule change - sync both schedules when not using separate
  const handleUnifiedScheduleChange = (schedule: ScheduleFrequency) => {
    const newFormData = {
      ...formData,
      deep_analysis_schedule: schedule,
      competitor_discovery_schedule: schedule,
    };
    setFormData(newFormData);
    onChange(newFormData);
  };

  // Check if using separate schedules
  const useSeparateSchedules = getValue('competitor_discovery_schedule') !== getValue('deep_analysis_schedule') &&
    getValue('competitor_discovery_mode') === 'scheduled' &&
    getValue('deep_analysis_mode') === 'scheduled';

  // Unified mode for display (scheduled if either is scheduled)
  const unifiedMode = getValue('deep_analysis_mode') === 'scheduled' || getValue('competitor_discovery_mode') === 'scheduled'
    ? 'scheduled' : 'manual';

  return (
    <div className="space-y-6">
      {/* Schedule Section */}
      <section className="bg-gray-50 rounded-lg p-5">
        <h3 className="text-md font-medium text-gray-900 mb-4">Schedule</h3>

        {/* Mode Selection */}
        <div className="space-y-2 mb-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="radio"
              name="mode"
              checked={unifiedMode === 'manual'}
              onChange={() => handleModeChange('manual')}
              className="h-4 w-4 text-blue-600"
            />
            <span className="text-sm text-gray-700">Manual - Run analysis only when triggered</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="radio"
              name="mode"
              checked={unifiedMode === 'scheduled'}
              onChange={() => handleModeChange('scheduled')}
              className="h-4 w-4 text-blue-600"
            />
            <span className="text-sm text-gray-700">Scheduled - Run automatically</span>
          </label>
        </div>

        {/* Unified Schedule Frequency */}
        {unifiedMode === 'scheduled' && !useSeparateSchedules && (
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Frequency</label>
            <select
              value={getValue('deep_analysis_schedule') || 'weekly'}
              onChange={(e) => handleUnifiedScheduleChange(e.target.value as ScheduleFrequency)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Full pipeline runs: Discovery → Audits → Landscape Synthesis
            </p>
          </div>
        )}

        {/* Advanced Scheduling Toggle */}
        {unifiedMode === 'scheduled' && (
          <div>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800"
            >
              <svg
                className={`w-4 h-4 transform transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              Advanced scheduling options
            </button>

            {showAdvanced && (
              <div className="mt-3 ml-6 space-y-4 border-l-2 border-gray-200 pl-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useSeparateSchedules}
                    onChange={(e) => {
                      if (e.target.checked) {
                        // Enable separate schedules - set different defaults
                        const newFormData = {
                          ...formData,
                          competitor_discovery_mode: 'scheduled' as const,
                          competitor_discovery_schedule: 'monthly' as ScheduleFrequency,
                          deep_analysis_mode: 'scheduled' as const,
                          deep_analysis_schedule: 'weekly' as ScheduleFrequency,
                        };
                        setFormData(newFormData);
                        onChange(newFormData);
                      } else {
                        // Sync schedules
                        const schedule = getValue('deep_analysis_schedule') || 'weekly';
                        const newFormData = {
                          ...formData,
                          competitor_discovery_schedule: schedule,
                        };
                        setFormData(newFormData);
                        onChange(newFormData);
                      }
                    }}
                    className="h-4 w-4 text-blue-600 rounded"
                  />
                  <span className="text-sm text-gray-700">Use separate schedules for discovery and analysis</span>
                </label>

                {useSeparateSchedules && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Market Discovery
                      </label>
                      <select
                        value={getValue('competitor_discovery_schedule') || 'monthly'}
                        onChange={(e) => handleChange('competitor_discovery_schedule', e.target.value as ScheduleFrequency)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      >
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                      {showLastRunInfo && config?.competitor_discovery_last_run && (
                        <p className="text-xs text-gray-500 mt-1">
                          Last run: {formatDateTime(config.competitor_discovery_last_run)}
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Competitive Analysis
                      </label>
                      <select
                        value={getValue('deep_analysis_schedule') || 'weekly'}
                        onChange={(e) => handleChange('deep_analysis_schedule', e.target.value as ScheduleFrequency)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      >
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                      {showLastRunInfo && config?.deep_analysis_last_run && (
                        <p className="text-xs text-gray-500 mt-1">
                          Last run: {formatDateTime(config.deep_analysis_last_run)}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Last run info (when not showing separate schedules) */}
        {showLastRunInfo && !useSeparateSchedules && config?.deep_analysis_last_run && (
          <p className="text-xs text-gray-500 mt-2">
            Last run: {formatDateTime(config.deep_analysis_last_run)}
          </p>
        )}
      </section>

      {/* Alerts Section */}
      <section className="bg-gray-50 rounded-lg p-5">
        <h3 className="text-md font-medium text-gray-900 mb-4">Alerts</h3>

        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={getValue('alert_on_new_competitors') ?? true}
              onChange={(e) => handleChange('alert_on_new_competitors', e.target.checked)}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="text-sm text-gray-700">Alert on new competitors discovered</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={getValue('alert_on_disappeared_competitors') ?? true}
              onChange={(e) => handleChange('alert_on_disappeared_competitors', e.target.checked)}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="text-sm text-gray-700">Alert on competitor changes</span>
          </label>
        </div>
      </section>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-medium text-blue-800 mb-2">How Competitive Analysis Works</h4>
        <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
          <li>Audits pull public competitor data (features, pricing, integrations, reviews) via web research</li>
          <li>Produce a 15–25 row comparison table flagging each feature as Parity, Advantage, Gap, or Differentiator, plus positioning and technical constraints</li>
          <li>When a job map exists, each competitor is scored 1–10 per job against your product, with desired-outcome coverage and a unified view of which features — ours and theirs — drive the score</li>
          <li>Evidence you attach to a competitor is routed to the relevant job and cited directly in findings; citation counts update automatically</li>
          <li>Audits feed Opportunity Synthesis, where cross-competitor opportunities are scored and high-priority ones can auto-generate ideas. Configure that in the Synthesis Hub (linked from the product dashboard).</li>
        </ul>
      </div>
    </div>
  );
}
