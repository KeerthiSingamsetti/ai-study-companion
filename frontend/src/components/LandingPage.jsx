import { motion } from 'framer-motion'
import {
  ArrowRight,
  Brain,
  ChartNoAxesCombined,
  ChevronDown,
  ChevronRight,
  Compass,
  Database,
  FileSearch,
  Layers,
  Lightbulb,
  Lock,
  Network,
  Quote,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  SquarePen,
  Upload,
} from 'lucide-react'

/* ────────────────────────────────────────────────────────────────
   Public landing page (signed-out).

   Layout language borrowed from the reference the candidate supplied
   — floating glass nav, gradient headline, numbered flow cards, dense
   capability grid — but the copy is deliberately *short*: one line per
   card, no paragraphs. And the palette stays on the app's ink/gold
   tokens, so marketing and workspace read as one product.

   Deliberately absent: the mocked "Project analytics" panel that used
   to sit here — mock data competes with the hero and promises features
   to a visitor who has no account yet.
   ──────────────────────────────────────────────────────────────── */

/** Deterministic light-streak field (no layout thrash, stable across reloads). */
const STREAK_COLOURS = [
  'rgba(245, 181, 74, 0.75)',
  'rgba(96, 165, 250, 0.6)',
  'rgba(45, 212, 191, 0.55)',
  'rgba(167, 139, 250, 0.45)',
]

const STREAKS = Array.from({ length: 28 }, (_, index) => {
  const rnd = ((index * 9301 + 49297) % 233280) / 233280
  return {
    left: `${(index * 3.62 + rnd * 2.4).toFixed(2)}%`,
    delay: `${(rnd * 10).toFixed(2)}s`,
    duration: `${(9 + rnd * 10).toFixed(2)}s`,
    height: `${(13 + rnd * 22).toFixed(1)}vh`,
    opacity: (0.3 + rnd * 0.5).toFixed(2),
    drift: `${Math.round((rnd - 0.5) * 130)}px`,
    color: STREAK_COLOURS[index % STREAK_COLOURS.length],
  }
})

const NAV_LINKS = [
  { href: '#the-loop', label: 'The loop' },
  { href: '#capabilities', label: 'Capabilities' },
]

/** The five-stage learning loop — one line each, with a node tone for the rail. */
const LOOP = [
  {
    icon: Upload,
    tone: 'accent',
    title: 'Add material',
    body: 'Upload PDFs — parsed and indexed in the background.',
  },
  {
    icon: FileSearch,
    tone: 'blue',
    title: 'Ask the Tutor',
    body: 'Grounded answers that cite your pages — or refuse to guess.',
  },
  {
    icon: Layers,
    tone: 'teal',
    title: 'Practise',
    body: 'Adaptive quizzes and written answers you explain yourself.',
  },
  {
    icon: Brain,
    tone: 'accent',
    title: 'Measure',
    body: 'Every attempt moves a recency-weighted estimate per concept.',
  },
  {
    icon: Lightbulb,
    tone: 'blue',
    title: 'Act',
    body: 'One recommended next step, chosen from your weakest evidence.',
  },
]

/** Per-stage node styling — the icon carries the meaning, not a number. */
const NODE_TONES = {
  accent: {
    ring: 'border-[var(--accent)]/35 group-hover:border-[var(--accent)]',
    text: 'text-[var(--accent)]',
    glow: 'group-hover:shadow-[0_0_28px_-6px_rgba(245,181,74,0.8)]',
  },
  blue: {
    ring: 'border-[var(--accent-blue)]/35 group-hover:border-[var(--accent-blue)]',
    text: 'text-[var(--accent-blue)]',
    glow: 'group-hover:shadow-[0_0_28px_-6px_rgba(96,165,250,0.8)]',
  },
  teal: {
    ring: 'border-[var(--accent-teal)]/35 group-hover:border-[var(--accent-teal)]',
    text: 'text-[var(--accent-teal)]',
    glow: 'group-hover:shadow-[0_0_28px_-6px_rgba(45,212,191,0.8)]',
  },
}

