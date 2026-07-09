/**
 * EvidencePage
 *
 * Full-page evidence browser for the product factbase.
 * Shows all evidence records with filters by type, competitor, and search.
 * Allows adding, viewing, and deleting evidence.
 */

import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Navigation from "../../components/Navigation";
import AddEvidenceForm from "./components/AddEvidenceForm";
import { getEvidence, getAgentCompetitors, deleteEvidence } from "../../services/api";
import api from "../../services/api";
import { formatDate } from "../../utils/date";
import type { EvidenceRecord, EvidenceType, AgentCompetitor } from "../../types";

// Type badge styling
const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  competitive_intel: { bg: "#fef3c7", text: "#92400e" },
  customer_interview: { bg: "#dbeafe", text: "#1e40af" },
  market_signal: { bg: "#f3e8ff", text: "#6b21a8" },
  research: { bg: "#e0e7ff", text: "#3730a3" },
  analyst_report: { bg: "#fce7f3", text: "#9d174d" },
  pricing_change: { bg: "#ffedd5", text: "#9a3412" },
  partnership: { bg: "#d1fae5", text: "#065f46" },
  product_launch: { bg: "#ecfdf5", text: "#047857" },
  internal_note: { bg: "#f3f4f6", text: "#374151" },
};

const TYPE_LABELS: Record<string, string> = {
  competitive_intel: "Competitive Intel",
  customer_interview: "Customer Interview",
  market_signal: "Market Signal",
  research: "Research",
  analyst_report: "Analyst Report",
  pricing_change: "Pricing Change",
  partnership: "Partnership",
  product_launch: "Product Launch",
  internal_note: "Internal Note",
};

interface ProductInfo {
  id: number;
  product_name: string;
}

