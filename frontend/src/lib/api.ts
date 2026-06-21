import axios from 'axios'
import type { AnalysisResult, UserConfirmation, OptimizationResult } from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 300_000, // 5 min — covers slow OpenAI responses under high API load
})

export async function uploadFiles(
  resume: File,
  jd: File,
  template: File | null,
  templateChoice: string | null,
): Promise<{ session_id: string }> {
  const form = new FormData()
  form.append('resume', resume)
  form.append('jd', jd)
  if (template) form.append('template', template)
  if (templateChoice) form.append('template_choice', templateChoice)

  const res = await api.post('/upload/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function analyzeSession(sessionId: string): Promise<AnalysisResult> {
  const res = await api.post('/analyze/', { session_id: sessionId })
  return res.data
}

export async function optimizeResume(confirmation: UserConfirmation): Promise<OptimizationResult> {
  const res = await api.post('/optimize/', confirmation)
  return res.data
}

export function getDownloadUrl(sessionId: string, type: 'docx' | 'pdf' | 'report'): string {
  return `${API_URL}/download/${sessionId}/${type}`
}

export async function getSessionStatus(sessionId: string) {
  const res = await api.get(`/download/${sessionId}/status`)
  return res.data
}