const CAPABILITIES = [
  { icon: Compass, title: 'Hybrid retrieval', body: 'Dense + BM25 fused by rank, then reranked.' },
  { icon: Quote, title: 'Traceable citations', body: 'Every answer points back to document and page.' },
  { icon: ShieldCheck, title: 'Refusal on weak evidence', body: 'No supporting passage? The Tutor says so.' },
  { icon: Layers, title: 'Auditable adaptation', body: 'Chosen by mastery and repeated mistakes — not your last answer.' },
  { icon: SquarePen, title: 'Open-ended grading', body: 'Scores understanding, accuracy, relevance, missing concepts.' },
  { icon: Brain, title: 'Mastery & growth', body: 'Improving, stable or needs attention — with the delta.' },
  { icon: Lightbulb, title: 'Recommendations', body: 'One next action, from weaknesses, mistakes and goals.' },
  { icon: Database, title: 'Persistent context', body: 'Goals, mistakes and history survive the session.' },
  { icon: RefreshCw, title: 'Background work', body: 'Job states, retries and recovery — no open tab needed.' },
  { icon: Lock, title: 'Project isolation', body: 'Retrieval, jobs and tools stay inside one Project.' },
  { icon: Network, title: 'Structured AI tools', body: 'The model acts only through validated, scoped calls.' },
  { icon: ChartNoAxesCombined, title: 'Analytics & admin', body: 'Activity, AI usage, latency and system health.' },
]

const TRUST = [
  'Grounded citations',
  'Unsupported questions refused',
  'Adaptive quiz',
  'Open-ended grading',
  'Mastery',
  'Growth',
  'Recommendations',
  'Admin console',
]

function StreakField() {
  return (
    <div aria-hidden="true" className="streak-field">
      {STREAKS.map((streak, index) => (
        <span
          key={index}
          className="streak"
          style={{
            left: streak.left,
            height: streak.height,
            '--streak-color': streak.color,
            '--streak-opacity': streak.opacity,
            '--streak-drift': streak.drift,
            animationDelay: streak.delay,
            animationDuration: streak.duration,
          }}
        />
      ))}
    </div>
  )
}

function Reveal({ children, delay = 0, className = '' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

/** Compact section intro — eyebrow, one short line, one clarifying line. */
function SectionHeading({ eyebrow, title, body }) {
  return (
    <Reveal className="mx-auto max-w-2xl text-center">
      <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--accent)]">{eyebrow}</span>
      <h2 className="mt-3 font-display text-[1.7rem] font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-[2.1rem]">
        {title}
      </h2>
      {body && <p className="mt-3.5 text-[0.95rem] leading-relaxed text-[var(--text-secondary)]">{body}</p>}
    </Reveal>
  )
}

function TopNav({ onSignIn, onGetStarted }) {
  return (
    <div className="sticky top-0 z-50 px-4 pt-4 sm:px-6">
      <nav className="glass-panel edge-highlight mx-auto flex max-w-5xl items-center justify-between gap-4 rounded-[var(--radius-pill)] px-4 py-2.5 shadow-[var(--shadow-pop)]">
        <a href="#top" className="flex shrink-0 items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl border border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/30 via-[var(--accent)]/10 to-transparent text-[var(--accent)]">
            <Sparkles className="size-4" strokeWidth={2.2} />
          </span>
          <span className="font-display text-sm font-bold tracking-tight text-[var(--text-primary)]">
            Study Companion
          </span>
        </a>

        <ul className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-full px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onSignIn}
            className="hidden rounded-[var(--radius-pill)] px-3.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] sm:block"
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={onGetStarted}
            className="bg-gradient-cta shine inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-4 py-2 text-xs font-bold text-[#16110A] shadow-[var(--glow-accent)] transition hover:brightness-110"
          >
            Get started
            <ArrowRight className="size-3.5" />
          </button>
        </div>
      </nav>
    </div>
  )
}

