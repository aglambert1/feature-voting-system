/**
 * SessionWorkflowPage
 *
 * Orchestrates the multi-stage competitor intelligence workflow:
 * - Stage 2: Competitor Discovery
 * - Stage 3: Competitor Feature Analysis (future)
 * - Stage 4: Comparison & Idea Generation (future)
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import Navigation from '../../components/Navigation';
import Stage2_CompetitorDiscovery from './stages/Stage2_CompetitorDiscovery';
import Stage3_FeatureExtraction from './stages/Stage3_FeatureExtraction';
import Stage4_IdeaGeneration from './stages/Stage4_IdeaGeneration';
import Stage5_Finalization from './stages/Stage5_Finalization';

interface Session {
  id: number;
  session_name: string;
  session_number: number;
  analysis_type: 'differential' | 'full';
  comparison_to_session_id?: number | null;
}

interface ProductData {
  id: number;
  product_name: string;
  structured_product_data?: Record<string, any>;
  product_source_type?: string;
  product_source_data?: Record<string, any> | null;
}

export default function SessionWorkflowPage() {
  const { productId, sessionId } = useParams<{ productId: string; sessionId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const initializingRef = useRef<boolean>(false);

  const [session, setSession] = useState<Session | null>(null);
  const [product, setProduct] = useState<ProductData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<number>(2); // Start at Stage 2
  const [stage2State, setStage2State] = useState<any>(null); // Stage 2 state cache for back navigation
  const [stage3State, setStage3State] = useState<any>(null); // Stage 3 state cache for back navigation
  const [_stage4State, _setStage4State] = useState<any>(null); // Stage 4 state cache for back navigation

  useEffect(() => {
    // Only initialize once - prevent double-init in React StrictMode
    if (!initializingRef.current) {
      initializeSession();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, sessionId]);

  const initializeSession = async (): Promise<void> => {
    // Use ref for synchronous race condition protection
    if (initializingRef.current) return;
    initializingRef.current = true;

    try {
      setLoading(true);
      setError(null);

      // Fetch product
      const productResponse = await api.get<ProductData>(`/product-intelligence/products/${productId}`);
      setProduct(productResponse.data);

      // Verify product is analyzed
      if (!productResponse.data.structured_product_data) {
        setError('Product must be analyzed before creating a session. Please analyze the product first.');
        setLoading(false);
        return;
      }

      // If sessionId provided, fetch existing session
      if (sessionId) {
        const sessionResponse = await api.get<Session>(`/product-intelligence/sessions/${sessionId}`);
        setSession(sessionResponse.data);
        // Determine stage based on session status
        // (For now, default to stage 2)
        setCurrentStage(2);
        setLoading(false); // Transition to stage UI
      } else {
        // Fetch previous sessions to check for ones with competitors
        let previousSessionId: number | null = null;
        try {
          const sessionsResponse = await api.get<any[]>(`/product-intelligence/sessions/products/${productId}/sessions`);
          const sessions = sessionsResponse.data || [];
          console.log('[SessionWorkflow] Previous sessions:', sessions);

          // Find the most recent session with selected competitors
          for (const session of sessions) {
            if (session.competitors_count > 0) {
              previousSessionId = session.id;
              console.log('[SessionWorkflow] Found previous session with competitors:', previousSessionId, 'count:', session.competitors_count);
              break;
            }
          }

          if (!previousSessionId) {
            console.log('[SessionWorkflow] No previous session with competitors found');
          }
        } catch (err) {
          console.error('Failed to fetch previous sessions:', err);
          // Continue anyway - we'll just do fresh discovery
        }

        // Create new session
        const enableComparison = searchParams.get('compare') === 'true';
        const compareToSessionId = searchParams.get('compareToSession');

        const createResponse = await api.post<Session>('/product-intelligence/sessions', {
          product_id: parseInt(productId!),
          session_name: `${productResponse.data.product_name} - Session ${new Date().toLocaleDateString()}`,
          product_source_type: productResponse.data.product_source_type || 'text',
          product_source_data: productResponse.data.product_source_data || null,
          enable_comparison: enableComparison,
          compare_to_session_id: compareToSessionId ? parseInt(compareToSessionId) : null,
          previous_session_id: previousSessionId  // Backward compatibility
        });

        // Backend now returns comparison_to_session_id in response
        setSession(createResponse.data);
        setCurrentStage(2);
        setLoading(false); // Transition to stage UI immediately

        // Update URL to include session ID
        navigate(
          `/product-intelligence/products/${productId}/sessions/${createResponse.data.id}`,
          { replace: true }
        );
      }
    } catch (err: any) {
      console.error('Session initialization error:', err);
      setError(err.response?.data?.detail || 'Failed to initialize session');
      setLoading(false); // Stop loading on error
    }
  };

  const handleStage2Complete = (): void => {
    // Move to Stage 3 (feature analysis)
    // Clear any old Stage 3 state since competitor selection may have changed
    setStage3State(null);
    setCurrentStage(3);
  };

  const handleStage3Complete = (): void => {
    // Move to Stage 4 (idea generation)
    setCurrentStage(4);
  };

  const handleStage4Complete = (): void => {
    // Move to Stage 5 (finalization)
    setCurrentStage(5);
  };

  const handleBackToStage2 = (): void => {
    // Clear stage 3 state so feature extraction restarts when returning
    setStage3State(null);
    setCurrentStage(2);
  };

  const handleBackToStage3 = (): void => {
    setCurrentStage(3);
  };

  const handleBackToStage4 = (): void => {
    setCurrentStage(4);
  };

  const handleBack = (): void => {
    navigate(`/product-intelligence/products/${productId}`);
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
            <div className={`flex-1 border-t-2 ${currentStage >= 5 ? 'border-blue-600' : 'border-gray-300'} mx-4`}></div>
            <div className={`flex-1 ${currentStage >= 5 ? 'text-blue-600' : 'text-gray-400'}`}>
              <div className="flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${currentStage >= 5 ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'}`}>
                  5
                </div>
                <span className="ml-3 font-medium">Finalize & Submit</span>
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
              savedState={stage2State}
              onStateChange={setStage2State}
              previousSessionId={session.comparison_to_session_id}
            />
          )}

          {currentStage === 3 && (
            <Stage3_FeatureExtraction
              sessionId={session.id.toString()}
              hasPreviousAnalysis={session.analysis_type === 'differential'}
              onComplete={handleStage3Complete}
              onBack={handleBackToStage2}
              savedState={stage3State}
              onStateChange={setStage3State}
              previousSessionId={session.comparison_to_session_id}
            />
          )}

          {currentStage === 4 && (
            <Stage4_IdeaGeneration
              sessionId={session.id}
              onComplete={handleStage4Complete}
              onBack={handleBackToStage3}
            />
          )}

          {currentStage === 5 && (
            <Stage5_Finalization
              sessionId={session.id}
              onBack={handleBackToStage4}
            />
          )}
        </div>
      </main>
    </div>
  );
}
