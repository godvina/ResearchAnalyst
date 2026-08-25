/**
 * ══════════════════════════════════════════════════════════════
 * Evidence Audit Trail — Type Definitions
 * DOJ-Compliant Chain of Custody for TALOS
 * ══════════════════════════════════════════════════════════════
 */

// ── Evidence Trace (main data structure) ──

export interface EvidenceTraceData {
  findingId: string;
  findingText: string;
  chain: EvidenceChainLink[];
  counterIndicators: CounterIndicator[];
  confidenceExplanation: ConfidenceBreakdown;
  methodology: MethodologyReference;
  exportedAt?: string;
}

export interface EvidenceChainLink {
  step: 'source' | 'extraction' | 'pattern-match' | 'analyst-approval' | 'ai-conclusion';
  timestamp: string; // ISO UTC, second precision
  description: string;
  icon: string; // lucide-react icon name
  details: ChainLinkDetails;
}

export interface ChainLinkDetails {
  // Source step
  documentId?: string;
  documentTitle?: string;
  documentHash?: string;
  sourceUrl?: string;
  sourceAgency?: string;
  corpus?: string;
  passageOffsets?: { start: number; end: number; text: string }[];
  ingestedAt?: string;
  ingestionMethod?: string;

  // Extraction step
  model?: string;
  modelVersion?: string;
  chunkId?: string;
  chunkScore?: number;
  extractionType?: 'entity' | 'relationship' | 'finding';

  // Pattern Match step
  signatureId?: string;
  signatureName?: string;
  similarity?: number;
  vectorStore?: string;
  matchedConditions?: string[];

  // Analyst Approval step
  analystId?: string;
  analystName?: string;
  decision?: 'approved' | 'rejected' | 'escalated';
  notes?: string;

  // AI Conclusion step
  prompt?: string;
  confidence?: number;
  conclusionType?: string;
}

// ── Counter-Indicators (Brady Compliance) ──

export interface CounterIndicator {
  id: string;
  type: 'alternative-explanation' | 'non-criminal-context' | 'temporal-gap' | 'dual-use';
  description: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  mitigating: boolean; // true if this weakens the finding
}

// ── Confidence Breakdown ──

export interface ConfidenceBreakdown {
  overall: number;
  previousScore?: number; // for delta display
  deltaReason?: string;
  factors: ConfidenceFactor[];
}

export interface ConfidenceFactor {
  name: string;
  score: number; // 0-100
  weight: number; // how much this factor contributes (0-1)
  explanation: string; // plain English
}

// ── Methodology (Daubert Compliance) ──

export interface MethodologyReference {
  modelName: string;
  modelVersion: string;
  provider: string;
  taskType: string;
  knownLimitations: string[];
  falsePositiveRate: number; // percentage
  validationScore: number;
  lastValidated: string;
}

// ── Source Document Registry ──

export interface SourceDocument {
  documentId: string;
  title: string;
  originalText: string;
  sha256Hash: string;
  ingestedAt: string; // ISO UTC
  sourceUrl: string;
  sourceAgency: string;
  fileFormat: string;
  ingestionMethod: string; // trawler name or 'manual-upload'
  corpus: string;
  pageCount: number;
  versions: DocumentVersion[];
  modified?: boolean; // flag when content changed on re-pull
  /** Local file path to the original PDF (for demo) */
  localFilePath?: string;
  /** Page number(s) where the key passage appears */
  pageReference?: string;
}

export interface DocumentVersion {
  version: number;
  sha256Hash: string;
  ingestedAt: string;
  contentDelta?: string; // description of what changed
}

export interface HighlightRange {
  findingId: string;
  start: number;
  end: number;
  text: string;
  color: string;
}

// ── Audit Log (28 CFR Part 23 + CJIS) ──

export interface AuditLogEntry {
  id: string;
  timestamp: string; // ISO UTC
  analystId: string;
  analystName: string;
  actionType: AuditActionType;
  target: string; // documentId, entityId, laneId, etc.
  targetType: 'document' | 'entity' | 'lane' | 'finding' | 'export' | 'search';
  result: 'success' | 'denied' | 'error';
  metadata?: Record<string, string>;
}

export type AuditActionType =
  | 'document-access'
  | 'search-query'
  | 'investigation-start'
  | 'investigation-approve'
  | 'investigation-reject'
  | 'export-action'
  | 'entity-view'
  | 'evidence-trace-view'
  | 'finding-review';

// ── Export (Court-Ready Package) ──

export interface ExportRequest {
  findingIds: string[];
  format: 'pdf' | 'json' | 'docx';
  caseNumber: string;
  dateRange: { start: string; end: string };
  analysts: string[];
  includeBrady: boolean;
  includeMethodology: boolean;
  includeAuditTrail: boolean;
}

export interface ExportPackage {
  coverPage: CoverPageData;
  findings: ExportedFinding[];
  sourceDocuments: SourceDocument[];
  methodology: MethodologyReference[];
  bradyDisclosure: CounterIndicator[];
  auditTrail: AuditLogEntry[];
  certificate: CertificateOfAuthenticity;
}

export interface CoverPageData {
  caseNumber: string;
  dateRange: { start: string; end: string };
  analysts: string[];
  systemVersion: string;
  totalEvidenceItems: number;
  generatedAt: string;
}

export interface CertificateOfAuthenticity {
  documentHashes: { documentId: string; hash: string; verified: boolean }[];
  systemIntegrityCheck: boolean;
  generatedAt: string;
  generatedBy: string;
}

export interface ExportedFinding {
  findingId: string;
  findingText: string;
  chain: EvidenceChainLink[];
  counterIndicators: CounterIndicator[];
  confidenceBreakdown: ConfidenceBreakdown;
}

// ── Highlight Color Palette ──

export const HIGHLIGHT_PALETTE = [
  'amber',   // primary highlight color
  'cyan',    // second finding
  'purple',  // third finding
  'green',   // fourth finding
  'pink',    // fifth finding
  'blue',    // sixth finding
  'orange',  // seventh finding
  'red',     // eighth finding
] as const;

/**
 * Deterministic color assignment for multiple highlights on same document.
 * For N findings (where N <= palette size), all colors are distinct.
 */
export function assignHighlightColor(findingIndex: number): string {
  return HIGHLIGHT_PALETTE[findingIndex % HIGHLIGHT_PALETTE.length];
}
