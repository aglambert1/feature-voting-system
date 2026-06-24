import { useState, useEffect, useCallback } from 'react';
import Navigation from '../components/Navigation';
import { getCostSummary, getCostToday, getUserCosts, getProductCosts, getDailyCostSeries } from '../services/api';

interface CostSummary {
  period_days: number;
  total_requests: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  by_operation: Record<string, { count: number; cost: number; input_tokens: number; output_tokens: number }>;
  by_model: Record<string, { count: number; cost: number }>;
  top_users: Array<{ user_id: number; username: string; email: string; count: number; cost: number }>;
  top_products: Array<{ product_id: number; product_name: string; count: number; cost: number }>;
}

interface TodayCost {
  total_cost_usd: number;
  limit_exceeded: boolean;
  daily_limit_usd: number;
}

interface DailyCostEntry {
  date: string;
  total_cost_usd: number;
  request_count: number;
}

interface DrilldownData {
  label: string;
  total_cost_usd: number;
  total_requests: number;
  by_operation: Record<string, { count: number; cost: number }>;
}

export default function CostReportingPage() {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [todayCost, setTodayCost] = useState<TodayCost | null>(null);
  const [dailySeries, setDailySeries] = useState<DailyCostEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Drilldown modal state
  const [drilldown, setDrilldown] = useState<DrilldownData | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryData, todayData, seriesData] = await Promise.all([
        getCostSummary(days),
        getCostToday(),
        getDailyCostSeries(days),
      ]);
      setSummary(summaryData);
      setTodayCost(todayData);
      setDailySeries(seriesData);
    } catch {
      setError('Failed to load cost data');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleUserDrilldown = async (userId: number, username: string) => {
    setDrilldownLoading(true);
    try {
      const data = await getUserCosts(userId, days);
      setDrilldown({
        label: username,
        total_cost_usd: data.total_cost_usd,
        total_requests: data.total_requests,
        by_operation: data.by_operation,
      });
    } catch {
      setError('Failed to load user costs');
    } finally {
      setDrilldownLoading(false);
    }
  };

  const handleProductDrilldown = async (productId: number, productName: string) => {
    setDrilldownLoading(true);
    try {
      const data = await getProductCosts(productId, days);
      setDrilldown({
        label: productName,
        total_cost_usd: data.total_cost_usd,
        total_requests: data.total_requests,
        by_operation: data.by_operation,
      });
    } catch {
      setError('Failed to load product costs');
    } finally {
      setDrilldownLoading(false);
    }
  };

  const formatUsd = (val: number) => `$${val.toFixed(4)}`;
  const formatUsd2 = (val: number) => `$${val.toFixed(2)}`;

  const maxDailyCost = dailySeries.length > 0
    ? Math.max(...dailySeries.map(d => d.total_cost_usd))
    : 0;

  const formatOperationName = (op: string) =>
    op.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">LLM Cost Report</h1>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : summary && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-medium text-gray-500">Total Cost</h3>
                <p className="mt-2 text-3xl font-bold text-gray-900">{formatUsd2(summary.total_cost_usd)}</p>
                <p className="mt-1 text-xs text-gray-500">{days}-day period</p>
              </div>
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-medium text-gray-500">Total Requests</h3>
                <p className="mt-2 text-3xl font-bold text-blue-600">{summary.total_requests.toLocaleString()}</p>
                <p className="mt-1 text-xs text-gray-500">{summary.total_input_tokens.toLocaleString()} in / {summary.total_output_tokens.toLocaleString()} out tokens</p>
              </div>
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-medium text-gray-500">Today's Cost</h3>
                <p className={`mt-2 text-3xl font-bold ${todayCost?.limit_exceeded ? 'text-red-600' : 'text-green-600'}`}>
                  {todayCost ? formatUsd2(todayCost.total_cost_usd) : '—'}
                </p>
                {todayCost?.limit_exceeded && (
                  <p className="mt-1 text-xs text-red-600 font-medium">Limit exceeded (${todayCost.daily_limit_usd})</p>
                )}
                {todayCost && !todayCost.limit_exceeded && (
                  <p className="mt-1 text-xs text-gray-500">Limit: ${todayCost.daily_limit_usd}</p>
                )}
              </div>
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-sm font-medium text-gray-500">Avg Cost / Request</h3>
                <p className="mt-2 text-3xl font-bold text-gray-900">
                  {summary.total_requests > 0 ? formatUsd(summary.total_cost_usd / summary.total_requests) : '—'}
                </p>
              </div>
            </div>

            {/* Daily Spend Trend */}
            {dailySeries.length > 0 && (
              <div className="bg-white shadow rounded-lg p-6 mb-8">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Daily Spend</h2>
                <div className="space-y-1">
                  {dailySeries.map(d => (
                    <div key={d.date} className="flex items-center gap-3 text-sm">
                      <span className="w-20 text-gray-500 text-xs shrink-0">{d.date.slice(5)}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                        <div
                          className="bg-blue-500 h-5 rounded-full"
                          style={{ width: maxDailyCost > 0 ? `${(d.total_cost_usd / maxDailyCost) * 100}%` : '0%' }}
                        />
                      </div>
                      <span className="w-20 text-right text-gray-700 text-xs shrink-0">
                        {formatUsd(d.total_cost_usd)}
                      </span>
                      <span className="w-12 text-right text-gray-400 text-xs shrink-0">
                        {d.request_count}req
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tables Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
              {/* Cost by Operation */}
              <div className="bg-white shadow rounded-lg overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Cost by Operation</h2>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-6 py-3 font-medium text-gray-500">Operation</th>
                      <th className="text-right px-6 py-3 font-medium text-gray-500">Requests</th>
                      <th className="text-right px-6 py-3 font-medium text-gray-500">Cost</th>
                      <th className="text-right px-6 py-3 font-medium text-gray-500">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {Object.entries(summary.by_operation)
                      .sort(([,a], [,b]) => b.cost - a.cost)
                      .map(([op, data]) => (
                        <tr key={op} className="hover:bg-gray-50">
                          <td className="px-6 py-3 text-gray-900">{formatOperationName(op)}</td>
                          <td className="px-6 py-3 text-right text-gray-600">{data.count}</td>
                          <td className="px-6 py-3 text-right text-gray-900">{formatUsd(data.cost)}</td>
                          <td className="px-6 py-3 text-right text-gray-500">
                            {summary.total_cost_usd > 0 ? `${((data.cost / summary.total_cost_usd) * 100).toFixed(1)}%` : '—'}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Cost by Model */}
              <div className="bg-white shadow rounded-lg overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Cost by Model</h2>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-6 py-3 font-medium text-gray-500">Model</th>
                      <th className="text-right px-6 py-3 font-medium text-gray-500">Requests</th>
                      <th className="text-right px-6 py-3 font-medium text-gray-500">Cost</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {Object.entries(summary.by_model)
                      .sort(([,a], [,b]) => b.cost - a.cost)
                      .map(([model, data]) => (
                        <tr key={model} className="hover:bg-gray-50">
                          <td className="px-6 py-3 text-gray-900 font-mono text-xs">{model}</td>
                          <td className="px-6 py-3 text-right text-gray-600">{data.count}</td>
                          <td className="px-6 py-3 text-right text-gray-900">{formatUsd(data.cost)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Top Users and Products */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Top Users */}
              {summary.top_users.length > 0 && (
                <div className="bg-white shadow rounded-lg overflow-hidden">
                  <div className="px-6 py-4 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">Top Users by Cost</h2>
                  </div>
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="text-left px-6 py-3 font-medium text-gray-500">User</th>
                        <th className="text-right px-6 py-3 font-medium text-gray-500">Requests</th>
                        <th className="text-right px-6 py-3 font-medium text-gray-500">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {summary.top_users.map(u => (
                        <tr
                          key={u.user_id}
                          className="hover:bg-gray-50 cursor-pointer"
                          onClick={() => handleUserDrilldown(u.user_id, u.username)}
                        >
                          <td className="px-6 py-3">
                            <div className="text-gray-900 font-medium">{u.username}</div>
                            <div className="text-gray-400 text-xs">{u.email}</div>
                          </td>
                          <td className="px-6 py-3 text-right text-gray-600">{u.count}</td>
                          <td className="px-6 py-3 text-right text-gray-900">{formatUsd(u.cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Top Products */}
              {summary.top_products.length > 0 && (
                <div className="bg-white shadow rounded-lg overflow-hidden">
                  <div className="px-6 py-4 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">Top Products by Cost</h2>
                  </div>
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="text-left px-6 py-3 font-medium text-gray-500">Product</th>
                        <th className="text-right px-6 py-3 font-medium text-gray-500">Requests</th>
                        <th className="text-right px-6 py-3 font-medium text-gray-500">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {summary.top_products.map(p => (
                        <tr
                          key={p.product_id}
                          className="hover:bg-gray-50 cursor-pointer"
                          onClick={() => handleProductDrilldown(p.product_id, p.product_name)}
                        >
                          <td className="px-6 py-3 text-gray-900 font-medium">{p.product_name}</td>
                          <td className="px-6 py-3 text-right text-gray-600">{p.count}</td>
                          <td className="px-6 py-3 text-right text-gray-900">{formatUsd(p.cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* Drilldown Modal */}
      {(drilldown || drilldownLoading) && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Cost Breakdown — {drilldown?.label || 'Loading...'}
              </h3>
            </div>

            <div className="px-6 py-4">
              {drilldownLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : drilldown && (
                <>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Total Cost</p>
                      <p className="text-lg font-bold text-gray-900">{formatUsd(drilldown.total_cost_usd)}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Requests</p>
                      <p className="text-lg font-bold text-blue-600">{drilldown.total_requests}</p>
                    </div>
                  </div>

                  {Object.keys(drilldown.by_operation).length > 0 && (
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-500">Operation</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-500">Count</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-500">Cost</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {Object.entries(drilldown.by_operation)
                          .sort(([,a], [,b]) => b.cost - a.cost)
                          .map(([op, data]) => (
                            <tr key={op}>
                              <td className="px-3 py-2 text-gray-900">{formatOperationName(op)}</td>
                              <td className="px-3 py-2 text-right text-gray-600">{data.count}</td>
                              <td className="px-3 py-2 text-right text-gray-900">{formatUsd(data.cost)}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => { setDrilldown(null); }}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
