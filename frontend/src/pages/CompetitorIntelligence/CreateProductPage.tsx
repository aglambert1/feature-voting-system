/**
 * CreateProductPage
 *
 * Stage 0: Create a new product with multi-source documentation support.
 * This is the first step in the independent stages flow.
 */

import { useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import Navigation from '../../components/Navigation';
import { MultiSourceInput } from '../../components/MultiSourceInput';
import { ProductSource } from '../../types';

interface FormData {
  product_name: string;
  sources: ProductSource[];
}

export default function CreateProductPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    product_name: '',
    sources: [],
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSourcesChange = (sources: ProductSource[]): void => {
    setFormData((prev) => ({
      ...prev,
      sources,
    }));
    setError(null); // Clear errors when sources change
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();

    // Validation
    if (!formData.product_name.trim()) {
      setError('Product name is required');
      return;
    }

    if (formData.sources.length === 0) {
      setError('Please add at least one source of product information');
      return;
    }

    // Concatenate all source texts for product_description
    const product_description = formData.sources
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

    // Prepare source_data for backend
    const source_data = {
      sources: formData.sources,
      concatenated_text: product_description,
      total_tokens_estimate: formData.sources.reduce(
        (sum, s) => sum + (s.token_estimate || 0),
        0
      ),
    };

    try {
      setLoading(true);
      setError(null);

      console.log('[CreateProduct] Creating product with sources:', formData.sources.length);

      // Create product (Stage 0) with multi-source support
      const response = await api.post<{ id: number }>('/product-intelligence/products', {
        product_name: formData.product_name,
        product_description,
        source_type: 'text', // Multi-source is represented as concatenated text
        source_data,
      });

      console.log('[CreateProduct] Product created:', response.data.id);
      const productId = response.data.id;

      // Navigate to analyze page with auto-analyze flag
      navigate(`/product-intelligence/products/${productId}/analyze`, {
        state: { autoAnalyze: true }
      });
    } catch (err: any) {
      setError(err.message || err.data?.detail || 'Failed to create product');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = (): void => {
    navigate('/product-intelligence');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={handleCancel}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← Back to Products
          </button>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">Create New Product</h1>
          <p className="text-gray-600">
            Step 1 of 2: Define your product with multiple sources of information. You'll analyze
            it in the next step.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Product Name */}
            <div>
              <label
                htmlFor="product_name"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Product Name *
              </label>
              <input
                type="text"
                id="product_name"
                name="product_name"
                value={formData.product_name}
                onChange={handleChange}
                placeholder="e.g., My SaaS Platform"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                maxLength={255}
              />
              <p className="mt-1 text-sm text-gray-500">
                A unique name for your product (globally unique across all users)
              </p>
            </div>

            {/* Multi-Source Input */}
            <div>
              <MultiSourceInput sources={formData.sources} onSourcesChange={handleSourcesChange} />
              <p className="mt-2 text-sm text-gray-500">
                Add one or more sources: type text directly, upload documents (PDF, DOCX, TXT, MD),
                or fetch content from URLs. All sources will be combined for AI analysis.
              </p>
            </div>

            {/* Submit Buttons */}
            <div className="border-t pt-6 flex justify-end gap-4">
              <button
                type="button"
                onClick={handleCancel}
                className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                disabled={loading || formData.sources.length === 0}
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Creating...
                  </>
                ) : (
                  'Next: Analyze Product →'
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Help Section */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">What happens next?</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">1.</span>
              <span>Your product will be created as a team resource</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">2.</span>
              <span>All sources will be combined and analyzed with AI to extract features and insights</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">3.</span>
              <span>
                You can add more sources and re-analyze your product anytime as it evolves
              </span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}
