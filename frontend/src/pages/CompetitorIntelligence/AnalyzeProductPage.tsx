/**
 * AnalyzeProductPage
 *
 * Stage 1: Analyze a product with AI to extract features, category, target users, etc.
 * This can be used for initial analysis or re-analysis as the product evolves.
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import Navigation from '../../components/Navigation';
import SourceInput from './components/SourceInput';

interface StructuredProductData {
  product_category?: string;
  core_features?: string[];
  target_users?: string;
  value_propositions?: string[];
  competitor_search_keywords?: string[];
}

interface ProductData {
  id: number;
  product_name: string;
  product_description: string;
  product_source_type?: string;
  product_source_data?: { url?: string; filename?: string } | null;
  analysis_version: number;
}

interface AnalyzeResponse {
  analyzed_structure: StructuredProductData;
}

export default function AnalyzeProductPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<ProductData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<StructuredProductData | null>(null);
  const [sourceType, setSourceType] = useState<'text' | 'url' | 'document'>('text');
  const [sourceData, setSourceData] = useState<{ url?: string; filename?: string } | null>(null);
  const [productDescription, setProductDescription] = useState<string>('');
  const shouldAutoAnalyze = useRef<boolean>(false);

  useEffect(() => {
    if (productId) {
      fetchProduct();
    }
  }, [productId]);

  // Pre-fill source information from product
  useEffect(() => {
    if (product) {
      console.log('[AnalyzeProduct] Pre-filling from product:', {
        source_type: product.product_source_type,
        source_data: product.product_source_data,
        description_length: product.product_description?.length
      });
      setSourceType((product.product_source_type as 'text' | 'url' | 'document') || 'text');
      setSourceData(product.product_source_data || null);
      setProductDescription(product.product_description);

      // Mark for auto-analyze if this is a new product
      if (product.analysis_version === 0 && !analyzing && !analysisResult) {
        console.log('[AnalyzeProduct] New product detected, marking for auto-analysis...');
        shouldAutoAnalyze.current = true;
      }
    }
  }, [product]);

  // Auto-analyze when description is loaded for new products
  useEffect(() => {
    if (shouldAutoAnalyze.current && productDescription && productDescription.length >= 10) {
      console.log('[AnalyzeProduct] Auto-starting analysis...');
      shouldAutoAnalyze.current = false; // Prevent re-triggering
      handleAnalyze();
    }
  }, [productDescription]);

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
    console.log('[AnalyzeProduct] Starting analysis with current state:', {
      productDescription,
      sourceType,
      sourceData
    });

    try {
      setAnalyzing(true);
      setError(null);

      const payload = {
        product_description: productDescription,
        source_type: sourceType,
        source_data: sourceData
      };

      console.log('[AnalyzeProduct] Sending to API:', payload);

      // Analyze product (Stage 1) with updated description
      const response = await api.post<AnalyzeResponse>(
        `/product-intelligence/products/${productId}/analyze`,
        payload
      );

      console.log('[AnalyzeProduct] API response:', response.data);

      setAnalysisResult(response.data.analyzed_structure);

      // Refresh product to get updated analysis_version
      await fetchProduct();
    } catch (err: any) {
      console.error('[AnalyzeProduct] Error during analysis:', err);
      setError(err.message || err.data?.detail || 'Failed to analyze product');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSourceTypeChange = (type: 'text' | 'url' | 'document'): void => {
    console.log('[AnalyzeProduct] Source type changed:', type);
    setSourceType(type);
  };

  const handleSourceDataChange = (data: { url?: string; filename?: string } | null): void => {
    console.log('[AnalyzeProduct] Source data changed:', data);
    setSourceData(data);
  };

  const handleDescriptionChange = (description: string): void => {
    console.log('[AnalyzeProduct] Description changed, length:', description?.length);
    setProductDescription(description);
  };

  const handleContinue = (): void => {
    navigate(`/product-intelligence/products/${productId}`);
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
              ? `Current analysis version: ${product.analysis_version}. Run a new analysis to update.`
              : analyzing
                ? 'Step 2 of 2: AI is analyzing your product...'
                : 'Step 2 of 2: AI will analyze your product to extract features, category, and insights.'
            }
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {!analysisResult && !analyzing && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {product.analysis_version > 0 ? 'Edit Source & Description' : 'Product Source'}
            </h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Product Name
              </label>
              <p className="text-gray-900">{product.product_name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Product Description & Source
              </label>
              <SourceInput
                sourceType={sourceType}
                sourceData={sourceData}
                description={productDescription}
                onSourceTypeChange={handleSourceTypeChange}
                onSourceDataChange={handleSourceDataChange}
                onDescriptionChange={handleDescriptionChange}
                minLength={10}
              />
              <p className="mt-2 text-sm text-gray-600">
                {product.analysis_version > 0
                  ? 'You can change the source type and description before re-analyzing. The product will be analyzed with this new information.'
                  : 'Define the source of your product information before analysis.'
                }
              </p>
            </div>
          </div>
        )}

        {!analysisResult && !analyzing && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
            <h3 className="font-medium text-blue-900 mb-2">
              What will AI extract?
            </h3>
            <ul className="space-y-2 text-sm text-blue-800">
              <li className="flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Product category</span>
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Core features</span>
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Target users</span>
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Value propositions</span>
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Competitor search keywords</span>
              </li>
            </ul>
          </div>
        )}

        {analyzing && (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-4"></div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              Analyzing product with AI...
            </h3>
            <p className="text-gray-600">
              This may take 10-30 seconds. Please wait.
            </p>
          </div>
        )}

        {analysisResult && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <svg className="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <h2 className="text-lg font-semibold text-gray-900">
                Analysis Complete!
              </h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Product Category
                </label>
                <p className="text-gray-900">{analysisResult.product_category || 'N/A'}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Core Features ({analysisResult.core_features?.length || 0})
                </label>
                <ul className="list-disc list-inside space-y-1 text-gray-700">
                  {analysisResult.core_features?.map((feature, idx) => (
                    <li key={idx}>{feature}</li>
                  ))}
                </ul>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Target Users
                </label>
                <p className="text-gray-700">{analysisResult.target_users || 'N/A'}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Value Propositions
                </label>
                <ul className="list-disc list-inside space-y-1 text-gray-700">
                  {analysisResult.value_propositions?.map((vp, idx) => (
                    <li key={idx}>{vp}</li>
                  ))}
                </ul>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Competitor Search Keywords
                </label>
                <div className="flex flex-wrap gap-2">
                  {analysisResult.competitor_search_keywords?.map((keyword, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-4">
          {!analysisResult && !analyzing && (
            <>
              {product.analysis_version > 0 && (
                <button
                  onClick={handleSkip}
                  className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                >
                  Skip Re-analysis
                </button>
              )}
              <button
                onClick={handleAnalyze}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                {product.analysis_version > 0 ? 'Re-analyze with AI' : 'Analyze with AI'}
              </button>
            </>
          )}
          {analysisResult && (
            <button
              onClick={handleContinue}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              Continue to Product →
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
