/**
 * SubmitIdeaPage
 *
 * AI-powered idea submission flow:
 * Step 1: Freeform text input
 *   - Large textarea for user to describe idea
 *   - "Structure with AI" button
 *   - Loading state during AI processing
 *
 * Step 2: AI-structured output
 *   - Show AI-generated fields (what, why, use_case)
 *   - Editable inputs for each field
 *   - Title field (required)
 *   - "Submit Idea" button
 *   - "Start Over" button
 */

import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { structureText, submitIdea } from '../services/api';
import api from '../services/api';
import Navigation from '../components/Navigation';

const SubmitIdeaPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Step management (1 = freeform input, 2 = structured editing)
  const [step, setStep] = useState(1);

  // Form data
  const [freeformText, setFreeformText] = useState('');
  const [structuredData, setStructuredData] = useState({
    title: '',
    what_description: '',
    why_description: '',
    use_case_description: '',
  });

  // Product selection
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState(null);
  const [hasProducts, setHasProducts] = useState(true);
  const [loadingProducts, setLoadingProducts] = useState(true);

  // UI state
  const [isStructuring, setIsStructuring] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Fetch products on mount
  useEffect(() => {
    fetchProducts();
  }, []);

  /**
   * Fetch products from API
   */
  const fetchProducts = async () => {
    try {
      setLoadingProducts(true);
      const response = await api.get('/ideas/products');
      setProducts(response.data || []);
      setHasProducts(response.data.length > 0);

      // Auto-select if only one product
      if (response.data.length === 1) {
        setSelectedProductId(response.data[0].id);
      }
    } catch (err) {
      console.error('Error fetching products:', err);
      setHasProducts(false);
    } finally {
      setLoadingProducts(false);
    }
  };

  /**
   * Handle "Structure with AI" button click
   * Calls Claude API to structure the freeform text
   */
  const handleStructure = async () => {
    // Validation
    if (!freeformText.trim()) {
      setError('Please enter your idea first');
      return;
    }

    setIsStructuring(true);
    setError('');

    try {
      // Call API to structure text using Claude
      const result = await structureText(freeformText);

      // Update structured data with AI response
      setStructuredData({
        title: result.title || '',
        what_description: result.what_description || '',
        why_description: result.why_description || '',
        use_case_description: result.use_case_description || '',
      });

      // Move to step 2
      setStep(2);
    } catch (err) {
      setError(err.message || 'Failed to structure idea. Please try again.');
      console.error('Structure error:', err);
    } finally {
      setIsStructuring(false);
    }
  };

  /**
   * Handle structured field changes
   */
  const handleFieldChange = (field, value) => {
    setStructuredData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  /**
   * Handle "Submit Idea" button click
   * Creates the idea and submission records
   */
  const handleSubmit = async () => {
    // Validation
    if (!selectedProductId) {
      setError('Please select a product');
      return;
    }
    if (!structuredData.title.trim()) {
      setError('Title is required');
      return;
    }
    if (!structuredData.what_description.trim()) {
      setError('What description is required');
      return;
    }
    if (!structuredData.why_description.trim()) {
      setError('Why description is required');
      return;
    }
    if (!structuredData.use_case_description.trim()) {
      setError('Use case description is required');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      // Submit the idea
      await submitIdea({
        original_freeform_text: freeformText,
        title: structuredData.title,
        what_description: structuredData.what_description,
        why_description: structuredData.why_description,
        use_case_description: structuredData.use_case_description,
        product_id: selectedProductId,
      });

      // Success - redirect to ideas page
      navigate('/ideas');
    } catch (err) {
      setError(err.message || 'Failed to submit idea. Please try again.');
      console.error('Submit error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle "Start Over" button
   */
  const handleStartOver = () => {
    setStep(1);
    setFreeformText('');
    setStructuredData({
      title: '',
      what_description: '',
      why_description: '',
      use_case_description: '',
    });
    setError('');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <Navigation />

      {/* Main Content */}
      <main className="main-content max-w-4xl mx-auto py-8">
        {/* Page Header */}
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-900">Submit New Idea</h2>
          <p className="mt-2 text-gray-600">
            Describe your idea and let AI help structure it
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {/* Empty State - No Products */}
        {!loadingProducts && !hasProducts && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center py-8">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                />
              </svg>
              <h3 className="mt-4 text-lg font-medium text-gray-900">
                No products available
              </h3>
              <p className="mt-2 text-gray-600">
                {user?.role === 'voter'
                  ? "A product needs to be created before submitting ideas"
                  : "Create a product first to start submitting ideas"
                }
              </p>
              {(user?.role === 'product_owner' || user?.role === 'admin') && (
                <Link
                  to="/product-intelligence"
                  className="mt-6 inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg"
                >
                  Go to Products
                </Link>
              )}
            </div>
          </div>
        )}

        {/* Product Selection */}
        {!loadingProducts && hasProducts && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Product *
            </label>
            <select
              value={selectedProductId || ''}
              onChange={(e) => setSelectedProductId(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              required
            >
              <option value="">-- Choose a product --</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.product_name}
                </option>
              ))}
            </select>
            <p className="mt-2 text-sm text-gray-500">
              All ideas must be associated with a product
            </p>
          </div>
        )}

        {/* Step 1: Freeform Input */}
        {!loadingProducts && hasProducts && selectedProductId && step === 1 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Step 1: Describe Your Idea
            </h3>
            <p className="text-gray-600 mb-4">
              Write freely about your idea. Our AI will help structure it into
              a clear format.
            </p>

            {/* Freeform Textarea */}
            <div className="mb-4">
              <label
                htmlFor="freeform"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Your Idea
              </label>
              <textarea
                id="freeform"
                rows={10}
                value={freeformText}
                onChange={(e) => setFreeformText(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Example: We need a way for users to export their data to CSV. This would be valuable because users want to analyze their data in Excel or other tools. They could click an 'Export' button and download their data..."
                disabled={isStructuring}
              />
              <p className="mt-2 text-sm text-gray-500">
                {freeformText.length} characters
              </p>
            </div>

            {/* Structure Button */}
            <div className="flex justify-end">
              <button
                onClick={handleStructure}
                disabled={isStructuring || !freeformText.trim()}
                className={`px-6 py-3 rounded-lg font-medium ${
                  isStructuring || !freeformText.trim()
                    ? 'bg-blue-400 cursor-not-allowed text-white'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {isStructuring ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-5 w-5"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Structuring with AI...
                  </span>
                ) : (
                  'Structure with AI'
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Structured Editing */}
        {!loadingProducts && hasProducts && selectedProductId && step === 2 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Step 2: Review and Edit
            </h3>
            <p className="text-gray-600 mb-6">
              AI has structured your idea. You can edit any field before
              submitting.
            </p>

            <div className="space-y-6">
              {/* Title Field */}
              <div>
                <label
                  htmlFor="title"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Title *
                </label>
                <input
                  id="title"
                  type="text"
                  value={structuredData.title}
                  onChange={(e) => handleFieldChange('title', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Brief title for your idea"
                />
              </div>

              {/* What Description */}
              <div>
                <label
                  htmlFor="what"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  What is the feature? *
                </label>
                <textarea
                  id="what"
                  rows={4}
                  value={structuredData.what_description}
                  onChange={(e) =>
                    handleFieldChange('what_description', e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Describe what the feature is..."
                />
              </div>

              {/* Why Description */}
              <div>
                <label
                  htmlFor="why"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Why is it valuable? *
                </label>
                <textarea
                  id="why"
                  rows={4}
                  value={structuredData.why_description}
                  onChange={(e) =>
                    handleFieldChange('why_description', e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Explain why this is valuable..."
                />
              </div>

              {/* Use Case Description */}
              <div>
                <label
                  htmlFor="use_case"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  How would it be used? *
                </label>
                <textarea
                  id="use_case"
                  rows={4}
                  value={structuredData.use_case_description}
                  onChange={(e) =>
                    handleFieldChange('use_case_description', e.target.value)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Describe how it would be used..."
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-8 flex justify-between">
              <button
                onClick={handleStartOver}
                disabled={isSubmitting}
                className="px-6 py-3 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50"
              >
                Start Over
              </button>

              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className={`px-6 py-3 rounded-lg font-medium ${
                  isSubmitting
                    ? 'bg-blue-400 cursor-not-allowed text-white'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-5 w-5"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Submitting...
                  </span>
                ) : (
                  'Submit Idea'
                )}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default SubmitIdeaPage;
