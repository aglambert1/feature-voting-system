/**
 * AnalyzeProductPage
 *
 * Stage 1: Analyze a product with AI to extract features, category, target users, etc.
 * Supports multi-source documentation and re-analysis.
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../../services/api';
import Navigation from '../../components/Navigation';
import { MultiSourceInput } from '../../components/MultiSourceInput';
import { ProductSource } from '../../types';

interface ProductData {
  id: number;
  product_name: string;
  product_description: string;
  product_source_type?: string;
  product_source_data?: any;
  analysis_version: number;
}

export default function AnalyzeProductPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [product, setProduct] = useState<ProductData | null>(null);
  const [sources, setSources] = useState<ProductSource[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const initialSourcesLoaded = useRef<boolean>(false);
  const autoAnalyzeTriggered = useRef<boolean>(false);

  // Check if we should auto-analyze (navigated from CreateProductPage)
  const autoAnalyze = (location.state as { autoAnalyze?: boolean })?.autoAnalyze ?? false;

  useEffect(() => {
    if (productId) {
      fetchProduct();
    }
  }, [productId]);

  // Parse existing product sources from source_data
  useEffect(() => {
    if (product && !initialSourcesLoaded.current) {
      try {
        let loadedSources: ProductSource[] = [];

        if (product.product_source_data) {
          // Try to extract sources from source_data
          const sourceData = product.product_source_data;

          if (sourceData.sources && Array.isArray(sourceData.sources)) {
            // Multi-source format
            loadedSources = sourceData.sources;
          } else if (product.product_description) {
            // Legacy single-source format - create a single text source
            loadedSources = [{
              type: 'text',
              content: product.product_description,
              extracted_text: product.product_description,
              token_estimate: Math.floor(product.product_description.length / 4),
            }];
          }
        } else if (product.product_description) {
          // No source_data at all - create a single text source from product_description
          loadedSources = [{
            type: 'text',
            content: product.product_description,
            extracted_text: product.product_description,
            token_estimate: Math.floor(product.product_description.length / 4),
          }];
        }

        setSources(loadedSources);

        // Mark that initial sources have been loaded
        initialSourcesLoaded.current = true;
      } catch (err) {
        console.error('[AnalyzeProduct] Failed to parse sources:', err);
        // Fallback to single text source
        if (product.product_description) {
          setSources([{
            type: 'text',
            content: product.product_description,
            extracted_text: product.product_description,
            token_estimate: Math.floor(product.product_description.length / 4),
          }]);
        }
        initialSourcesLoaded.current = true;
      }
    }
  }, [product]);

  const fetchProduct = async (): Promise<void> => {
    try {
      setLoading(true);
      const response = await api.get<ProductData>(`/product-intelligence/products/${productId}`);
      setProduct(response.data);
    } catch (err: any) {
      setError(err.message || err.data?.detail || 'Failed to load product');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (): Promise<void> => {
    if (sources.length === 0) {
      setError('Please add at least one source of product information');
      return;
    }

    console.log('[AnalyzeProduct] Starting analysis with', sources.length, 'sources');

    try {
      setAnalyzing(true);
      setError(null);

      // Concatenate all source texts for product_description
      const product_description = sources
        .map((source, index) => {
          const label =
            source.type === 'text'
              ? `Source ${index + 1}: Text Description`
              : source.type === 'document'
              ? `Source ${index + 1}: ${source.filename}`
              : `Source ${index + 1}: ${source.title || source.url}`;

          return `===== ${label.toUpperCase()} =====\n${source.extracted_text || source.content || ''}`;
        })
        .join('\n\n');

      // Prepare payload
      const payload = {
        product_description,
        source_type: 'text', // Multi-source represented as concatenated text
        source_data: {
          sources,
          concatenated_text: product_description,
          total_tokens_estimate: sources.reduce((sum, s) => sum + (s.token_estimate || 0), 0),
        },
      };

      console.log('[AnalyzeProduct] Sending to API with', payload.source_data.total_tokens_estimate, 'tokens');

      // Analyze product (Stage 1)
      await api.post(
        `/product-intelligence/products/${productId}/analyze`,
        payload
      );

      console.log('[AnalyzeProduct] Analysis complete');

      // Redirect directly to product detail page after successful analysis
      navigate(`/product-intelligence/products/${productId}`);
    } catch (err: any) {
      console.error('[AnalyzeProduct] Error during analysis:', err);
      setError(err.message || err.data?.detail || 'Failed to analyze product');
      setAnalyzing(false);
    }
  };

  // Auto-trigger analysis if navigated from CreateProductPage
  useEffect(() => {
    if (autoAnalyze && sources.length > 0 && !autoAnalyzeTriggered.current && !analyzing) {
      autoAnalyzeTriggered.current = true;
      handleAnalyze();
    }
  }, [autoAnalyze, sources, analyzing]);

  const handleSourcesChange = (newSources: ProductSource[]): void => {
    setSources(newSources);
    setError(null);
  };

  const handleSkip = (): void => {
    navigate(`/product-intelligence/products/${productId}`);
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

  if (error && !product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        </main>
      </div>
    );
  }

  if (!product) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={() => navigate(`/product-intelligence/products/${productId}`)}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← Back to Product
          </button>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {product.analysis_version > 0 ? 'Re-analyze' : 'Analyze'} Product
          </h1>
          <p className="text-gray-600">
            {product.analysis_version > 0
              ? `Current analysis version: ${product.analysis_version}. Add or modify sources and run a new analysis to update.`
              : analyzing
              ? 'AI is analyzing your product...'
              : 'Review your product information and click "Analyze Product" when ready.'}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {!analyzing && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {product.analysis_version > 0 ? 'Edit Product Information' : 'Product Information'}
            </h2>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Product Name
              </label>
              <p className="text-gray-900 font-medium">{product.product_name}</p>
            </div>

            <div>
              <MultiSourceInput sources={sources} onSourcesChange={handleSourcesChange} />
              <p className="mt-2 text-sm text-gray-600">
                {product.analysis_version > 0
                  ? 'You can add, remove, or modify sources before re-analyzing. All sources will be combined for AI analysis.'
                  : 'Add one or more sources: type text directly, upload documents (PDF, DOCX, TXT, MD), or fetch content from URLs.'}
              </p>
            </div>
          </div>
        )}

        {!analyzing && (
          <div className="flex justify-end gap-4 mb-6">
            <button
              onClick={handleSkip}
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleAnalyze}
              disabled={sources.length === 0}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {product.analysis_version > 0 ? 'Re-analyze Product' : 'Analyze Product'}
            </button>
          </div>
        )}

        {analyzing && (
          <div className="bg-white rounded-lg shadow p-8 mb-6">
            <div className="flex flex-col items-center justify-center space-y-4">
              <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600"></div>
              <h3 className="text-lg font-semibold text-gray-900">Analyzing Product...</h3>
              <p className="text-sm text-gray-600 text-center max-w-md">
                AI is extracting features, categorizing, identifying target users, and generating competitor search keywords.
                This may take a minute.
              </p>
            </div>
          </div>
        )}

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">What happens during analysis?</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">•</span>
              <span>AI extracts core features and categorizes your product</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">•</span>
              <span>Identifies target user segments and value propositions</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">•</span>
              <span>Generates keywords for finding competitors</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">•</span>
              <span>Creates vector embeddings for semantic search</span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}
