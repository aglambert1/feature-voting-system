/**
 * TargetCustomerCard
 *
 * View/edit card for a product's target customer profile.
 * Persona name + company characteristics + key traits (one per line) + hiring criteria.
 */

import { useState } from 'react';
import type { TargetCustomerProfile } from '../../../types';

interface TargetCustomerCardProps {
  profile: TargetCustomerProfile | null;
  onSave: (profile: TargetCustomerProfile) => Promise<void>;
}

export default function TargetCustomerCard({ profile, onSave }: TargetCustomerCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [personaName, setPersonaName] = useState(profile?.persona_name ?? '');
  const [companyCharacteristics, setCompanyCharacteristics] = useState(
    profile?.company_characteristics ?? ''
  );
  const [keyTraitsText, setKeyTraitsText] = useState(
    (profile?.key_traits ?? []).join('\n')
  );
  const [hiringCriteria, setHiringCriteria] = useState(profile?.hiring_criteria ?? '');

  const startEdit = () => {
    setPersonaName(profile?.persona_name ?? '');
    setCompanyCharacteristics(profile?.company_characteristics ?? '');
    setKeyTraitsText((profile?.key_traits ?? []).join('\n'));
    setHiringCriteria(profile?.hiring_criteria ?? '');
    setError(null);
    setIsEditing(true);
  };

  const cancelEdit = () => {
    setError(null);
    setIsEditing(false);
  };

  const handleSave = async () => {
    setError(null);
    if (!personaName.trim()) {
      setError('Persona name is required.');
      return;
    }
    setSaving(true);
    try {
      const keyTraits = keyTraitsText
        .split('\n')
        .map((t) => t.trim())
        .filter((t) => t.length > 0);
      await onSave({
        persona_name: personaName.trim(),
        company_characteristics: companyCharacteristics.trim() || undefined,
        key_traits: keyTraits,
        hiring_criteria: hiringCriteria.trim() || undefined,
      });
      setIsEditing(false);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to save target customer profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Target Customer</h2>
        {!isEditing && (
          <button
            onClick={startEdit}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            {profile ? 'Edit' : 'Add profile'}
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {!isEditing && !profile && (
        <p className="text-sm text-gray-500 italic">
          No target customer profile set yet. Click <strong>Add profile</strong> to define who this
          product is for.
        </p>
      )}

      {!isEditing && profile && (
        <div className="space-y-3 text-sm">
          <div>
            <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Persona</div>
            <div className="text-gray-900 font-medium">{profile.persona_name}</div>
          </div>
          {profile.company_characteristics && (
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
                Company characteristics
              </div>
              <div className="text-gray-800 whitespace-pre-wrap">
                {profile.company_characteristics}
              </div>
            </div>
          )}
          {profile.key_traits.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Key traits</div>
              <ul className="list-disc list-inside text-gray-800 space-y-0.5">
                {profile.key_traits.map((trait, i) => (
                  <li key={i}>{trait}</li>
                ))}
              </ul>
            </div>
          )}
          {profile.hiring_criteria && (
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">
                Hiring criteria
              </div>
              <div className="text-gray-800 whitespace-pre-wrap">{profile.hiring_criteria}</div>
            </div>
          )}
        </div>
      )}

      {isEditing && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Persona name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={personaName}
              onChange={(e) => setPersonaName(e.target.value)}
              placeholder="e.g. VP of Product at a mid-market B2B SaaS"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company characteristics
            </label>
            <textarea
              value={companyCharacteristics}
              onChange={(e) => setCompanyCharacteristics(e.target.value)}
              rows={2}
              placeholder="Size, industry, geography, tech stack..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Key traits <span className="text-xs font-normal text-gray-500">(one per line)</span>
            </label>
            <textarea
              value={keyTraitsText}
              onChange={(e) => setKeyTraitsText(e.target.value)}
              rows={4}
              placeholder={'Data-driven decision maker\nOwns the roadmap\nReports to CPO'}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Hiring criteria</label>
            <textarea
              value={hiringCriteria}
              onChange={(e) => setHiringCriteria(e.target.value)}
              rows={2}
              placeholder="What signals do they look for when buying?"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={saving}
            />
          </div>

          <div className="flex gap-2 justify-end pt-2">
            <button
              onClick={cancelEdit}
              disabled={saving}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !personaName.trim()}
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
