/**
 * ══════════════════════════════════════════════════════════════
 * Planner Types — Adaptive Agent Planner response interface
 * ══════════════════════════════════════════════════════════════
 */

import type { UtsVector } from '@/lib/theory-scoring';
import type { AgentEntry } from '@/lib/agent-registry';
import type { AgentRecommendation } from '@/components/shared/AgentOrchestrator';

export interface PlannerResult {
  decision: 'continue' | 'stop' | 'agent_gap';
  selectedAgent: AgentEntry | null;
  recommendation: AgentRecommendation | null;
  justification: string;
  utsVectorTargeted: UtsVector | null;
  confidenceLevel: 'HIGH' | 'MODERATE' | 'LOW';
  confidenceBasis: string;
  agentGap: {
    vector: UtsVector;
    capability: string;
    suggestedName: string;
    description: string;
  } | null;
  stopReason: string | null;
  reasoning: string;
}

/** Parse Claude's JSON response into a typed PlannerResult */
export function parsePlannerResponse(responseText: string, registry: AgentEntry[]): PlannerResult {
  // Default fallback
  const fallback: PlannerResult = {
    decision: 'continue',
    selectedAgent: null,
    recommendation: null,
    justification: 'Planner response could not be parsed. Falling back to heuristic.',
    utsVectorTargeted: null,
    confidenceLevel: 'LOW',
    confidenceBasis: 'Planner unavailable',
    agentGap: null,
    stopReason: null,
    reasoning: responseText,
  };

  try {
    // Extract JSON from potential markdown code blocks
    let jsonStr = responseText.trim();
    if (jsonStr.startsWith('```')) {
      jsonStr = jsonStr.replace(/```json?\n?/g, '').replace(/```/g, '').trim();
    }
    const parsed = JSON.parse(jsonStr);

    const selectedAgent = parsed.selectedAgent
      ? registry.find(a => a.id === parsed.selectedAgent) || null
      : null;

    // Build AgentRecommendation from selected agent (fits existing UI interface)
    let recommendation: AgentRecommendation | null = null;
    if (selectedAgent) {
      recommendation = {
        id: `planner-rec-${Date.now()}`,
        agentType: selectedAgent.id as any,
        target: parsed.target || 'Investigation targets',
        reason: parsed.justification || '',
        confidence: parsed.confidenceLevel === 'HIGH' ? 85 : parsed.confidenceLevel === 'MODERATE' ? 65 : 45,
        priority: parsed.confidenceLevel === 'HIGH' ? 'critical' : parsed.confidenceLevel === 'MODERATE' ? 'high' : 'medium',
        estimate: {
          time: `${selectedAgent.estimatedTimeSeconds}s`,
          cost: `$${selectedAgent.estimatedCostUSD.toFixed(2)}`,
        },
        dataSources: selectedAgent.dataSources,
      };
    }

    return {
      decision: parsed.decision || 'continue',
      selectedAgent,
      recommendation,
      justification: parsed.justification || '',
      utsVectorTargeted: parsed.utsVectorTargeted || null,
      confidenceLevel: parsed.confidenceLevel || 'MODERATE',
      confidenceBasis: parsed.confidenceBasis || '',
      agentGap: parsed.agentGap || null,
      stopReason: parsed.stopReason || null,
      reasoning: responseText,
    };
  } catch {
    return fallback;
  }
}
