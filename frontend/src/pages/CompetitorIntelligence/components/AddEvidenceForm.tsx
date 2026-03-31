/**
 * AddEvidenceForm
 *
 * Form for adding evidence to the product factbase. Supports three input modes:
 * - Text: Direct title + content entry
 * - URL: Fetch content from a URL
 * - Document: Upload a file (PDF, DOCX, TXT, MD)
 *
 * Includes AI-powered competitor suggestion and ability to create new competitors.
 */

import { useState, useEffect } from "react";
import { URLFetchInput } from "../../../components/URLFetchInput";
import { FileUploadZone } from "../../../components/FileUploadZone";
import {
  createEvidence,
  suggestCompetitorForEvidence,
  getAgentCompetitors,
} from "../../../services/api";
import type {
  EvidenceType,
  AgentCompetitor,
  CompetitorSuggestion,
  URLFetchResponse,
  DocumentUploadResponse,
} from "../../../types";

type InputTab = "text" | "url" | "document";

const EVIDENCE_TYPES: { value: EvidenceType; label: string }[] = [
  { value: "competitive_intel", label: "Competitive Intel" },
  { value: "customer_interview", label: "Customer Interview" },
  { value: "market_signal", label: "Market Signal" },
  { value: "research", label: "Research" },
  { value: "analyst_report", label: "Analyst Report" },
  { value: "pricing_change", label: "Pricing Change" },
  { value: "partnership", label: "Partnership" },
  { value: "product_launch", label: "Product Launch" },
  { value: "internal_note", label: "Internal Note" },
];

interface AddEvidenceFormProps {
  productId: number;
  /** Pre-selected competitor (when opened from competitor panel) */
  preselectedCompetitorId?: number;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function AddEvidenceForm({
  productId,
  preselectedCompetitorId,
  onSuccess,
  onCancel,
}: AddEvidenceFormProps) {
  // Input mode
  const [activeTab, setActiveTab] = useState<InputTab>("text");

  // Form fields
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceDescription, setSourceDescription] = useState("");
  const [evidenceType, setEvidenceType] = useState<EvidenceType>(
    preselectedCompetitorId ? "competitive_intel" : "research"
  );
  const [tags, setTags] = useState("");

  // Competitor association
  type CompetitorMode = "existing" | "new" | "ai" | "none";
  const [competitorMode, setCompetitorMode] = useState<CompetitorMode>(
    preselectedCompetitorId ? "existing" : "none"
  );
  const [selectedCompetitorId, setSelectedCompetitorId] = useState<number | undefined>(
    preselectedCompetitorId
  );
  const [newCompetitorName, setNewCompetitorName] = useState("");
  const [newCompetitorUrl, setNewCompetitorUrl] = useState("");
  const [competitors, setCompetitors] = useState<AgentCompetitor[]>([]);

