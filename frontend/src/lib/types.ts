export interface ATSScoreBreakdown {
  keyword_match: number
  section_completeness: number
  format_parsability: number
  keyword_placement: number
  date_consistency: number
  file_health: number
  total: number
}

export type FlagType = 'red' | 'yellow' | 'info'
export type FlagCategory =
  | 'experience_gap'
  | 'domain_mismatch'
  | 'skill_missing'
  | 'location_mismatch'
  | 'education_mismatch'
  | 'seniority_mismatch'
  | 'notice_period'
  | 'certification_missing'

export interface PreflightFlag {
  flag_type: FlagType
  category: FlagCategory
  title: string
  message: string
  detail?: string
  requires_acknowledgement: boolean
}

export type SkillStatus = 'matched' | 'can_add' | 'partial' | 'missing'

export interface SkillItem {
  skill: string
  status: SkillStatus
  related_skill?: string
  user_decision?: boolean
}

export interface AnalysisResult {
  session_id: string
  match_score: number
  ats_score_before: ATSScoreBreakdown
  flags: PreflightFlag[]
  skills: SkillItem[]
  experience_candidate?: number
  experience_required_min?: number
  experience_required_max?: number
  domain_candidate?: string
  domain_jd?: string
  missing_certifications: string[]
}

export interface UserConfirmation {
  session_id: string
  flags_acknowledged: string[]
  skills_to_add: string[]
  skills_to_skip: string[]
  rewrite_summary: boolean
  rewrite_bullets: boolean
  reorder_sections: boolean
  adjust_tone: boolean
  template_choice?: string
}

export interface OptimizationResult {
  session_id: string
  ats_score_before: ATSScoreBreakdown
  ats_score_after: ATSScoreBreakdown
  match_score_before: number
  match_score_after: number
  skills_added: string[]
  keywords_injected: string[]
  sections_rewritten: string[]
  known_gaps: string[]
  suggestions: string[]
  docx_filename: string
  pdf_filename?: string
  report_filename: string
}
