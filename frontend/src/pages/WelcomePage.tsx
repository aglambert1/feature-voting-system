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
        <div className="flex justify-end mb-4">
          <button
            onClick={() => handleAcknowledge(isPO ? '/product-intelligence' : '/ideas')}
            disabled={acknowledging}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:text-gray-300 underline"
          >
            Skip and go to my dashboard
          </button>
        </div>
        <header className="mb-10">
          <p className="text-sm text-blue-600 font-medium mb-2">Welcome to Feature-IQ</p>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Hi{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}.
          </h1>
          <p className="text-lg text-gray-700">
            Feature-IQ builds a living factbase for your product — signals from competitors, customer
            ideas, your internal data, and any evidence you upload (interview transcripts, extra
            competitive research, anything). It organizes everything around your customers'
            Jobs-to-be-Done, then synthesizes it into prioritized opportunities that flow into a
            voting board.
          </p>
        </header>

        <IntroVideo loomVideoId="f3263c31da0947c3baf719798fc011b3" />

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">What you can do today</h2>
          <div className="space-y-3 text-gray-700">
            <p>
              <span className="font-medium text-gray-900">Read access to a demo product</span> —{' '}
              browse a fully populated example. You can vote on its ideas and connect an AI assistant
              to ask questions about it. You cannot run audits or change settings.
            </p>
            {isPO && (
              <p>
                <span className="font-medium text-gray-900">Full ownership of products you create</span>{' '}
                — create your own product, add your competitors, run analysis pipelines, invite voters. 
                As product creator, you control who can see your product and its ideas, and who can vote on them. 
                You can also upload your own evidence (interview transcripts, competitive research, etc.) to enrich the factbase.
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
              body="Open the demo product. Look at the Job Map (the analytical spine), one of the Competitor Reports, and the latest Opportunity Synthesis. Notice opportunities are tagged to a customer need and traceable to the competitive analysis or evidence sources."
              cta="Go to Product Dashboard"
              ctaHref="/product-intelligence"
              onClick={() => navigate('/product-intelligence')}
            />
            <ActionCard
              step="2"
              title="Connect an AI assistant over MCP"
              time="5 min"
              body={
                'Feature-IQ exposes its factbase through MCP, so you can query and drive it in plain ' +
                'English from the MCP-capable tool of your choice. Easiest path, no install: in ' +
                'claude.ai go to Settings → Connectors → Add custom connector, paste the MCP server ' +
                'URL below, and leave the OAuth Client ID and Secret blank — sign in with your ' +
                'Feature-IQ credentials when the browser prompts you. Claude Desktop and other MCP ' +
                'tools work too: point them at the same URL. Prefer headless or CLI use? Generate an ' +
                'API key from your profile instead. Once connected, ask things like "What are the top ' +
                '3 opportunities in my latest synthesis report, and which jobs do they serve?"'
              }
              copyValue="https://feature-iq-mcp.onrender.com/mcp"
              copyLabel="Copy MCP server URL"
              cta="Need a key instead?"
              ctaHref="/profile"
              onClick={() => navigate('/profile')}
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
                body="On your product, add one competitor by name + URL or the Market Discovery agent. Run the audit. It takes ~3 minutes (Stage 1 web research + Stage 2 structured assessment). When it lands, open the report — your first competitor's positions across your job map."
              />
            )}
          </div>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">What's worth knowing</h2>
          <ul className="space-y-2 text-gray-700 list-disc list-inside">
            <li>
              <span className="font-medium">The job map is load-bearing.</span> Skip it and every
              downstream artifact is weaker. 
            </li>
            <li>
              <span className="font-medium">The system is async.</span> Audits, synthesis, and triage
              run on a background queue. Watch progress badges — clicking doesn't mean done.
            </li>
            <li>
              <span className="font-medium">Triage runs on every idea.</span> Each idea gets classified,
              linked to the closest job, and tagged with competitive context. 
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
              <span className="font-medium">Anything at all?</span>{' '}
              <a href="mailto:featureiq@gmail.com" className="text-blue-600 hover:underline">
                Email me
              </a>{' '}
              (featureiq@gmail.com) — happy to walk you through setup, the JTBD model, or what the
              system can do, and to share the reference docs.
            </li>
            <li>
              <span className="font-medium">Something broken or surprising?</span> Email me.
            </li>
          </ul>
          <p className="text-gray-700 mt-3">
            To return to this Welcome page, open the profile menu in the top-right.
          </p>
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
                Product Dashboard
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
            The project framing and feedback channels live on the landing page — click the
            Feature-IQ wordmark in the header anytime.
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
  copyValue?: string;
  copyLabel?: string;
}

const ActionCard = ({
  step,
  title,
  time,
  body,
  cta,
  ctaHref,
  onClick,
  copyValue,
  copyLabel,
}: ActionCardProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(copyValue ?? '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can fail (permissions / insecure context) — the URL is also
      // printed in the body text, so the user still has it.
    }
  };

  const hasActions = copyValue || (cta && ctaHref);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
      <div className="flex items-baseline gap-3 mb-2">
        <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2 py-0.5 rounded">
          Step {step}
        </span>
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <span className="text-xs text-gray-500 ml-auto">{time}</span>
      </div>
      <p className="text-gray-700 text-sm mb-3">{body}</p>
      {hasActions && (
        <div className="flex gap-2 flex-wrap items-center">
          {copyValue && (
            <button
              onClick={handleCopy}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded transition-colors"
            >
              {copied ? 'Copied!' : copyLabel ?? 'Copy'}
            </button>
          )}
          {cta && ctaHref && (
            <button
              onClick={onClick}
              className={
                copyValue
                  ? 'text-blue-600 hover:underline text-sm font-medium px-2 py-2'
                  : 'bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded transition-colors'
              }
            >
              {cta}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

interface IntroVideoProps {
  loomVideoId: string | null;
}

const IntroVideo = ({ loomVideoId }: IntroVideoProps) => (
  <section className="mb-10">
    <h2 className="text-xl font-semibold text-gray-900 mb-4">See it in 90 seconds</h2>
    {loomVideoId ? (
      <div className="relative w-full overflow-hidden rounded-lg border border-gray-200 shadow-sm" style={{ paddingBottom: '56.25%' }}>
        <iframe
          src={`https://www.loom.com/embed/${loomVideoId}?hide_owner=true&hide_share=true&hide_title=true`}
          allowFullScreen
          className="absolute inset-0 w-full h-full"
          title="Feature-IQ intro video"
        />
      </div>
    ) : (
      <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-100 text-gray-500 text-sm" style={{ aspectRatio: '16/9' }}>
        Intro video coming soon
      </div>
    )}
    <p className="mt-3 text-sm text-gray-500">An introduction to Feature-IQ.</p>
  </section>
);

export default WelcomePage;
