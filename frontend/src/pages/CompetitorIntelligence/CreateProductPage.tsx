/**
 * CreateProductPage
 *
 * Stage 0: Create a new product without automatic analysis.
 * This is the first step in the independent stages flow.
 */

import { useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import Navigation from '../../components/Navigation';
import SourceInput from './components/SourceInput';

interface FormData {
  product_name: string;
  product_description: string;
  source_type: 'text' | 'url' | 'document';
  source_data: { url?: string; filename?: string } | null;
}

export default function CreateProductPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    product_name: '',
    product_description: '',
    source_type: 'text',
    source_data: null
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSourceTypeChange = (type: 'text' | 'url' | 'document'): void => {
    setFormData(prev => ({
      ...prev,
      source_type: type,
      source_data: null  // Reset source data when switching types
    }));
  };

  const handleSourceDataChange = (data: { url?: string; filename?: string } | null): void => {
    setFormData(prev => ({
      ...prev,
      source_data: data
    }));
  };

  const handleDescriptionChange = (description: string): void => {
    console.log('[CreateProduct] Description changed:', description);
    setFormData(prev => {
      const newData = {
        ...prev,
        product_description: description
      };
      console.log('[CreateProduct] Updated formData:', newData);
      return newData;
    });
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();

    console.log('[CreateProduct] Submitting with formData:', formData);

    // Validation
    if (!formData.product_name.trim()) {
      setError('Product name is required');
      return;
    }
    if (formData.product_description.length < 10) {
      setError('Product description must be at least 10 characters');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      console.log('[CreateProduct] Sending to API:', formData);
      // Create product (Stage 0)
      const response = await api.post<{ id: number }>('/product-intelligence/products', formData);
      console.log('[CreateProduct] API response:', response.data);
      const productId = response.data.id;

      // Navigate to analyze page
      navigate(`/product-intelligence/products/${productId}/analyze`);
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

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={handleCancel}
            className="text-blue-600 hover:text-blue-800 mb-4 font-medium"
          >
            ← Back to Products
          </button>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Create New Product
          </h1>
          <p className="text-gray-600">
            Step 1 of 2: Define your product. You'll analyze it in the next step.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
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

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Product Description *
              </label>
              <SourceInput
                sourceType={formData.source_type}
                sourceData={formData.source_data}
                description={formData.product_description}
                onSourceTypeChange={handleSourceTypeChange}
                onSourceDataChange={handleSourceDataChange}
                onDescriptionChange={handleDescriptionChange}
                minLength={10}
              />
              <p className="mt-2 text-sm text-gray-500">
                Select source type and provide product description. This will be used for AI analysis in the next step.
              </p>
            </div>

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
                disabled={loading}
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

        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-900 mb-2">
            What happens next?
          </h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">1.</span>
              <span>Your product will be created as a team resource</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">2.</span>
              <span>You'll be taken to the analysis page to extract features and insights</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 font-bold">3.</span>
              <span>You can re-analyze your product anytime as it evolves</span>
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
}