function Hero({ onGetStarted, onSignIn }) {
  return (
    /* Full viewport height: the loop section must start below the fold, so the
       first screen reads as one composed statement rather than two halves. */
    <header
      id="top"
      className="relative flex min-h-[calc(100svh-4rem)] flex-col justify-center overflow-hidden px-4 py-14 sm:px-6"
    >
      <StreakField />
      <div aria-hidden="true" className="hero-halo pointer-events-none absolute inset-x-0 top-0 h-[620px]" />

      <div className="relative mx-auto max-w-3xl text-center">
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--accent)]"
        >
          <span className="size-1.5 animate-pulse rounded-full bg-current" />
          AI-powered learning workspace
        </motion.span>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
          className="mt-6 font-display text-[1.9rem] font-bold leading-[1.1] tracking-[-0.03em] text-[var(--text-primary)] sm:text-4xl lg:text-[2.9rem]"
        >
          Study smarter with
          <span className="text-gradient-brand"> your own PDFs</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mx-auto mt-5 max-w-xl text-[0.95rem] leading-relaxed text-[var(--text-secondary)] sm:text-base"
        >
          Grounded answers with citations, adaptive quizzes and graded written assessments. Mastery, growth and one
          clear next step — for every Project.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.16 }}
          className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <button
            type="button"
            onClick={onGetStarted}
            className="bg-gradient-cta shine inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] px-6 py-3 text-sm font-bold text-[#16110A] shadow-[var(--glow-accent)] transition hover:brightness-110 sm:w-auto"
          >
            Create your workspace
            <ArrowRight className="size-4" />
          </button>
          <button
            type="button"
            onClick={onSignIn}
            className="inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] border border-[var(--border-strong)] bg-[var(--surface-1)]/70 px-6 py-3 text-sm font-semibold text-[var(--text-primary)] backdrop-blur transition hover:border-[var(--accent)]/40 hover:bg-[var(--surface-2)] sm:w-auto"
          >
            I already have an account
          </button>
        </motion.div>

        <Reveal delay={0.2} className="mt-8">
          <ul className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
            {TRUST.map((item) => (
              <li key={item} className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-muted)]">
                <span className="size-1 rounded-full bg-[var(--accent)]/70" />
                {item}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.28} className="mt-10">
          <a
            href="#the-loop"
            className="group inline-flex flex-col items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)] transition hover:text-[var(--accent)]"
          >
            Scroll to explore
            <span className="grid size-7 place-items-center rounded-full border border-[var(--border)] transition group-hover:border-[var(--accent)]/50">
              <ChevronDown className="size-3.5 animate-float-slow" />
            </span>
          </a>
        </Reveal>
      </div>
    </header>
  )
}

function LoopSection() {
  return (
    <section id="the-loop" className="landing-anchor px-4 py-16 sm:px-6 sm:py-20">
      <SectionHeading
        eyebrow="The learning loop"
        title="Five steps, then back to the start"
        body="Material becomes knowledge, knowledge becomes questions, and questions become your next move."
      />

      <div className="relative mx-auto mt-12 max-w-6xl">
        {/* The rail the stages sit on, with a pulse travelling along it. */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-[var(--accent)]/35 to-transparent lg:block"
        >
          <span className="rail-dot" />
        </div>

        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {LOOP.map((step, index) => {
            const tone = NODE_TONES[step.tone] ?? NODE_TONES.accent
            return (
              <li key={step.title} className="group relative flex flex-col items-center text-center">
                {/* Stage node — an icon on the rail rather than a step number. */}
                <span
                  className={`relative z-10 grid size-12 shrink-0 place-items-center rounded-full border bg-[var(--bg)] shadow-[0_0_0_6px_var(--bg)] transition duration-300 group-hover:scale-105 ${tone.ring} ${tone.text} ${tone.glow}`}
                >
                  <step.icon className="size-5" />
                </span>

                {/* Direction arrow on the rail, between stages. */}
                {index < LOOP.length - 1 && (
                  <ChevronRight
                    aria-hidden="true"
                    className="absolute -right-[22px] top-[14px] hidden size-4 text-[var(--accent)]/45 transition group-hover:text-[var(--accent)] lg:block"
                  />
                )}

                <div className="mt-4 w-full rounded-[var(--radius-card)] border border-transparent p-3 transition group-hover:border-[var(--border-glow)] group-hover:bg-[var(--surface-1)]/70">
                  <h3 className="font-display text-sm font-semibold tracking-tight text-[var(--text-primary)]">
                    {step.title}
                  </h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">{step.body}</p>
                </div>
              </li>
            )
          })}
        </ol>

        {/* The loop closes: evidence from step 5 becomes the next question. */}
        <Reveal delay={0.1} className="relative mt-3 hidden h-8 lg:block">
          <div
            aria-hidden="true"
            className="absolute inset-x-10 top-0 h-full rounded-b-[26px] border-x border-b border-dashed border-[var(--border-strong)]"
          />
          <span className="absolute -left-1 bottom-[-7px] grid size-4 place-items-center rounded-full border border-[var(--accent)]/40 bg-[var(--bg)] text-[var(--accent)]">
            <ChevronDown className="size-3 rotate-90" />
          </span>
          <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-pill)] border border-[var(--border)] bg-[var(--bg)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            feeds the next question
          </span>
        </Reveal>
      </div>
    </section>
  )
}

