import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types';

const LINKEDIN_URL = 'https://www.linkedin.com/in/aglambert/';
const GITHUB_URL = 'https://github.com/aglambert1/feature-voting-system';
const GITHUB_DISCUSSIONS_URL = 'https://github.com/aglambert1/feature-voting-system/discussions';
const GITHUB_ISSUES_URL = 'https://github.com/aglambert1/feature-voting-system/issues';
const LICENSE_URL = 'https://github.com/aglambert1/feature-voting-system/blob/main/LICENSE';
const FEEDBACK_EMAIL = 'ag@feature-iq.app';

const SCREENSHOT_JOB_MAP = '/screenshots/jobmap.png';
const SCREENSHOT_SYNTHESIS = '/screenshots/synthesis.png';
const LOOM_EMBED_URL = '';

const LandingPage = () => {
  const { user } = useAuth();
  const isPO = user?.role === UserRole.PRODUCT_OWNER || user?.role === UserRole.ADMIN;
  const dashboardPath = isPO ? '/product-intelligence' : '/ideas';

  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-gray-200 bg-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <span className="text-lg font-semibold text-gray-900">Feature-IQ</span>
          {user ? (
            <Link
              to={dashboardPath}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              Continue to dashboard →
            </Link>
          ) : (
            <Link
              to="/login"
              className="text-sm text-gray-700 hover:text-gray-900 font-medium"
            >
              Sign in
            </Link>
          )}
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <section className="mb-16">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 leading-tight mb-6">
            Exploring a new product management workflow.
          </h1>
          <p className="text-lg text-gray-700 leading-relaxed mb-5">
            Most AI-for-PM tools speed up steps in the existing workflow — conduct competitive
            analysis, write a PRD, etc. This can drive incremental productivity, but can't deliver
            the kind of transformative change that's needed to truly modernize product management.
          </p>
          <p className="text-lg text-gray-700 leading-relaxed mb-5">
            Feature-IQ is a focused component of a new approach based on agents analyzing market and
            competitive data, triaging customer feedback, recommending features to build, presenting
            PRDs for implementation, providing documentation to support launch, and monitoring
            product success. The PM stays in the loop as the strategic judge — what gets built, why,
            and what to ignore. But every step of the workflow around that judgment will be
            transformed by AI agents.
          </p>
          <p className="text-lg text-gray-700 leading-relaxed mb-8">
            Feature-IQ is one step of that workflow: a continuous evidence base for market and customer
            signal, synthesized through a Jobs-to-be-Done spine, with every claim traceable back to
            its source. It is intended to deliver value today, and it's also an experiment in how AI is
            changing the practice of product management. The opportunity in transforming product processes with AI is to strip
            product management down to its core — understanding and empathizing with customers'
            needs — and remove the administrative and project management overhead. When you use it,
            I want to hear what you think.
          </p>
          {!user && (
            <a
              href={`mailto:${FEEDBACK_EMAIL}?subject=Feature-IQ access request`}
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-5 py-2.5 rounded transition-colors"
            >
              Request access
            </a>
          )}
        </section>

        <section className="mb-16">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6">What it does today</h2>
          <ul className="space-y-4 text-gray-700">
            <li className="border-l-2 border-blue-500 pl-4">
              <span className="font-medium text-gray-900">Analyze uploaded product information to create a Jobs-to-be-Done
                map.</span>{' '}
              Accelerate product manager understanding and documentation of customer needs. Extract core features, target users,
              and key value propositions from product data.
            </li>
            <li className="border-l-2 border-blue-500 pl-4">
              <span className="font-medium text-gray-900">Track and audit key competitors on demand or on a schedule.</span>{' '}
              Get back a structured comparison across your customers' Jobs-to-be-Done — not a
              bullet list of features.
            </li>
            <li className="border-l-2 border-blue-500 pl-4">
              <span className="font-medium text-gray-900">Triage customer feedback.</span>{' '}
              Automate triage of customer ideas and feature requests, comparing to existing features and past requests, 
              eliminating duplicates and associating ideas with a specific job.
            </li>
            <li className="border-l-2 border-blue-500 pl-4">
              <span className="font-medium text-gray-900">Synthesize across signals.</span>{' '}
              Customer ideas, competitor reports, internal feedback themes, and uploaded evidence combine into
              prioritized opportunities, each tagged to a specific job. Optionally export opportunities to the idea voting
              system for further customer or internal feedback.
            </li>
            <li className="border-l-2 border-blue-500 pl-4">
              <span className="font-medium text-gray-900">Ask in plain English.</span>{' '}
              Connect Claude Desktop or other tools via MCP. Ask "what are the top opportunities and which jobs
              do they serve?" — get an answer grounded in your own data.
            </li>
          </ul>
        </section>

        <section className="mb-16">
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">
            The job map is the spine.
          </h2>
          <p className="text-gray-700 mb-6">
            You define what customers are trying to do. Audits, synthesis, and idea triage all
            reason against the same structure. Every claim traces back to its source.
          </p>
          <ScreenshotSlot src={SCREENSHOT_JOB_MAP} alt="Job map editor" caption="The PO-owned job map. Functional, emotional, and social jobs." />
        </section>

        <section className="mb-16">
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">
            Synthesis isn't a list — it's a structured view per job.
          </h2>
          <p className="text-gray-700 mb-6">
            Opportunities are scored, tier-classified, and tagged to the job they serve.
            High-priority ones flow into the voting board as triaged ideas automatically.
          </p>
          <ScreenshotSlot src={SCREENSHOT_SYNTHESIS} alt="Synthesis output" caption="Unified synthesis: opportunities grouped by job, scored, and linked to ideas." />
        </section>

        {LOOM_EMBED_URL && (
          <section className="mb-16">
            <h2 className="text-2xl font-semibold text-gray-900 mb-6">See it in 90 seconds</h2>
            <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
              <iframe
                src={LOOM_EMBED_URL}
                className="w-full h-full"
                frameBorder={0}
                allow="fullscreen"
                title="Feature-IQ demo"
              />
            </div>
          </section>
        )}

        <section className="mb-16 bg-gray-50 border border-gray-200 rounded-lg p-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Try it</h2>
          <div className="space-y-4">
            <div>
              <p className="text-gray-900 font-medium mb-1">Already have credentials?</p>
              <Link to="/login" className="text-blue-600 hover:underline">
                Sign in →
              </Link>
            </div>
            <div>
              <p className="text-gray-900 font-medium mb-1">Want to try Feature-IQ?</p>
              <p className="text-gray-700 text-sm">
                Email me at {' '}
                <a href={`mailto:${FEEDBACK_EMAIL}?subject=Feature-IQ access request`} className="text-blue-600 hover:underline">
                  {FEEDBACK_EMAIL}
                </a>
                {' '}with a sentence on what you'd want to use it for. I'll set up an account and send credentials.
              </p>
            </div>
          </div>
        </section>

        <section className="mb-16">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            Part of a broader transformation
          </h2>
          <p className="text-gray-700 mb-6">
            Feature-IQ is one bet on how AI is reshaping the practice of product management.
            The bigger conversation — what changes, what doesn't, what's still missing — is
            happening across the industry. Your feedback shapes both this tool and that
            conversation. Two ways to engage:
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <FeedbackCard
              title="Email a quick thought"
              body="Best for general reactions, half-formed ideas, or 'what do you think about X' questions."
              cta="Email AG"
              href={`mailto:${FEEDBACK_EMAIL}?subject=Feature-IQ feedback`}
            />
            <FeedbackCard
              title="GitHub Discussions or Issues"
              body="Best for technical discussion, bug reports, and conversations a broader community might want to see."
              cta="Open a discussion"
              href={GITHUB_DISCUSSIONS_URL}
              secondaryCta="Or file an issue"
              secondaryHref={GITHUB_ISSUES_URL}
            />
          </div>
        </section>

        <section className="mb-16">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">What it isn't</h2>
          <ul className="space-y-2 text-gray-700">
            <li>— A roadmapping tool. It informs roadmap decisions; it doesn't replace Jira / Linear / Aha / Productboard.</li>
            <li>— A replacement for a customer-facing portal. Voters are internal stakeholders, not the public.</li>
            <li>— A live CRM integration. Internal feedback comes in via import, not real-time sync.</li>
          </ul>
          <p className="text-gray-700 mt-4">
            If Feature-IQ proves useful, future integrations may expand its capabilities.
          </p>
        </section>
      </main>

      <footer className="border-t border-gray-200 bg-gray-50">
        <div className="max-w-3xl mx-auto px-6 py-8 text-sm text-gray-600 flex flex-col md:flex-row md:justify-between gap-4">
          <p>
            Built by{' '}
            <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
              A.G. Lambert
            </a>
            , with assistance from Claude Code.
          </p>
          <p className="flex gap-4">
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
              Open source on GitHub
            </a>
            <a href={LICENSE_URL} target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:underline">
              MIT licensed
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
};

