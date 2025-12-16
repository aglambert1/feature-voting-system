/**
 * ProductDetailPage
 *
 * Detailed view of a single product with current analysis and history
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import api from '../../services/api';
import Navigation from '../../components/Navigation';

export default function ProductDetailPage() {
  const { productId } = useParams();
  const [product, setProduct] = useState(null);
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedVersions, setExpandedVersions] = useState(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    if (productId) {
      fetchProductData();
    }
  }, [productId]);

  const fetchProductData = async () => {
    try {
      setLoading(true);

      // Fetch product details
      const productResponse = await api.get(`/competitor-intelligence/products/${productId}`);
      setProduct(productResponse.data);

      // Fetch analysis history if product has been analyzed
      if (productResponse.data.analysis_version > 0) {
        const historyResponse = await api.get(
          `/competitor-intelligence/products/${productId}/analysis-history`
        );
        setAnalysisHistory(historyResponse.data);
      }
    } catch (err) {
      setError(err.message || err.data?.detail || 'Failed to load product');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = () => {
    navigate(`/competitor-intelligence/products/${productId}/analyze`);
  };

  const handleFindCompetitors = async () => {
    // Check for existing sessions and reuse the most recent one
    try {
      const sessionsResponse = await api.get(`/competitor-intelligence/sessions/products/${productId}/sessions`);
      const sessions = sessionsResponse.data || [];

      // Find the most recent session
      if (sessions.length > 0) {
        const mostRecentSession = sessions[0]; // Sessions are ordered by creation date (newest first)
        console.log('[ProductDetail] Reusing existing session:', mostRecentSession.id);
        navigate(`/competitor-intelligence/products/${productId}/sessions/${mostRecentSession.id}`);
      } else {
        // No existing sessions - create new one
        console.log('[ProductDetail] No existing sessions, creating new one');
        navigate(`/competitor-intelligence/products/${productId}/sessions`);
      }
    } catch (err) {
      console.error('[ProductDetail] Failed to check existing sessions:', err);
      // Fall back to creating new session
      navigate(`/competitor-intelligence/products/${productId}/sessions`);
    }
  };

  const toggleVersionExpanded = (versionId) => {
    setExpandedVersions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(versionId)) {
        newSet.delete(versionId);
      } else {
        newSet.add(versionId);
      }
      return newSet;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error || 'Product not found'}</p>
          </div>
        </main>
      </div>
    );
  }

  const currentAnalysis = product.structured_product_data;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={() => navigate('/competitor-intelligence')}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← Back to Products
          </button>

          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-3">
                {product.product_name}
              </h1>
              <div className="flex flex-wrap gap-2">
                {product.analysis_version > 0 ? (
                  <span className="inline-block px-3 py-1 bg-green-100 text-green-800 text-sm rounded-full font-medium">
                    ✓ Analyzed (v{product.analysis_version})
                  </span>
                ) : (
                  <span className="inline-block px-3 py-1 bg-yellow-100 text-yellow-800 text-sm rounded-full font-medium">
                    Not Analyzed
                  </span>
                )}
                {product.product_category && (
                  <span className="inline-block px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full font-medium">
                    {product.product_category}
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-3">
              {product.analysis_version > 0 && (
                <button
                  onClick={handleFindCompetitors}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  Find Competitors
                </button>
              )}
              <button
                onClick={handleAnalyze}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                {product.analysis_version > 0 ? 'Re-analyze Product' : 'Analyze Product'}
              </button>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Product Description
          </h2>
          <p className="text-gray-700 mb-3">{product.product_description}</p>
          {product.product_source_type && product.product_source_type !== 'text' && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Source:</span>{' '}
                <span className="capitalize">{product.product_source_type}</span>
                {product.product_source_data?.url && (
                  <span className="ml-2 text-blue-600">
                    <a href={product.product_source_data.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {product.product_source_data.url}
                    </a>
                  </span>
                )}
                {product.product_source_data?.filename && (
                  <span className="ml-2">: {product.product_source_data.filename}</span>
                )}
              </p>
            </div>
          )}
        </div>

        {currentAnalysis && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Current Analysis (Version {product.analysis_version})
            </h2>
            <div className="space-y-4">
              {currentAnalysis.core_features && currentAnalysis.core_features.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Core Features ({currentAnalysis.core_features.length})
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {currentAnalysis.core_features.map((feature, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-gray-700">
                        <svg className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {currentAnalysis.target_users && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Users
                  </label>
                  <p className="text-gray-700">{currentAnalysis.target_users}</p>
                </div>
              )}

              {currentAnalysis.value_propositions && currentAnalysis.value_propositions.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Value Propositions
                  </label>
                  <ul className="space-y-2">
                    {currentAnalysis.value_propositions.map((vp, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-gray-700">
                        <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span>{vp}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {currentAnalysis.competitor_search_keywords && currentAnalysis.competitor_search_keywords.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Competitor Search Keywords
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {currentAnalysis.competitor_search_keywords.map((keyword, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Analysis History ({analysisHistory.length})
          </h2>

          {analysisHistory.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-gray-500 mb-4">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <p className="text-gray-500 mb-4">No analyses yet</p>
              <button
                onClick={handleAnalyze}
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                Run your first analysis
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {analysisHistory.map((analysis) => (
                <div
                  key={analysis.id}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="font-medium text-gray-900">
                        Version {analysis.analysis_version}
                        {analysis.analysis_version === product.analysis_version && (
                          <span className="ml-2 text-xs text-green-600 font-semibold">
                            (Current)
                          </span>
                        )}
                      </h3>
                      <p className="text-sm text-gray-500">
                        Analyzed {formatDistanceToNow(new Date(analysis.created_at), {
                          addSuffix: true,
                        })}
                      </p>
                    </div>
                    {analysis.tokens_used && (
                      <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">
                        {analysis.tokens_used} tokens
                      </span>
                    )}
                  </div>
                  {analysis.analyzed_structure && (
                    <div className="mt-3 text-sm text-gray-600 space-y-1">
                      <p>
                        {analysis.analyzed_structure.core_features?.length || 0} features •{' '}
                        {analysis.analyzed_structure.value_propositions?.length || 0} value props
                      </p>
                      {analysis.product_source_type && analysis.product_source_type !== 'text' && (
                        <p className="text-xs">
                          <span className="font-medium">Source:</span>{' '}
                          <span className="capitalize">{analysis.product_source_type}</span>
                          {analysis.product_source_data?.url && (
                            <span className="ml-1 text-blue-600">
                              <a href={analysis.product_source_data.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                                {analysis.product_source_data.url}
                              </a>
                            </span>
                          )}
                          {analysis.product_source_data?.filename && (
                            <span className="ml-1">: {analysis.product_source_data.filename}</span>
                          )}
                        </p>
                      )}
                    </div>
                  )}
                  {analysis.product_description && (
                    <div className="mt-3 border-t border-gray-200 pt-3">
                      <button
                        onClick={() => toggleVersionExpanded(analysis.id)}
                        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
                      >
                        {expandedVersions.has(analysis.id) ? (
                          <>
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                            Hide Product Description
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                            View Product Description
                          </>
                        )}
                      </button>
                      {expandedVersions.has(analysis.id) && (
                        <div className="mt-2 p-3 bg-gray-50 rounded text-sm text-gray-700 whitespace-pre-wrap">
                          {analysis.product_description}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
