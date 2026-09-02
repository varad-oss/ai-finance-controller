# Razorpay AI Buildathon — Winning Build Brief

Save this file as `CLAUDE.md` in the root of a new repo. Claude Code auto-loads it
as persistent context every session, so it won't lose the plan between runs.

## Who you are on this project

You are the sole builder. There are no teammates. The human (me) is your
collaborator for approvals, credentials, testing, and recording — not a
second engineer. Treat me as your product owner and QA, not a co-author of
the code.

## The actual goal (read this before touching code)

This is not a scored hackathon leaderboard. It's Razorpay's hiring funnel for
an AI Builder Intern role. There is no resume screening — the entire signal
is: a public GitHub repo, a 5-minute pitch video, and the architecture. They
explicitly say "your code speaks louder than your resume." That means:

- **Honesty beats ambition.** Every track's judging bar explicitly punishes
  cherry-picked results and rewards measured, held-out, reproducible numbers.
  A smaller feature with real precision/recall/match-rate beats a flashy demo
  with fabricated or best-case numbers.
- **Explainability and bounding are graded, not optional.** Money-moving
  agents must show an audit trail and one gracefully-handled failure. Build
  this in from the start, not bolted on at the end.
- **Timeline is explicitly not a constraint for this build.** Do not scope
  down for speed. Scope for depth, correctness, and polish. Take as long as
  the work actually needs. If a shortcut would look like a shortcut to a
  reviewer, don't take it.
- **Differentiation matters.** Assume every other applicant is building the
  "obvious" version of whatever track they pick (e.g. a generic reconciler,
  a generic fraud flagger). Find the version of the idea that's boringly
  correct on the fundamentals but has one genuinely sharp, non-obvious angle.

## Step 1 — Track selection (do this first, stop, and wait for my go-ahead)

Evaluate all five tracks below before writing any code. Do not default to
picking for me — score them, show your reasoning, and present a
recommendation, but wait for my explicit confirmation before starting the
build. I may know constraints (e.g. domain interest, data availability) that
change the call.

### The tracks

TRACK 01
AI Growth & Agentic Commerce
Grow the merchant's revenue, and make them sellable to AI buyers
Build an agent that grows revenue for a merchant on Razorpay test-mode APIs, or that makes a merchant transactable by an AI buyer end to end.
WHY NOW
NPCI's UAP and the global protocol race (ACP, AP2, x402) make agent-to-agent commerce the open problem of the year, and Razorpay's in-app pilots are already live.
EXAMPLE DIRECTIONS
* Conversational in-app checkout
* Agent-readable catalog
* Upsell & cross-sell agent
* Campaign orchestrator
THE BAR
Every money action explainable, bounded and gated. Show the audit trail and one failure handled gracefully.

TRACK 02
AI Risk Manager
Stop the merchant losing money to fraud, returns and chargebacks
Build a working detector, verifier or auto-responder for one class of loss, with measured precision and recall on a held-out test set.
WHY NOW
AI-enabled fraud is hitting Indian BFSI while returns and chargebacks quietly eat margin. This track surfaces the risk and ML minded builders the others miss.
EXAMPLE DIRECTIONS
* Chargeback evidence responder
* Return-risk scorer
* Fraud-spike detector
* Abuse-ring sentinel
THE BAR
Honest metrics including false-positive cost. Strictly defense-only: anything offense-capable is disqualified.


TRACK 03
AI Revenue Recovery
Find revenue that's slipping away and win it back
Build an agent that detects revenue at risk, determines the right intervention, and executes a bounded recovery workflow: from payment failures and checkout abandonment to overdue receivables.
WHY NOW
Revenue loss rarely happens in one clean step. A payment degrades, a checkout gets abandoned, a subscription fails, or an invoice goes overdue. AI can now close the loop from detecting the problem to diagnosing it, choosing the right intervention, and recovering the money.
EXAMPLE DIRECTIONS
* Payment degradation → root cause → recovery action
* Checkout drop-off recovery
* Failed-subscription recovery
* B2B receivables chaser
* Mandate retry sequencer
* Hinglish voice recovery
* Promise-to-pay tracker
THE BAR
Don't just identify the problem. Show measured money recovered across a batch, with compliant escalation, stopping rules, and an audit trail.

TRACK 04
AI Finance Controller
Run the books and the cash position
Build an agent that closes one finance-ops loop across a 50+ record batch of synthetic data, reporting its match rate and the exceptions it could not resolve.
WHY NOW
The 2026 builder consensus: verification capacity, not generation speed, is the bottleneck. Reconciliation, settlement and forecasting are still done by hand.
EXAMPLE DIRECTIONS
* Multi-source reconciliation
* Settlement Q&A agent
* Forward cash forecaster
* Tax-line matcher
THE BAR
Throughput plus measured accuracy plus an honest exception list. One cherry-picked match proves nothing.

