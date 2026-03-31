/**
 * CompetitorEvidencePanel
 *
 * Compact panel showing evidence linked to a specific competitor.
 * Used inline within the CompetitorReportsTab to show per-competitor evidence.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import AddEvidenceForm from "./AddEvidenceForm";
import { getEvidence, deleteEvidence } from "../../../services/api";
import type { EvidenceRecord } from "../../../types";

const TYPE_LABELS: Record<string, string> = {
  competitive_intel: "Competitive",
  customer_interview: "Customer",
  market_signal: "Market",
  research: "Research",
  analyst_report: "Analyst",
  pricing_change: "Pricing",
  partnership: "Partnership",
  product_launch: "Launch",
  internal_note: "Note",
};

interface CompetitorEvidencePanelProps {
  productId: number;
  competitorId: number;
  competitorName: string;
}

export default function CompetitorEvidencePanel({
  productId,
  competitorId,
  competitorName,
}: CompetitorEvidencePanelProps) {
  const navigate = useNavigate();
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);

  const fetchEvidence = useCallback(async () => {
    try {
      const data = await getEvidence(productId, competitorId, undefined, 10);
      setEvidence(data.evidence);
      setTotalCount(data.count);
    } catch {
      // Silent
    } finally {
      setLoading(false);
    }
  }, [productId, competitorId]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  const handleDelete = async (evidenceId: number) => {
    if (!window.confirm("Delete this evidence?")) return;
    try {
      await deleteEvidence(productId, evidenceId);
      fetchEvidence();
    } catch {
      // Silent
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <div style={{ padding: "12px", color: "#6b7280", fontSize: "13px" }}>
        Loading evidence...
      </div>
    );
  }

  return (
    <div style={{
      borderTop: "1px solid #e5e7eb",
      padding: "12px 0",
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "8px",
      }}>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "#374151" }}>
          Evidence ({totalCount})
        </span>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            style={{
              padding: "4px 10px",
              fontSize: "12px",
              backgroundColor: showAddForm ? "#fee2e2" : "#eff6ff",
              color: showAddForm ? "#dc2626" : "#1d4ed8",
              border: "1px solid",
              borderColor: showAddForm ? "#fca5a5" : "#bfdbfe",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: 500,
            }}
          >
            {showAddForm ? "Cancel" : "+ Add"}
          </button>
          {totalCount > 0 && (
            <button
              onClick={() =>
                navigate(
                  `/product-intelligence/products/${productId}/evidence?competitor=${competitorId}`
                )
              }
              style={{
                padding: "4px 10px",
                fontSize: "12px",
                backgroundColor: "white",
                color: "#6b7280",
                border: "1px solid #d1d5db",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              View All
            </button>
          )}
        </div>
      </div>

      {showAddForm && (
        <AddEvidenceForm
          productId={productId}
          preselectedCompetitorId={competitorId}
          onSuccess={() => {
            setShowAddForm(false);
            fetchEvidence();
          }}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {evidence.length === 0 && !showAddForm ? (
        <div style={{
          padding: "12px",
          textAlign: "center",
          color: "#9ca3af",
          fontSize: "13px",
          backgroundColor: "#f9fafb",
          borderRadius: "6px",
        }}>
          No evidence for {competitorName} yet
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          {evidence.map((ev) => (
            <div
              key={ev.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 8px",
                backgroundColor: "#f9fafb",
                borderRadius: "4px",
                fontSize: "13px",
              }}
            >
              <span style={{
                padding: "1px 6px",
                borderRadius: "3px",
                fontSize: "10px",
                fontWeight: 600,
                backgroundColor: "#e5e7eb",
                color: "#374151",
                whiteSpace: "nowrap",
                textTransform: "uppercase",
              }}>
                {TYPE_LABELS[ev.evidence_type] || ev.evidence_type}
              </span>
              <span style={{ flex: 1, color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.title}
              </span>
              <span style={{ color: "#9ca3af", fontSize: "11px", flexShrink: 0 }}>
                {formatDate(ev.created_at)}
              </span>
              {ev.source_url && (
                <a
                  href={ev.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "#3b82f6", fontSize: "11px", textDecoration: "none", flexShrink: 0 }}
                >
                  Link
                </a>
              )}
              <button
                onClick={() => handleDelete(ev.id)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#d1d5db",
                  cursor: "pointer",
                  fontSize: "14px",
                  padding: "0 2px",
                  flexShrink: 0,
                }}
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
