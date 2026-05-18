/**
 * Shared TypeScript types mirroring backend Pydantic schemas.
 * Requirements: 4.4, 4.5
 */

/** A single entry in the care plan timeline. */
export interface TimelineEntry {
  timestamp: string;
  specialty: string;
  description: string;
}

/** Structured findings produced by a Specialty Agent. */
export interface SpecialtyFindings {
  specialty: string;
  summary: string;
  action_items: string[];
}

/** Unified care plan reconciled by the Coordinator Agent. */
export interface CarePlan {
  case_id: string;
  timeline: TimelineEntry[];
  recommendations: string[];
  alerts: string[];
  findings: Record<string, SpecialtyFindings>;
}

/** A message emitted by an agent during orchestration. */
export interface AgentMessage {
  agent: string;
  content: string;
  timestamp: string;
}

/** Input payload for POST /api/orchestrate. */
export interface OrchestrateInput {
  text?: string;
  image_b64?: string;
  case_id?: string;
}

/** A pre-loaded sample case for demonstration and testing. */
export interface SampleCase {
  id: string;
  title: string;
  specialties: string[];
  text: string;
}