function CapabilitiesSection() {
  return (
    <section
      id="capabilities"
      className="landing-anchor border-y border-[var(--border)] bg-[var(--bg-elevated)]/60 px-4 py-16 sm:px-6 sm:py-20"
    >
      <SectionHeading
        eyebrow="Capabilities"
        title="Built as separate responsibilities"
        body="Not one large prompt — retrieval, grounding, assessment, mastery and observability as real services."
      />

      <div className="mx-auto mt-10 grid max-w-5xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map((item, index) => (
          <Reveal key={item.title} delay={(index % 3) * 0.04}>
            <article className="group flex h-full items-start gap-3 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface-1)]/60 p-4 transition hover:-translate-y-0.5 hover:border-[var(--border-glow)] hover:bg-[var(--surface-2)]/70">
              <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent)] transition group-hover:border-[var(--accent)]/40 group-hover:bg-[var(--accent-soft)]">
                <item.icon className="size-4" />
              </span>
              <div className="min-w-0">
                <h3 className="font-display text-sm font-semibold tracking-tight text-[var(--text-primary)]">
                  {item.title}
                </h3>
                <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-secondary)]">{item.body}</p>
              </div>
            </article>
          </Reveal>
        ))}
      </div>
    </section>
  )
}

function ClosingCta({ onGetStarted, onSignIn }) {
  return (
    <section className="relative overflow-hidden px-4 py-20 sm:px-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-[var(--accent-soft)] to-transparent"
      />
      <Reveal className="relative mx-auto max-w-2xl text-center">
        <h2 className="font-display text-[1.85rem] font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-[2.6rem]">
          Bring your own material,
          <span className="text-gradient-brand"> Master It</span>
        </h2>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onGetStarted}
            className="bg-gradient-cta shine inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] px-6 py-3 text-sm font-bold text-[#16110A] shadow-[var(--glow-accent)] transition hover:brightness-110 sm:w-auto"
          >
            Get started free
            <ArrowRight className="size-4" />
          </button>
          <button
            type="button"
            onClick={onSignIn}
            className="inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] border border-[var(--border-strong)] px-6 py-3 text-sm font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text-primary)] sm:w-auto"
          >
            Sign in
          </button>
        </div>
      </Reveal>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-[var(--border)] px-4 py-6 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-3 sm:flex-row">
        <div className="flex items-center gap-2.5">
          <span className="grid size-7 place-items-center rounded-lg border border-[var(--accent)]/25 bg-[var(--accent-soft)] text-[var(--accent)]">
            <Sparkles className="size-3" />
          </span>
          <span className="font-display text-xs font-bold tracking-tight text-[var(--text-primary)]">
            Study Companion
          </span>
        </div>
        <p className="text-center text-[11px] text-[var(--text-muted)]">
          What am I learning? · How well? · What&apos;s next?
        </p>
        <p className="font-mono-numbers text-[10px] text-[var(--text-muted)]/70">
          FastAPI · LangGraph · FAISS + BM25 · React 19
        </p>
      </div>
    </footer>
  )
}

export default function LandingPage({ onSignIn, onGetStarted }) {
  return (
    <main className="app-aurora min-h-screen">
      <TopNav onSignIn={onSignIn} onGetStarted={onGetStarted} />
      <Hero onGetStarted={onGetStarted} onSignIn={onSignIn} />
      <LoopSection />
      <CapabilitiesSection />
      <ClosingCta onGetStarted={onGetStarted} onSignIn={onSignIn} />
      <Footer />
    </main>
  )
}
