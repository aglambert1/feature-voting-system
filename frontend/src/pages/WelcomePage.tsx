import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types';
import { markWelcomed } from '../services/api';
import Navigation from '../components/Navigation';

const WelcomePage = () => {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [acknowledging, setAcknowledging] = useState(false);

  const isPO = user?.role === UserRole.PRODUCT_OWNER || user?.role === UserRole.ADMIN;

  const handleAcknowledge = async (destination: string) => {
    setAcknowledging(true);
    try {
      const updatedUser = await markWelcomed();
      setUser(updatedUser);
    } catch {
      // If the flag flip fails, still let the user proceed. The next login will
      // re-show the welcome page, which is acceptable.
    } finally {
      navigate(destination);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <main className="main-content max-w-4xl mx-auto py-10 px-4">
        <header className="mb-10">
          <p className="text-sm text-blue-600 font-medium mb-2">Welcome to Feature-IQ</p>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Hi{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}.
          </h1>
          <p className="text-lg text-gray-700">
            Feature-IQ runs automated competitive analysis against your customers' Jobs-to-be-Done,
            then synthesizes the results with your customer feedback into prioritized opportunities
            that flow into a voting board.
          </p>
        </header>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">What you can do today</h2>
          <div className="space-y-3 text-gray-700">
            <p>
              <span className="font-medium text-gray-900">Read access to a demo product</span> —{' '}
              browse a fully populated example (Concur Invoice, AP automation). You can vote on its
              ideas and ask Claude Desktop questions about it. You cannot run audits or change settings.
            </p>
            {isPO && (
              <p>
                <span className="font-medium text-gray-900">Full ownership of products you create</span>{' '}
                — create your own product, add your competitors, run analysis pipelines, invite voters.
              </p>
            )}
          </div>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Try this in the next 15 minutes</h2>
          <div className="grid gap-4">
            <ActionCard
              step="1"
              title="Browse the demo product"
              time="3 min"
              body="Open Concur Invoice. Look at the Job Map (the analytical spine), one of the Competitor Reports (notice positions are grouped by job, not separate gaps/advantages), and the Synthesis Hub."
              cta="Go to Competitive Intelligence"
              ctaHref="/product-intelligence"
              onClick={() => navigate('/product-intelligence')}
            />
            <ActionCard
              step="2"
              title="Connect Claude Desktop"
              time="5 min"
              body='Generate an API key from your profile, paste it into Claude Desktop config. Then ask things like "What are the top 3 opportunities in my latest synthesis report, and which jobs do they serve?" This is the showcase use case.'
              cta="Open my profile to generate a key"
              ctaHref="/profile"
              onClick={() => navigate('/profile')}
              secondaryCta="Setup guide"
              secondaryHref="https://github.com/aglambert1/feature-voting-system/blob/main/docs/getting-started/claude-desktop.md"
              external
            />
            {isPO && (
              <ActionCard
                step="3"
                title="Create your own product"
                time="5 min"
                body="Fill in name, a real description (this drives job-map quality), and category. Run Product Analysis (~30s) and Generate Job Map (~30s). Edit the job map until it looks right — bad job statements produce bad audits."
                cta="Create a product"
                ctaHref="/product-intelligence/products/create"
                onClick={() => navigate('/product-intelligence/products/create')}
              />
            )}
            {isPO && (
              <ActionCard
                step="4"
                title="Add a competitor and run an audit"
                time="4 min wall time"
                body="On your product, add one competitor by name + URL. Run the audit. It takes ~3 minutes (Stage 1 web research + Stage 2 structured assessment). When it lands, open the report — your first competitor's positions across your job map."
              />
            )}
          </div>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">What's worth knowing</h2>
          <ul className="space-y-2 text-gray-700 list-disc list-inside">
            <li>
              <span className="font-medium">The job map is load-bearing.</span> Skip it and every
              downstream artifact is weaker. Spend the time.
            </li>
            <li>
              <span className="font-medium">The system is async.</span> Audits, synthesis, and triage
              run on a background queue. Watch progress badges — clicking doesn't mean done.
            </li>
            <li>
              <span className="font-medium">Triage runs on every idea.</span> Each idea gets classified,
              linked to the closest job, and tagged with competitive context. Not decoration — that's how
              the loop closes.
            </li>
            <li>
              <span className="font-medium">Costs are real.</span> Each audit ~$0.50–$1.00. Synthesis
              ~$0.30. Don't loop them unless you mean to.
            </li>
          </ul>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">When you have questions</h2>
          <ul className="space-y-2 text-gray-700">
            <li>
              <span className="font-medium">How does X work?</span>{' '}
              <ExternalLink href="https://github.com/aglambert1/feature-voting-system/blob/main/docs/getting-started/architecture.md">
                Architecture guide
              </ExternalLink>{' '}
              — JTBD model and major components
            </li>
            <li>
              <span className="font-medium">What features exist?</span>{' '}
              <ExternalLink href="https://github.com/aglambert1/feature-voting-system/blob/main/docs/getting-started/tour.md">
                Tour
              </ExternalLink>{' '}
              — feature inventory by role
            </li>
            <li>
              <span className="font-medium">Connect Claude Desktop?</span>{' '}
              <ExternalLink href="https://github.com/aglambert1/feature-voting-system/blob/main/docs/getting-started/claude-desktop.md">
                Setup guide
              </ExternalLink>
            </li>
            <li>
              <span className="font-medium">Something broken or surprising?</span> Contact the operator
              who gave you access.
            </li>
          </ul>
        </section>

        <footer className="border-t border-gray-200 pt-8 mt-10">
          <p className="text-sm text-gray-600 mb-4">
            Got it. Take me to:
          </p>
          <div className="flex flex-wrap gap-3">
            {isPO && (
              <button
                onClick={() => handleAcknowledge('/product-intelligence')}
                disabled={acknowledging}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
              >
                Competitive Intelligence
              </button>
            )}
            <button
              onClick={() => handleAcknowledge('/ideas')}
              disabled={acknowledging}
              className={`text-sm font-medium px-4 py-2 rounded transition-colors ${
                isPO
                  ? 'bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 disabled:bg-gray-100'
                  : 'bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white'
              }`}
            >
              Ideas board
            </button>
            <button
              onClick={() => handleAcknowledge('/profile')}
              disabled={acknowledging}
              className="bg-white border border-gray-300 hover:bg-gray-50 disabled:bg-gray-100 text-gray-700 text-sm font-medium px-4 py-2 rounded transition-colors"
            >
              Profile
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            You can return to this page anytime by clicking the Feature-IQ wordmark in the header.
          </p>
        </footer>
      </main>
    </div>
  );
};

interface ActionCardProps {
  step: string;
  title: string;
  time: string;
  body: string;
  cta?: string;
  ctaHref?: string;
  onClick?: () => void;
  secondaryCta?: string;
  secondaryHref?: string;
  external?: boolean;
}

const ActionCard = ({
  step,
  title,
  time,
  body,
  cta,
  ctaHref,
  onClick,
  secondaryCta,
  secondaryHref,
  external,
}: ActionCardProps) => (
  <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
    <div className="flex items-baseline gap-3 mb-2">
      <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2 py-0.5 rounded">
        Step {step}
      </span>
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      <span className="text-xs text-gray-500 ml-auto">{time}</span>
    </div>
    <p className="text-gray-700 text-sm mb-3">{body}</p>
    {(cta || secondaryCta) && (
      <div className="flex gap-2 flex-wrap">
        {cta && ctaHref && (
          <button
            onClick={onClick}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
          >
            {cta}
          </button>
        )}
        {secondaryCta && secondaryHref && (
          <a
            href={secondaryHref}
            target={external ? '_blank' : undefined}
            rel={external ? 'noopener noreferrer' : undefined}
            className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-medium px-4 py-2 rounded transition-colors"
          >
            {secondaryCta}
          </a>
        )}
      </div>
    )}
  </div>
);

const ExternalLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <a
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    className="text-blue-600 hover:underline"
  >
    {children}
  </a>
);

export default WelcomePage;
