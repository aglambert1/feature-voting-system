/**
 * SessionWorkflowPage
 *
 * Orchestrates the multi-stage competitor intelligence workflow:
 * - Stage 2: Competitor Discovery
 * - Stage 3: Competitor Feature Analysis (future)
 * - Stage 4: Comparison & Idea Generation (future)
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import Navigation from '../../components/Navigation';
import Stage2_CompetitorDiscovery from './stages/Stage2_CompetitorDiscovery';
import Stage3_FeatureExtraction from './stages/Stage3_FeatureExtraction';

export default function SessionWorkflowPage() {
  const { productId, sessionId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentStage, setCurrentStage] = useState(2); // Start at Stage 2

  useEffect(() => {
    initializeSession();
  }, [productId, sessionId]);

  const initializeSession = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch product
      const productResponse = await api.get(`/competitor-intelligence/products/${productId}`);
      setProduct(productResponse.data);

      // Verify product is analyzed
      if (!productResponse.data.structured_product_data) {
        setError('Product must be analyzed before creating a session. Please analyze the product first.');
        setLoading(false);
        return;
      }

      // If sessionId provided, fetch existing session
      if (sessionId) {
        const sessionResponse = await api.get(`/competitor-intelligence/sessions/${sessionId}`);
        setSession(sessionResponse.data);
        // Determine stage based on session status
        // (For now, default to stage 2)
        setCurrentStage(2);
      } else {
        // Create new session
        const createResponse = await api.post('/competitor-intelligence/sessions', {
          product_id: parseInt(productId),
          session_name: `${productResponse.data.product_name} - Session ${new Date().toLocaleDateString()}`,
          product_source_type: productResponse.data.product_source_type || 'text',
          product_source_data: productResponse.data.product_source_data || null,
          enable_comparison: searchParams.get('compare') === 'true'
        });

        setSession(createResponse.data);
        setCurrentStage(2);

        // Update URL to include session ID
        navigate(
          `/competitor-intelligence/products/${productId}/sessions/${createResponse.data.id}`,
          { replace: true }
        );
      }
    } catch (err) {
      console.error('Session initialization error:', err);
      setError(err.response?.data?.detail || 'Failed to initialize session');
    } finally {
      setLoading(false);
    }
  };

  const handleStage2Complete = () => {
    // Move to Stage 3 (feature analysis)
    setCurrentStage(3);
  };

  const handleStage3Complete = () => {
    // Move to Stage 4 (idea generation)
    setCurrentStage(4);
  };

  const handleBackToStage2 = () => {
    setCurrentStage(2);
  };

  const handleBack = () => {
    navigate(`/competitor-intelligence/products/${productId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex flex-col justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600 font-medium">Creating analysis session...</p>
          <p className="text-sm text-gray-500 mt-2">This should only take a moment</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-red-900 mb-2">Error</h3>
            <p className="text-red-800 mb-4">{error}</p>
            <button
              onClick={handleBack}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              ← Back to Product
            </button>
          </div>
        </main>
      </div>
    );
  }

  if (!session || !product) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={handleBack}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← Back to Product
          </button>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {session.session_name || `Session ${session.session_number}`}
          </h1>
          <p className="text-gray-600">
            {product.product_name} • {session.analysis_type === 'differential' ? 'Differential Analysis' : 'Full Analysis'}
          </p>
        </div>

        {/* Stage Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className={`flex-1 ${currentStage >= 2 ? 'text-blue-600' : 'text-gray-400'}`}>
              <div className="flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${currentStage >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'}`}>
                  2
                </div>
                <span className="ml-3 font-medium">Discover Competitors</span>
              </div>
            </div>
            <div className={`flex-1 border-t-2 ${currentStage >= 3 ? 'border-blue-600' : 'border-gray-300'} mx-4`}></div>
            <div className={`flex-1 ${currentStage >= 3 ? 'text-blue-600' : 'text-gray-400'}`}>
              <div className="flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${currentStage >= 3 ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'}`}>
                  3
                </div>
                <span className="ml-3 font-medium">Analyze Features</span>
              </div>
            </div>
            <div className={`flex-1 border-t-2 ${currentStage >= 4 ? 'border-blue-600' : 'border-gray-300'} mx-4`}></div>
            <div className={`flex-1 ${currentStage >= 4 ? 'text-blue-600' : 'text-gray-400'}`}>
              <div className="flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${currentStage >= 4 ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'}`}>
                  4
                </div>
                <span className="ml-3 font-medium">Generate Ideas</span>
              </div>
            </div>
          </div>
        </div>

        {/* Stage Content */}
        <div className="bg-white rounded-lg shadow p-6">
          {currentStage === 2 && (
            <Stage2_CompetitorDiscovery
              sessionId={session.id}
              hasPreviousAnalysis={session.analysis_type === 'differential'}
              onComplete={handleStage2Complete}
              onBack={handleBack}
            />
          )}

          {currentStage === 3 && (
            <Stage3_FeatureExtraction
              sessionId={session.id.toString()}
              hasPreviousAnalysis={session.analysis_type === 'differential'}
              onComplete={handleStage3Complete}
              onBack={handleBackToStage2}
            />
          )}

          {currentStage === 4 && (
            <div className="text-center py-12">
              <div className="mb-4">
                <svg
                  className="mx-auto h-16 w-16 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Stage 4: Idea Generation
              </h3>
              <p className="text-gray-600 mb-4">Coming soon...</p>
              <button
                onClick={() => setCurrentStage(3)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                ← Back to Stage 3
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
