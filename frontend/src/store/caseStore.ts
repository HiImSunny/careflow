/**
 * Zustand store for global CareFlow application state.
 * Requirements: 4.4, 4.5
 */

import { create } from 'zustand';
import type { AgentMessage, CarePlan } from '../types';

/** Shape of the global case store. */
export interface CaseStore {
  // State
  caseText: string;
  caseImage: File | null;
  carePlan: CarePlan | null;
  agentMessages: AgentMessage[];
  loading: boolean;
  error: string | null;
  pendingCaseId: string | null;  // set before POST so SSE can connect early

  // Actions
  setCaseText: (text: string) => void;
  setCaseImage: (file: File | null) => void;
  setCarePlan: (plan: CarePlan) => void;
  addAgentMessage: (msg: AgentMessage) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setPendingCaseId: (id: string | null) => void;
  reset: () => void;
}

const initialState = {
  caseText: '',
  caseImage: null,
  carePlan: null,
  agentMessages: [],
  loading: false,
  error: null,
  pendingCaseId: null,
};

export const useCaseStore = create<CaseStore>((set) => ({
  ...initialState,

  setCaseText: (text) => set({ caseText: text }),
  setCaseImage: (file) => set({ caseImage: file }),
  setCarePlan: (plan) => set({ carePlan: plan }),
  addAgentMessage: (msg) =>
    set((state) => ({ agentMessages: [...state.agentMessages, msg] })),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setPendingCaseId: (id) => set({ pendingCaseId: id }),
  reset: () => set(initialState),
}));
