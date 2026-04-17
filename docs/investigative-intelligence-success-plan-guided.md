# [Customer Name] — Investigative Intelligence Platform
# Guided Implementation Plan

---

## PoC Team

| Role | Name | Organization |
|------|------|-------------|
| Business Decision Owner | | |
| Technical Lead | | |
| Analyst Champion | | |
| AWS Lead | | Emerging Tech Solutions |

---

## Business Outcome

*From Discovery Questionnaire*

| # | Outcome | Target |
|---|---------|--------|
| 1 | | |
| 2 | | |

## Technical Outcome

| # | Outcome | Target |
|---|---------|--------|
| 1 | | |
| 2 | | |

---

## How This Works

We don't ask you to block out days or sit in all-day sessions. Instead:

1. We start with a short workshop to orient your team
2. Then we meet **every Tuesday and Thursday at 10am for 1 hour**
3. Each session: you show us what you built, we give feedback, you get your next assignment
4. You work at your own pace between sessions

This gives your team the elapsed time to complete each step without disrupting their day-to-day work. The platform is pre-built — your job is to connect your data, validate the results, and decide if it fits your workflow.

```
Week 1          Week 2          Week 3          Week 4          Week 5          Week 6
┌─────┐        ┌──┐  ┌──┐     ┌──┐  ┌──┐     ┌──┐  ┌──┐     ┌──┐  ┌──┐     ┌──┐
│ WS  │        │Tu│  │Th│     │Tu│  │Th│     │Tu│  │Th│     │Tu│  │Th│     │Go│
│ 3hr │        │1h│  │1h│     │1h│  │1h│     │1h│  │1h│     │1h│  │1h│     │No│
└─────┘        └──┘  └──┘     └──┘  └──┘     └──┘  └──┘     └──┘  └──┘     └──┘
 Orient        Deploy &        Load Real       Investigate     Secure &        Decide
               First Data      Dataset         & Validate      Harden
```

**Total customer time commitment: ~3 hours in Week 1, then 2 hours/week for 5 weeks = ~13 hours over 6 weeks.**

---

## Week 1: Orient — Kickoff Workshop (3 hours, one session)

**Purpose:** Your team sees the full platform, understands the architecture, and leaves with a clear first assignment.

| Time | Topic | What Happens |
|------|-------|-------------|
| 0:00 - 0:45 | Live Demo | Full platform walkthrough with real investigative data — search, knowledge graph, AI briefings, theories, anomaly detection |
| 0:45 - 1:15 | Your Use Case Mapping | Discussion: how does this map to your investigations? What matters most? |
| 1:15 - 1:30 | Break | |
| 1:30 - 2:15 | Architecture & Data Loader | How the 6 services work together. How data flows in. What your team needs to do vs. what's automated. |
| 2:15 - 3:00 | Deployment Walkthrough & Assignment #1 | Watch us deploy the template in 20 minutes. Your assignment: do the same in your account by Thursday. |

**Assignment #1:** Deploy the CloudFormation template in your GovCloud account. Run the Aurora migration. Upload the frontend. Confirm you can access the UI.

---

## Week 2: Connect — Deploy & First Data

### Tuesday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Your deployed environment — show us the UI running in your account | Troubleshoot any deployment issues. Walk through the data loader configuration. | **Assignment #2:** Configure the data loader for your file types. Upload 500-1,000 sample documents. Verify they appear in the UI. |

### Thursday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Your first batch of documents loaded — show us search results | Review data quality: Are entities being extracted correctly? Is search returning relevant results? | **Assignment #3:** Load your full pilot dataset (10K-50K docs). Let it run overnight. Note any errors or quality issues. |

---

## Week 3: Load — Real Dataset at Scale

### Tuesday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Pilot dataset loaded — show us the numbers (docs, entities, relationships) | Review scale: How did the pipeline handle your data? Any blank pages, OCR issues, timeouts? | **Assignment #4:** Run the AI briefing on your top 3 cases. Generate theories. Try semantic search with real investigative queries. |

### Thursday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| AI briefing results — are they useful? Search results — are they relevant? | Discuss: What's working? What's missing? Any features that don't apply to your workflow? | **Assignment #5:** Have 2-3 analysts use the platform independently for a week. Capture their feedback. |

---

## Week 4: Investigate — Analyst Validation

### Tuesday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Analyst feedback so far — what do they like? What's confusing? | Discuss adjustments. Walk through any features they haven't tried (hypothesis testing, cross-case analysis, knowledge graph). | Continue analyst evaluation. Try cross-case analysis if you have multiple cases loaded. |

### Thursday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Cross-case results. Any patterns discovered? | Review the knowledge graph — are entity connections meaningful? Discuss data governance needs. | **Assignment #6:** Document your access control requirements. How many teams? Do they need case isolation? What classification levels? |

---

## Week 5: Secure — Authentication & Access Control

### Tuesday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Your access control requirements document | Walk through authentication options (Cognito, SAML, PIV/CAC). Decide: label-based, RLS, or hybrid? | **Assignment #7:** Configure authentication integration. Test with 2-3 users at different access levels. |

### Thursday Check-In (1 hour)

| What You Show Us | What We Cover | Assignment |
|-----------------|---------------|------------|
| Authentication working — show us login flow and access control in action | Verify: users only see authorized data. Review audit trail. | **Assignment #8:** Prepare your evaluation summary. Compile analyst feedback, performance numbers, and cost projections. |

---

## Week 6: Decide — Go / No-Go

### Tuesday: Executive Readout (1 hour)

| Agenda | Who |
|--------|-----|
| Platform demo with customer's own data | AWS + Customer technical lead |
| Analyst feedback summary | Customer analyst champion |
| Performance metrics and cost model | AWS |
| Production roadmap and timeline | Joint |
| Go / No-Go discussion | Customer leadership |

---

## What Success Looks Like

| Criteria | Target | Result |
|----------|--------|--------|
| Deployment: template deploys cleanly in GovCloud | Yes / No | |
| Data loading: pilot dataset ingested without errors | ≥ 95% success | |
| AI briefing quality (analyst rating 1-5) | ≥ 4.0 | |
| Search relevance — finds what analysts expect | ≥ 80% | |
| Entity extraction — names, orgs, dates correct | ≥ 85% | |
| Query response time | < 5 seconds | |
| Analyst recommendation | Would use daily | |

---

## What's Already Built

This is not a build-from-scratch project. The platform is production-tested:

- 82,529 documents processed with entities, embeddings, and knowledge graph
- Config-driven deployment: one CloudFormation template, 3 tiers
- 30+ deployment issues discovered and resolved
- Well-Architected review completed
- Data governance framework with access control and audit trail

Your pilot validates fit, not feasibility.

---

## Budget

| Category | Estimated Cost |
|----------|---------------|
| Workshop + check-in calls | Included (AWS-led) |
| AWS services (6-week pilot) | $3,000 - $8,000 |
| ProServe (if custom integration needed) | TBD |

---

## Next Steps

1. ☐ Complete Discovery Questionnaire
2. ☐ Schedule Week 1 Workshop (3 hours)
3. ☐ Set recurring Tuesday/Thursday 10am check-ins
4. ☐ Identify technical lead + 2-3 analyst participants
5. ☐ Confirm GovCloud account access