  // AI suggestion
  const [aiSuggestion, setAiSuggestion] = useState<CompetitorSuggestion | null>(null);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestionApplied, setSuggestionApplied] = useState(false);

  // Form state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Load competitors for dropdown
  useEffect(() => {
    const fetchCompetitors = async () => {
      try {
        const data = await getAgentCompetitors(productId);
        setCompetitors(data);
      } catch {
        // Silent fail — dropdown will just be empty
      }
    };
    fetchCompetitors();
  }, [productId]);

  // Handle URL fetch complete
  const handleUrlFetchComplete = (response: URLFetchResponse) => {
    setContent(response.extracted_text || "");
    setSourceUrl(response.url);
    if (response.title) {
      setTitle(response.title);
    }
    setSourceDescription(response.title || response.url);
  };

  // Handle document upload complete
  const handleDocumentUploadComplete = (response: DocumentUploadResponse) => {
    setContent(response.extracted_text || "");
    setTitle(response.filename);
    setSourceDescription(response.filename);
  };

  // Request AI suggestion
  const handleAiSuggest = async () => {
    if (!content.trim() && !title.trim()) {
      setError("Enter content first so AI can analyze it for competitor mentions.");
      return;
    }
    setIsSuggesting(true);
    setError("");
    try {
      const suggestion = await suggestCompetitorForEvidence(
        productId,
        title,
        content.slice(0, 3000)
      );
      setAiSuggestion(suggestion);
      setSuggestionApplied(false);
    } catch {
      setError("Failed to get AI suggestion. You can still select a competitor manually.");
    } finally {
      setIsSuggesting(false);
    }
  };

  // Apply AI suggestion
  const applyAiSuggestion = (action: "link" | "create" | "none") => {
    if (!aiSuggestion) return;
    setSuggestionApplied(true);

    if (action === "link" && aiSuggestion.matched_competitor_id) {
      setCompetitorMode("existing");
      setSelectedCompetitorId(aiSuggestion.matched_competitor_id);
    } else if (action === "create" && aiSuggestion.suggested_name) {
      setCompetitorMode("new");
      setNewCompetitorName(aiSuggestion.suggested_name);
    } else {
      setCompetitorMode("none");
    }
  };

  // Submit form
  const handleSubmit = async () => {
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!content.trim()) {
      setError("Content is required.");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      const parsedTags = tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      await createEvidence(productId, {
        evidence_type: evidenceType,
        title: title.trim(),
        content: content.trim(),
        source_url: sourceUrl || undefined,
        source_description: sourceDescription || undefined,
        competitor_id:
          competitorMode === "existing" ? selectedCompetitorId : undefined,
        competitor_name:
          competitorMode === "new" ? newCompetitorName : undefined,
        competitor_url:
          competitorMode === "new" ? newCompetitorUrl || undefined : undefined,
        tags: parsedTags.length > 0 ? parsedTags : undefined,
      });

      onSuccess();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to create evidence";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputTabs: { id: InputTab; label: string }[] = [
    { id: "text", label: "Text" },
    { id: "url", label: "URL" },
    { id: "document", label: "Document" },
  ];

  return (
    <div style={{
      border: "1px solid #e5e7eb",
      borderRadius: "8px",
      padding: "20px",
      backgroundColor: "#f9fafb",
      marginBottom: "16px",
    }}>
      <h3 style={{ margin: "0 0 16px 0", fontSize: "16px", fontWeight: 600 }}>
        Add Evidence
      </h3>

      {error && (
        <div style={{
          padding: "8px 12px",
          backgroundColor: "#fef2f2",
          color: "#dc2626",
          borderRadius: "6px",
          marginBottom: "12px",
          fontSize: "14px",
        }}>
          {error}
        </div>
      )}

      {/* Input mode tabs */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "16px" }}>
        {inputTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: activeTab === tab.id ? "#3b82f6" : "#d1d5db",
              backgroundColor: activeTab === tab.id ? "#eff6ff" : "white",
              color: activeTab === tab.id ? "#1d4ed8" : "#374151",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: activeTab === tab.id ? 600 : 400,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Input content */}
      {activeTab === "text" && (
        <div>
          <div style={{ marginBottom: "12px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Short headline (e.g., 'Asana launches AI triage feature')"
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                fontSize: "14px",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div style={{ marginBottom: "12px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
              Content
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Full evidence details — article summary, interview notes, research findings..."
              rows={6}
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                fontSize: "14px",
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div style={{ marginBottom: "12px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
              Source URL (optional)
            </label>
            <input
              type="text"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://..."
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                fontSize: "14px",
                boxSizing: "border-box",
              }}
            />
          </div>
        </div>
      )}

      {activeTab === "url" && (
        <div style={{ marginBottom: "12px" }}>
          <URLFetchInput
            onFetchComplete={handleUrlFetchComplete}
            onError={(err) => setError(err)}
          />
          {content && (
            <div style={{ marginTop: "8px", padding: "8px", backgroundColor: "#f0fdf4", borderRadius: "6px", fontSize: "13px", color: "#166534" }}>
              Fetched {content.length.toLocaleString()} characters from {sourceUrl}
            </div>
          )}
        </div>
      )}

      {activeTab === "document" && (
        <div style={{ marginBottom: "12px" }}>
          <FileUploadZone
            onUploadComplete={handleDocumentUploadComplete}
            onError={(err) => setError(err)}
          />
          {content && (
            <div style={{ marginTop: "8px", padding: "8px", backgroundColor: "#f0fdf4", borderRadius: "6px", fontSize: "13px", color: "#166534" }}>
              Extracted {content.length.toLocaleString()} characters from {title}
            </div>
          )}
        </div>
      )}

      {/* Title override for URL/Document modes */}
      {activeTab !== "text" && content && (
        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
            Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              fontSize: "14px",
              boxSizing: "border-box",
            }}
          />
        </div>
      )}

      {/* Evidence type */}
      <div style={{ marginBottom: "12px" }}>
        <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
          Evidence Type
        </label>
        <select
          value={evidenceType}
          onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
          style={{
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: "6px",
            fontSize: "14px",
            backgroundColor: "white",
          }}
        >
          {EVIDENCE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {/* Competitor association */}
      {!preselectedCompetitorId && (
        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "8px", color: "#374151" }}>
            Competitor Association
          </label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
            {(["none", "existing", "new", "ai"] as CompetitorMode[]).map((mode) => {
              const labels: Record<CompetitorMode, string> = {
                none: "No Competitor",
                existing: "Select Existing",
                new: "Create New",
                ai: "AI Suggest",
              };
              return (
                <button
                  key={mode}
                  onClick={() => {
                    setCompetitorMode(mode);
                    if (mode === "ai") handleAiSuggest();
                  }}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "6px",
                    border: "1px solid",
                    borderColor: competitorMode === mode ? "#3b82f6" : "#d1d5db",
                    backgroundColor: competitorMode === mode ? "#eff6ff" : "white",
                    color: competitorMode === mode ? "#1d4ed8" : "#374151",
                    cursor: "pointer",
                    fontSize: "13px",
                    fontWeight: competitorMode === mode ? 600 : 400,
                  }}
                >
                  {labels[mode]}
                </button>
              );
            })}
          </div>

          {/* Existing competitor dropdown */}
          {competitorMode === "existing" && (
            <select
              value={selectedCompetitorId || ""}
              onChange={(e) => setSelectedCompetitorId(Number(e.target.value) || undefined)}
              style={{
                padding: "8px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                fontSize: "14px",
                backgroundColor: "white",
                width: "100%",
                boxSizing: "border-box",
              }}
            >
              <option value="">Select a competitor...</option>
              {competitors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.competitor_name}
                </option>
              ))}
            </select>
          )}

          {/* New competitor form */}
          {competitorMode === "new" && (
            <div style={{ display: "flex", gap: "8px" }}>
              <input
                type="text"
                value={newCompetitorName}
                onChange={(e) => setNewCompetitorName(e.target.value)}
                placeholder="Competitor name"
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  border: "1px solid #d1d5db",
                  borderRadius: "6px",
                  fontSize: "14px",
                }}
              />
              <input
                type="text"
                value={newCompetitorUrl}
                onChange={(e) => setNewCompetitorUrl(e.target.value)}
                placeholder="Website URL (optional)"
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  border: "1px solid #d1d5db",
                  borderRadius: "6px",
                  fontSize: "14px",
                }}
              />
            </div>
          )}

          {/* AI suggestion display */}
          {competitorMode === "ai" && (
            <div>
              {isSuggesting && (
                <div style={{ padding: "12px", color: "#6b7280", fontSize: "14px" }}>
                  Analyzing content for competitor mentions...
                </div>
              )}
              {aiSuggestion && !suggestionApplied && (
                <div style={{
                  padding: "12px",
                  backgroundColor: "#eff6ff",
                  borderRadius: "6px",
                  border: "1px solid #bfdbfe",
                }}>
                  {aiSuggestion.suggested_name ? (
                    <>
                      <p style={{ margin: "0 0 8px 0", fontSize: "14px" }}>
                        This appears to reference{" "}
                        <strong>{aiSuggestion.suggested_name}</strong>
                        {aiSuggestion.matched_competitor_name &&
                          ` (matches "${aiSuggestion.matched_competitor_name}")`}
                      </p>
                      <div style={{ display: "flex", gap: "8px" }}>
                        {aiSuggestion.matched_competitor_id ? (
                          <button
                            onClick={() => applyAiSuggestion("link")}
                            style={{
                              padding: "6px 12px",
                              backgroundColor: "#3b82f6",
                              color: "white",
                              border: "none",
                              borderRadius: "6px",
                              cursor: "pointer",
                              fontSize: "13px",
                            }}
                          >
                            Link to {aiSuggestion.matched_competitor_name}
                          </button>
                        ) : (
                          <button
                            onClick={() => applyAiSuggestion("create")}
                            style={{
                              padding: "6px 12px",
                              backgroundColor: "#3b82f6",
                              color: "white",
                              border: "none",
                              borderRadius: "6px",
                              cursor: "pointer",
                              fontSize: "13px",
                            }}
                          >
                            Create &quot;{aiSuggestion.suggested_name}&quot;
                          </button>
                        )}
                        <button
                          onClick={() => applyAiSuggestion("none")}
                          style={{
                            padding: "6px 12px",
                            backgroundColor: "white",
                            color: "#374151",
                            border: "1px solid #d1d5db",
                            borderRadius: "6px",
                            cursor: "pointer",
                            fontSize: "13px",
                          }}
                        >
                          No competitor
                        </button>
                      </div>
                    </>
                  ) : (
                    <p style={{ margin: 0, fontSize: "14px", color: "#6b7280" }}>
                      No specific competitor identified in this content.
                    </p>
                  )}
                </div>
              )}
              {suggestionApplied && (
                <div style={{ padding: "8px", fontSize: "13px", color: "#166534" }}>
                  {selectedCompetitorId
                    ? `Linked to ${competitors.find((c) => c.id === selectedCompetitorId)?.competitor_name || "competitor"}`
                    : newCompetitorName
                    ? `Will create competitor "${newCompetitorName}"`
                    : "No competitor association"}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tags */}
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
          Tags (optional, comma-separated)
        </label>
        <input
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="pricing, enterprise, AI"
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: "6px",
            fontSize: "14px",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* Source description */}
      <div style={{ marginBottom: "16px" }}>
        <label style={{ display: "block", fontSize: "13px", fontWeight: 500, marginBottom: "4px", color: "#374151" }}>
          Source Description (optional)
        </label>
        <input
          type="text"
          value={sourceDescription}
          onChange={(e) => setSourceDescription(e.target.value)}
          placeholder="e.g., 'G2 review', 'Customer call with Acme Corp'"
          style={{
            width: "100%",
            padding: "8px 12px",
            border: "1px solid #d1d5db",
            borderRadius: "6px",
            fontSize: "14px",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
        <button
          onClick={onCancel}
          disabled={isSubmitting}
          style={{
            padding: "8px 16px",
            backgroundColor: "white",
            color: "#374151",
            border: "1px solid #d1d5db",
            borderRadius: "6px",
            cursor: isSubmitting ? "not-allowed" : "pointer",
            fontSize: "14px",
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={isSubmitting || !title.trim() || !content.trim()}
          style={{
            padding: "8px 16px",
            backgroundColor:
              isSubmitting || !title.trim() || !content.trim()
                ? "#93c5fd"
                : "#3b82f6",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor:
              isSubmitting || !title.trim() || !content.trim()
                ? "not-allowed"
                : "pointer",
            fontSize: "14px",
            fontWeight: 500,
          }}
        >
          {isSubmitting ? "Saving..." : "Add Evidence"}
        </button>
      </div>
    </div>
  );
}
