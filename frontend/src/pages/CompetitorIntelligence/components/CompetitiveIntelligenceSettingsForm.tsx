/**
 * CompetitiveIntelligenceSettingsForm
 *
 * Shared form component for Competitive Intelligence Agent configuration.
 * Used by both CompetitiveIntelligenceSetupModal and AgentSettingsTab.
 *
 * Settings:
 * - Schedule mode (manual/scheduled) and frequency
 * - Advanced: separate schedules for discovery vs analysis
 * - Feature similarity threshold for clustering
 * - Auto-generate ideas toggle and threshold
 * - Alerts for competitor changes
 */

import { useState, useEffect } from 'react';
import { CompetitiveAgentConfig, ScheduleFrequency } from '../../../types';

export interface SettingsFormData {
  competitor_discovery_mode?: 'manual' | 'scheduled';
  competitor_discovery_schedule?: ScheduleFrequency;
  deep_analysis_mode?: 'manual' | 'scheduled';
  deep_analysis_schedule?: ScheduleFrequency;
  intensity_similarity_threshold?: number;
  intensity_idea_threshold?: number;
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

  // Derived values for UI
  // V2: Priority score threshold (0.0-1.0) instead of competitor count
  const priorityThreshold = getValue('intensity_idea_threshold') ?? 0;
  const autoGenerateIdeas = priorityThreshold > 0;
  // Display threshold as percentage for clarity
  const priorityThresholdDisplay = Math.round(priorityThreshold * 100);

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
                          Last run: {new Date(config.competitor_discovery_last_run).toLocaleString()}
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
                          Last run: {new Date(config.deep_analysis_last_run).toLocaleString()}
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
            Last run: {new Date(config.deep_analysis_last_run).toLocaleString()}
          </p>
        )}
      </section>

      {/* Idea Generation Settings Section */}
      <section className="bg-gray-50 rounded-lg p-5">
        <h3 className="text-md font-medium text-gray-900 mb-4">Idea Generation</h3>

        {/* Auto-generate Ideas Toggle */}
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={autoGenerateIdeas}
              onChange={(e) => {
                if (e.target.checked) {
                  handleChange('intensity_idea_threshold', 0.7);  // Default to High priority
                } else {
                  handleChange('intensity_idea_threshold', 0);
                }
              }}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="text-sm text-gray-700">Auto-generate ideas from competitive analysis</span>
          </label>

          {/* Idea Generation Threshold - only shown when auto-generate is enabled */}
          {autoGenerateIdeas && (
            <div className="ml-7 space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Minimum Priority Score: {priorityThresholdDisplay}%
                </label>
                <input
                  type="range"
                  min="50"
                  max="90"
                  step="5"
                  value={priorityThresholdDisplay}
                  onChange={(e) => handleChange('intensity_idea_threshold', parseInt(e.target.value) / 100)}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>50% (More ideas)</span>
                  <span>90% (Critical only)</span>
                </div>
              </div>

              {/* Priority level indicator */}
              <div className="bg-gray-100 rounded-lg p-3 text-xs">
                <div className="font-medium text-gray-700 mb-1">Current threshold will generate:</div>
                <div className="text-gray-600">
                  {priorityThreshold >= 0.85 ? (
                    <span className="text-red-600 font-medium">🔴 Critical priority only</span>
                  ) : priorityThreshold >= 0.7 ? (
                    <span className="text-orange-600 font-medium">🟠 High priority and above</span>
                  ) : (
                    <span className="text-yellow-600 font-medium">🟡 Medium priority and above</span>
                  )}
                </div>
              </div>

              {/* Help text explaining priority score */}
              <div className="text-xs text-gray-500 space-y-1">
                <p className="font-medium">Priority score is calculated based on:</p>
                <ul className="list-disc list-inside space-y-0.5 ml-1">
                  <li>Market prevalence — how many competitors have this feature</li>
                  <li>User value — severity of the pain point being addressed</li>
                  <li>Evidence quality — supporting quotes from competitor analysis</li>
                  <li>Table Stakes vs Innovation — industry expectation level</li>
                </ul>
              </div>
            </div>
          )}
        </div>
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
          <li>Functional audits analyze each competitor's features against your product</li>
          <li>Landscape synthesis identifies feature opportunities across all competitors</li>
          <li>Each opportunity receives a priority score based on market prevalence and user value</li>
          <li>High-priority opportunities can automatically generate product ideas for voting</li>
        </ul>
      </div>
    </div>
  );
}