interface ScreenshotSlotProps {
  src: string;
  alt: string;
  caption: string;
}

const ScreenshotSlot = ({ src, alt, caption }: ScreenshotSlotProps) => (
  <figure>
    <div className="bg-gray-100 border border-gray-200 rounded-lg aspect-video flex items-center justify-center overflow-hidden">
      <img
        src={src}
        alt={alt}
        className="w-full h-full object-cover"
        onError={(e) => {
          const target = e.currentTarget;
          target.style.display = 'none';
          if (target.parentElement) {
            target.parentElement.innerHTML =
              '<div class="text-gray-400 text-sm italic p-8 text-center">Screenshot placeholder — drop image at ' +
              src +
              '</div>';
          }
        }}
      />
    </div>
    <figcaption className="text-sm text-gray-500 mt-2 italic">{caption}</figcaption>
  </figure>
);

interface FeedbackCardProps {
  title: string;
  body: string;
  cta: string;
  href: string;
  primary?: boolean;
  secondaryCta?: string;
  secondaryHref?: string;
}

const FeedbackCard = ({ title, body, cta, href, primary, secondaryCta, secondaryHref }: FeedbackCardProps) => (
  <div
    className={`border rounded-lg p-5 ${
      primary ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
    }`}
  >
    <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
    <p className="text-sm text-gray-700 mb-4">{body}</p>
    <a
      href={href}
      target={href.startsWith('http') ? '_blank' : undefined}
      rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
      className={`text-sm font-medium hover:underline ${
        primary ? 'text-blue-700' : 'text-blue-600'
      }`}
    >
      {cta} →
    </a>
    {secondaryCta && secondaryHref && (
      <a
        href={secondaryHref}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-gray-600 hover:underline block mt-1"
      >
        {secondaryCta} →
      </a>
    )}
  </div>
);

export default LandingPage;