export default function EvidencePage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();

  const [product, setProduct] = useState<ProductInfo | null>(null);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [competitors, setCompetitors] = useState<AgentCompetitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);

  // Filters
  const [filterType, setFilterType] = useState<EvidenceType | "">("");
  const [filterCompetitorId, setFilterCompetitorId] = useState<number | undefined>();

  // Pagination
  const [offset, setOffset] = useState(0);
  const limit = 50;

  // Load product info
  useEffect(() => {
    const fetchProduct = async () => {
      try {
        const response = await api.get(`/product-intelligence/products/${productId}`);
        setProduct(response.data);
      } catch {
        // Ignore
      }
    };
    if (productId) fetchProduct();
  }, [productId]);

  // Load competitors for filter dropdown
  useEffect(() => {
    const fetchCompetitors = async () => {
      try {
        const data = await getAgentCompetitors(Number(productId));
        setCompetitors(data);
      } catch {
        // Ignore
      }
    };
    if (productId) fetchCompetitors();
  }, [productId]);

  // Load evidence
  const fetchEvidence = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    try {
      const data = await getEvidence(
        Number(productId),
        filterCompetitorId,
        filterType || undefined,
        limit,
        offset
      );
      setEvidence(data.evidence);
      setTotalCount(data.count);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  }, [productId, filterType, filterCompetitorId, offset]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [filterType, filterCompetitorId]);

  const handleDelete = async (evidenceId: number) => {
    if (!window.confirm("Delete this evidence record?")) return;
    try {
      await deleteEvidence(Number(productId), evidenceId);
      fetchEvidence();
    } catch {
      alert("Failed to delete evidence.");
    }
  };

  const handleAddSuccess = () => {
    setShowAddForm(false);
    fetchEvidence();
  };


  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f9fafb" }}>
      <Navigation />
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "24px" }}>
        {/* Header */}
        <div style={{ marginBottom: "24px" }}>
          <button
            onClick={() => navigate(`/product-intelligence/products/${productId}`)}
            style={{
              background: "none",
              border: "none",
              color: "#6b7280",
              cursor: "pointer",
              fontSize: "14px",
              padding: "0",
              marginBottom: "8px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            &larr; Back to {product?.product_name || "Product"}
          </button>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h1 style={{ margin: 0, fontSize: "24px", fontWeight: 700, color: "#111827" }}>
                Evidence
              </h1>
              <p style={{ margin: "4px 0 0", color: "#6b7280", fontSize: "14px" }}>
                {totalCount} evidence record{totalCount !== 1 ? "s" : ""} in the factbase
              </p>
            </div>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              style={{
                padding: "8px 16px",
                backgroundColor: showAddForm ? "#ef4444" : "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: 500,
              }}
            >
              {showAddForm ? "Cancel" : "+ Add Evidence"}
            </button>
          </div>
        </div>

        {/* Add form */}
        {showAddForm && (
          <AddEvidenceForm
            productId={Number(productId)}
            onSuccess={handleAddSuccess}
            onCancel={() => setShowAddForm(false)}
          />
        )}

        {/* Filters */}
        <div style={{
          display: "flex",
          gap: "12px",
          marginBottom: "16px",
          flexWrap: "wrap",
          alignItems: "center",
        }}>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as EvidenceType | "")}
            style={{
              padding: "8px 12px",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              fontSize: "14px",
              backgroundColor: "white",
            }}
          >
            <option value="">All Types</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={filterCompetitorId || ""}
            onChange={(e) =>
              setFilterCompetitorId(e.target.value ? Number(e.target.value) : undefined)
            }
            style={{
              padding: "8px 12px",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              fontSize: "14px",
              backgroundColor: "white",
            }}
          >
            <option value="">All Competitors</option>
            {competitors.map((c) => (
              <option key={c.id} value={c.id}>
                {c.competitor_name}
              </option>
            ))}
          </select>

          {(filterType || filterCompetitorId) && (
            <button
              onClick={() => {
                setFilterType("");
                setFilterCompetitorId(undefined);
              }}
              style={{
                padding: "8px 12px",
                backgroundColor: "white",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "13px",
                color: "#6b7280",
              }}
            >
              Clear Filters
            </button>
          )}
        </div>

        {/* Evidence list */}
        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#6b7280" }}>
            Loading evidence...
          </div>
        ) : evidence.length === 0 ? (
          <div style={{
            padding: "40px",
            textAlign: "center",
            color: "#6b7280",
            backgroundColor: "white",
            borderRadius: "8px",
            border: "1px solid #e5e7eb",
          }}>
            <p style={{ fontSize: "16px", marginBottom: "8px" }}>No evidence found</p>
            <p style={{ fontSize: "14px" }}>
              {filterType || filterCompetitorId
                ? "Try adjusting your filters."
                : "Add evidence from competitive research, customer interviews, or market signals."}
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {evidence.map((ev) => {
              const typeColor = TYPE_COLORS[ev.evidence_type] ?? { bg: "#f3f4f6", text: "#374151" };
              return (
                <div
                  key={ev.id}
                  style={{
                    backgroundColor: "white",
                    border: "1px solid #e5e7eb",
                    borderRadius: "8px",
                    padding: "14px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                  }}
                >
                  {/* Type badge */}
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: 600,
                      backgroundColor: typeColor.bg,
                      color: typeColor.text,
                      whiteSpace: "nowrap",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    {TYPE_LABELS[ev.evidence_type] || ev.evidence_type}
                  </span>

                  {/* Title & details */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "14px", fontWeight: 500, color: "#111827" }}>
                      {ev.title}
                    </div>
                    <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "2px", display: "flex", gap: "12px" }}>
                      {ev.competitor_name && (
                        <span>Competitor: {ev.competitor_name}</span>
                      )}
                      {ev.source_description && (
                        <span>Source: {ev.source_description}</span>
                      )}
                      <span>{formatDate(ev.created_at)}</span>
                    </div>
                  </div>

                  {/* Source link */}
                  {ev.source_url && (
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: "#3b82f6",
                        fontSize: "13px",
                        textDecoration: "none",
                        whiteSpace: "nowrap",
                      }}
                    >
                      Source
                    </a>
                  )}

                  {/* Tags */}
                  {ev.tags && ev.tags.length > 0 && (
                    <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
                      {ev.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          style={{
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontSize: "11px",
                            backgroundColor: "#f3f4f6",
                            color: "#4b5563",
                          }}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(ev.id)}
                    title="Delete evidence"
                    style={{
                      background: "none",
                      border: "none",
                      color: "#9ca3af",
                      cursor: "pointer",
                      fontSize: "16px",
                      padding: "4px",
                      flexShrink: 0,
                    }}
                  >
                    &times;
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalCount > limit && (
          <div style={{ display: "flex", justifyContent: "center", gap: "8px", marginTop: "16px" }}>
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              style={{
                padding: "6px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                backgroundColor: "white",
                cursor: offset === 0 ? "not-allowed" : "pointer",
                opacity: offset === 0 ? 0.5 : 1,
                fontSize: "13px",
              }}
            >
              Previous
            </button>
            <span style={{ padding: "6px 12px", fontSize: "13px", color: "#6b7280" }}>
              {offset + 1}-{Math.min(offset + limit, totalCount)} of {totalCount}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= totalCount}
              style={{
                padding: "6px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                backgroundColor: "white",
                cursor: offset + limit >= totalCount ? "not-allowed" : "pointer",
                opacity: offset + limit >= totalCount ? 0.5 : 1,
                fontSize: "13px",
              }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