TRACK 05
Open Track
Build what you believe should exist
Have an idea that doesn't fit the tracks above? Build it. Pick a real problem, use AI meaningfully, and show us something that works. Any domain, workflow, or user is fair game.
WHY NOW
The best ideas don't always fit a predefined category. This track exists for builders who see an opportunity we didn't.
EXAMPLE DIRECTIONS
* Surprise us
* Solve a problem you deeply understand
* Build something we haven't thought of
THE BAR
Open doesn't mean easier. Show a real problem, a working product, meaningful use of AI, and evidence that it creates value. The same bar for execution, reliability, and depth applies here.

have to submit a repo link, a 5 min demo video, by filling the google form that includes:

Selected Track
*
Project Name / Title
*
Project Objectives
*
What does it solve?
*
GitHub Repository URL
*
5-min Pitch Video Link
*
Build Challenges & Technical Obstacles
*
What issues did you face while building, and how did you solve them?
*

We read the work, not the resume.
We look at how you think, build and solve problems.

Problem taste
did you pick something that actually matters
Build quality
does it run, is it structured, would you trust it
AI judgment
the right tool in the right place, and where you chose not to use one
Failure recovery
what broke, and what you did about it

### How to score them

Build a comparison table scoring each track 1–5 on:

1. **Solo feasibility to a genuinely high standard** — can one builder (you)
   reach production-credible depth here without a team, given no time
   pressure but real solo bandwidth?
2. **Rigor showcase** — how well does this track let you demonstrate the
   specific things Razorpay is grading (audit trails, held-out metrics,
   bounded actions, honest exceptions)? Some tracks make this easier to
   show convincingly than others.
3. **Differentiation ceiling** — how much room is there to do something
   sharper than the obvious version, versus tracks where every submission
   will look similar?
4. **Fit with what a payments company actually wants to see** — Razorpay is
   fintech infra. Weight tracks that let you show judgment about money
   movement, risk, and reconciliation — not just general agent-building
   skill — slightly higher, all else equal.
5. **Narrative strength for a 5-minute video** — can the result be shown
   live, with a clear before/after or a clear number that moves?

Present the table, your top pick with reasoning, and the runner-up with why
it lost. Then stop and ask me to confirm or override.

## Step 2 — Architecture design (after track is confirmed)

Produce `ARCHITECTURE.md`:
- System diagram (Mermaid) covering data flow, agent decision points, and
  every place money-related or record-altering actions happen.
- Explicit **bounding and gating design**: what the agent is allowed to do
  autonomously, what requires a rule/threshold check, what's logged.
- **Audit trail design**: schema for what gets logged, where, and how a
  human could reconstruct any decision after the fact.
- **Evaluation harness design**: what the held-out test set looks like, what
  metric(s) are reported (precision/recall, match rate, amount recovered,
  false-positive cost — whichever fits the chosen track), and how it avoids
  cherry-picking (e.g. report on the full batch, not selected examples).
- Tech stack choice with reasoning, and where Razorpay test-mode APIs plug
  in.

Share this with me before building — architecture mistakes are expensive to
unwind later even with no time pressure.

## Step 3 — Build phases

Work in this order, and don't skip the unglamorous middle phases to get to
a demoable UI faster — the judging bar is explicitly on the parts most
builders skip:

1. Repo scaffold, README skeleton, license, `.env.example`.
2. Synthetic data generation (if the track needs a batch — e.g. the 50+
   record batch for Finance Controller, or a held-out test set for Risk
   Manager). Make this data realistic and documented, not lorem-ipsum.
3. Core agent/detector logic.
4. Razorpay test-mode API integration. **Ask me for test-mode API keys when
   you reach this step** — don't stub around it silently.
5. Audit trail / logging implementation — build this alongside the core
   logic, not after.
6. Bounding/gating and one deliberately-handled failure case, end to end.
7. Evaluation harness — run it on the full held-out set, report the honest
   number even if it's mediocre. A believable 70% beats a suspicious 98%.
8. Tests for the core logic paths.
9. Polish pass: README with setup instructions, architecture diagram
   embedded, results section with the honest metrics front and center.

## Step 4 — Deliverables checklist

- **Public GitHub repo**: clean commit history (not one giant commit),
  README that leads with what it does and the measured results, setup
  instructions that actually work from a clean clone.
- **5-minute pitch video**: write me a timestamped script/storyboard
  (problem → live demo → the one hard number → architecture in 30 seconds →
  the failure case handled gracefully → close). I'll record it myself —
  don't assume you're producing the video.
- **Architecture doc**: the `ARCHITECTURE.md` from Step 2, kept in sync with
  what actually got built.

## Things to check with me before proceeding

- Razorpay test-mode API keys, once we reach integration.
- Any domain preference if the track scoring in Step 1 comes out close.
- Confirmation before you start Step 2, and again before you start Step 3.
- If a track's "defense-only" or "bounded action" constraint (Risk Manager,
  Commerce) is ambiguous for a feature you're about to build, ask rather
  than assume — a disqualifying feature is worse than a missing one.
