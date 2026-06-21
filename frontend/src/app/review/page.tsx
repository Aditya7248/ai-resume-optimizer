'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  AlertTriangle, AlertCircle, Info, CheckCircle2,
  ChevronRight, ChevronDown, ChevronUp, Loader2, X
} from 'lucide-react'
import { optimizeResume } from '@/lib/api'
import type { AnalysisResult, PreflightFlag, SkillItem, UserConfirmation } from '@/lib/types'

export default function ReviewPage() {
  const router = useRouter()
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [templateChoice, setTemplateChoice] = useState<string | undefined>(undefined)

  // User decisions
  const [acknowledgedFlags, setAcknowledgedFlags] = useState<Set<string>>(new Set())
  const [skillDecisions, setSkillDecisions] = useState<Record<string, boolean>>({})

  // Content section toggles
  const [rewriteSummary, setRewriteSummary] = useState(true)
  const [rewriteBullets, setRewriteBullets] = useState(true)
  const [reorderSections, setReorderSections] = useState(true)
  const [adjustTone, setAdjustTone] = useState(true)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const a = sessionStorage.getItem('analysis')
    const s = sessionStorage.getItem('session_id')
    const t = sessionStorage.getItem('template_choice')
    if (!a || !s) { router.push('/'); return }
    setAnalysis(JSON.parse(a))
    setSessionId(s)
    setTemplateChoice(t || undefined)
  }, [])

  if (!analysis) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-6 h-6 animate-spin text-brand-700" />
      </div>
    )
  }

  const redFlags = analysis.flags.filter(f => f.flag_type === 'red')
  const yellowFlags = analysis.flags.filter(f => f.flag_type === 'yellow')
  const infoFlags = analysis.flags.filter(f => f.flag_type === 'info')

  const unresolvedRed = redFlags.filter(f =>
    f.requires_acknowledgement && !acknowledgedFlags.has(f.category)
  )

  const matchedSkills = analysis.skills.filter(s => s.status === 'matched')
  const canAddSkills = analysis.skills.filter(s => s.status === 'can_add')
  const partialSkills = analysis.skills.filter(s => s.status === 'partial')
  const missingSkills = analysis.skills.filter(s => s.status === 'missing')
  // can_add + partial require explicit decisions; missing are optional (default skip)
  const requiredDecisionSkills = [...canAddSkills, ...partialSkills]
  const pendingSkillDecisions = requiredDecisionSkills.filter(s => skillDecisions[s.skill] === undefined)

  const canProceed = unresolvedRed.length === 0 && pendingSkillDecisions.length === 0

  function selectGroup(skills: typeof canAddSkills, add: boolean) {
    const updates: Record<string, boolean> = {}
    skills.forEach(s => { updates[s.skill] = add })
    setSkillDecisions(prev => ({ ...prev, ...updates }))
  }

  async function handleOptimize() {
    if (!canProceed || loading) return
    setLoading(true)
    setError(null)

    const confirmation: UserConfirmation = {
      session_id: sessionId,
      flags_acknowledged: Array.from(acknowledgedFlags),
      skills_to_add: Object.entries(skillDecisions).filter(([, v]) => v).map(([k]) => k),
      skills_to_skip: Object.entries(skillDecisions).filter(([, v]) => !v).map(([k]) => k),
      rewrite_summary: rewriteSummary,
      rewrite_bullets: rewriteBullets,
      reorder_sections: reorderSections,
      adjust_tone: adjustTone,
      template_choice: templateChoice || undefined,
    }

    try {
      const result = await optimizeResume(confirmation)
      sessionStorage.setItem('result', JSON.stringify(result))
      router.push('/result')
    } catch (e: any) {
      const detail = e?.response?.data?.detail || ''
      if (detail.includes('already in progress')) {
        setError('Optimization is already running — please wait for it to complete.')
      } else {
        setError(detail || 'Optimization failed. Please try again.')
      }
      setLoading(false)
    }
  }

  const contentSections = [
    {
      key: 'summary',
      label: 'Professional Summary',
      desc: 'AI rewrites your summary to lead with JD-aligned keywords and value proposition.',
      value: rewriteSummary,
      set: setRewriteSummary,
    },
    {
      key: 'bullets',
      label: 'Experience Bullet Points',
      desc: 'Rephrases bullets with stronger action verbs and ATS keywords from the JD.',
      value: rewriteBullets,
      set: setRewriteBullets,
    },
    {
      key: 'reorder',
      label: 'Section Reordering',
      desc: 'Moves most-relevant sections (e.g. Skills) to the top for this specific role.',
      value: reorderSections,
      set: setReorderSections,
    },
    {
      key: 'tone',
      label: 'Tone & Keyword Density',
      desc: 'Aligns phrasing tone with the JD (formal/startup/technical) and natural keyword weaving.',
      value: adjustTone,
      set: setAdjustTone,
    },
  ]

  const enabledCount = contentSections.filter(s => s.value).length

  return (
    <div className="max-w-3xl mx-auto px-4 pt-8 pb-32 space-y-5">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Review & Confirm</h1>
        <p className="text-slate-500 text-sm mt-1">
          Review what we found. Select exactly what you want to change — nothing runs without your approval.
        </p>
      </div>

      {/* Match Overview */}
      <div className="card p-5">
        <h2 className="section-title mb-3">Match Overview</h2>
        <div className="grid grid-cols-3 gap-3">
          <ScoreCard
            label="Match Score"
            value={`${analysis.match_score.toFixed(0)}%`}
            color={analysis.match_score >= 70 ? 'green' : analysis.match_score >= 50 ? 'yellow' : 'red'}
          />
          <ScoreCard
            label="ATS Score"
            value={`${analysis.ats_score_before.total.toFixed(0)}/100`}
            color={analysis.ats_score_before.total >= 70 ? 'green' : analysis.ats_score_before.total >= 50 ? 'yellow' : 'red'}
          />
          <ScoreCard
            label="Experience"
            value={`${analysis.experience_candidate ?? '?'} yr${(analysis.experience_candidate ?? 0) !== 1 ? 's' : ''}`}
            sub={analysis.experience_required_min ? `${analysis.experience_required_min}+ required` : undefined}
            color={(analysis.experience_candidate ?? 0) >= (analysis.experience_required_min ?? 0) ? 'green' : 'red'}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-500">
          {analysis.domain_candidate && (
            <span>Your domain: <strong className="text-slate-700">{analysis.domain_candidate}</strong></span>
          )}
          {analysis.domain_jd && (
            <span>JD domain: <strong className="text-slate-700">{analysis.domain_jd}</strong></span>
          )}
        </div>
      </div>

      {/* Flags */}
      {analysis.flags.length > 0 && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="section-title mb-0">Flags</h2>
            {unresolvedRed.length > 0 && (
              <span className="text-xs bg-red-100 text-red-700 px-2.5 py-1 rounded-full font-medium">
                {unresolvedRed.length} need acknowledgement
              </span>
            )}
          </div>
          <div className="space-y-2">
            {[...redFlags, ...yellowFlags, ...infoFlags].map((flag) => (
              <FlagCard
                key={flag.category}
                flag={flag}
                acknowledged={acknowledgedFlags.has(flag.category)}
                onAcknowledge={() => {
                  const next = new Set(acknowledgedFlags)
                  next.add(flag.category)
                  setAcknowledgedFlags(next)
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Skills Breakdown */}
      <div className="card p-5">
        <div className="mb-4">
          <h2 className="section-title mb-0">Skills Breakdown</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {analysis.skills.length === 0
              ? 'No skill data extracted — optimization will still run using JD keywords.'
              : `${matchedSkills.length} matched · ${requiredDecisionSkills.length} you can add · ${missingSkills.length} not detected in your profile`}
          </p>
        </div>

        {analysis.skills.length === 0 ? (
          <div className="text-center py-6 text-slate-400 text-sm">
            Optimization will run using JD keywords directly.
          </div>
        ) : (
          <div className="space-y-5">

            {/* Matched — green tags, no action */}
            {matchedSkills.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                  Already in your resume ({matchedSkills.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {matchedSkills.map(s => (
                    <span key={s.skill} className="text-xs px-2.5 py-1 rounded-full font-medium bg-green-100 text-green-700 border border-green-200">
                      ✓ {s.skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Can Add — required decision */}
            {canAddSkills.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-blue-500" />
                    In your profile — choose to highlight ({canAddSkills.length})
                  </p>
                  <div className="flex gap-1.5">
                    <button onClick={() => selectGroup(canAddSkills, true)} className="text-xs px-2 py-1 rounded font-medium bg-green-50 text-green-700 border border-green-200 hover:bg-green-100">Add All</button>
                    <button onClick={() => selectGroup(canAddSkills, false)} className="text-xs px-2 py-1 rounded font-medium bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100">Skip All</button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {canAddSkills.map(s => (
                    <SkillDecisionRow key={s.skill} skill={s} decision={skillDecisions[s.skill]}
                      onDecide={(add) => setSkillDecisions(prev => ({ ...prev, [s.skill]: add }))} />
                  ))}
                </div>
              </div>
            )}

            {/* Partial — required decision */}
            {partialSkills.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-yellow-500" />
                    Related skills — you have something similar ({partialSkills.length})
                  </p>
                  <div className="flex gap-1.5">
                    <button onClick={() => selectGroup(partialSkills, true)} className="text-xs px-2 py-1 rounded font-medium bg-green-50 text-green-700 border border-green-200 hover:bg-green-100">Add All</button>
                    <button onClick={() => selectGroup(partialSkills, false)} className="text-xs px-2 py-1 rounded font-medium bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100">Skip All</button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {partialSkills.map(s => (
                    <SkillDecisionRow key={s.skill} skill={s} decision={skillDecisions[s.skill]}
                      onDecide={(add) => setSkillDecisions(prev => ({ ...prev, [s.skill]: add }))} />
                  ))}
                </div>
              </div>
            )}

            {/* Missing — optional per-skill override */}
            {missingSkills.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                    Not detected in your profile ({missingSkills.length})
                  </p>
                  <div className="flex gap-1.5">
                    <button onClick={() => selectGroup(missingSkills, true)} className="text-xs px-2 py-1 rounded font-medium bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100">Override All</button>
                    <button onClick={() => selectGroup(missingSkills, false)} className="text-xs px-2 py-1 rounded font-medium bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100">Skip All</button>
                  </div>
                </div>
                <p className="text-xs text-slate-400 mb-2 italic">
                  If the AI missed a skill you genuinely have, override it — the AI will only include it where context supports it.
                </p>
                <div className="space-y-1.5">
                  {missingSkills.map(s => (
                    <SkillDecisionRow
                      key={s.skill}
                      skill={{ ...s, status: 'missing' }}
                      decision={skillDecisions[s.skill]}
                      onDecide={(add) => setSkillDecisions(prev => ({ ...prev, [s.skill]: add }))}
                      isOverride
                    />
                  ))}
                </div>
              </div>
            )}

          </div>
        )}

        {pendingSkillDecisions.length > 0 && (
          <div className="mt-4 flex items-center gap-2 p-2.5 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-700">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            {pendingSkillDecisions.length} skill{pendingSkillDecisions.length > 1 ? 's' : ''} still need a decision
          </div>
        )}
      </div>

      {/* Content Changes — per-section */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-1">
          <div>
            <h2 className="section-title mb-0">Content Changes</h2>
            <p className="text-xs text-slate-500 mt-0.5">{enabledCount} of {contentSections.length} sections selected</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => contentSections.forEach(s => s.set(true))}
              className="text-xs px-3 py-1.5 rounded-md font-medium bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100 transition-colors"
            >
              Select All
            </button>
            <button
              onClick={() => contentSections.forEach(s => s.set(false))}
              className="text-xs px-3 py-1.5 rounded-md font-medium bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100 transition-colors"
            >
              Clear All
            </button>
          </div>
        </div>

        <div className="mt-4 divide-y divide-slate-100">
          {contentSections.map((section) => (
            <div key={section.key} className="py-3 flex items-start gap-3">
              <button
                onClick={() => section.set(!section.value)}
                className={`mt-0.5 w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                  section.value
                    ? 'bg-brand-700 border-brand-700'
                    : 'bg-white border-slate-300 hover:border-brand-400'
                }`}
              >
                {section.value && <CheckCircle2 className="w-3 h-3 text-white" />}
              </button>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800">{section.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{section.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Sticky bottom action bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 shadow-lg z-50">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between gap-4">
          <div className="text-sm min-w-0">
            {!canProceed ? (
              <div className="text-slate-500 space-y-0.5">
                {unresolvedRed.length > 0 && (
                  <p className="text-red-500 font-medium">⚠ {unresolvedRed.length} flag{unresolvedRed.length > 1 ? 's' : ''} need acknowledgement</p>
                )}
                {pendingSkillDecisions.length > 0 && (
                  <p className="text-yellow-600 font-medium">⚠ {pendingSkillDecisions.length} skill decision{pendingSkillDecisions.length > 1 ? 's' : ''} pending</p>
                )}
              </div>
            ) : (
              <p className="text-green-600 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" /> Ready to optimize
              </p>
            )}
          </div>
          <button
            onClick={handleOptimize}
            disabled={!canProceed || loading}
            className="flex-shrink-0 btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Optimizing…</>
            ) : (
              <>Generate Optimized Resume <ChevronRight className="w-4 h-4" /></>
            )}
          </button>
        </div>
      </div>

    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function ScoreCard({ label, value, sub, color }: {
  label: string; value: string; sub?: string; color: 'green' | 'yellow' | 'red'
}) {
  const colors = {
    green: 'bg-green-50 text-green-700 border-green-200',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    red: 'bg-red-50 text-red-700 border-red-200',
  }
  return (
    <div className={`rounded-xl border p-4 text-center ${colors[color]}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs font-medium mt-1 opacity-80">{label}</div>
      {sub && <div className="text-xs opacity-60 mt-0.5">{sub}</div>}
    </div>
  )
}

function FlagCard({ flag, acknowledged, onAcknowledge }: {
  flag: PreflightFlag; acknowledged: boolean; onAcknowledge: () => void
}) {
  const [expanded, setExpanded] = useState(flag.flag_type === 'red')

  const icons = {
    red: <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />,
    yellow: <AlertCircle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />,
    info: <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />,
  }
  const borders = {
    red: 'border-red-200 bg-red-50',
    yellow: 'border-yellow-200 bg-yellow-50',
    info: 'border-blue-100 bg-blue-50',
  }

  return (
    <div className={`rounded-lg border p-3 ${borders[flag.flag_type]}`}>
      <div className="flex items-start gap-2">
        {icons[flag.flag_type]}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <span className="font-semibold text-sm text-slate-800">{flag.title}</span>
              <p className="text-xs text-slate-600 mt-0.5">{flag.message}</p>
            </div>
            {flag.detail && (
              <button onClick={() => setExpanded(!expanded)} className="text-slate-400 hover:text-slate-600 flex-shrink-0">
                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            )}
          </div>
          {expanded && flag.detail && (
            <p className="text-xs text-slate-500 mt-1.5 italic border-t border-slate-200 pt-1.5">{flag.detail}</p>
          )}
          {flag.requires_acknowledgement && !acknowledged && (
            <button
              onClick={onAcknowledge}
              className="mt-2 text-xs font-semibold bg-white border border-slate-300 px-3 py-1 rounded-md hover:bg-slate-50 transition-colors"
            >
              I understand — proceed anyway
            </button>
          )}
          {acknowledged && (
            <span className="mt-2 inline-flex items-center gap-1 text-xs text-green-600 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" /> Acknowledged
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function SkillDecisionRow({ skill, decision, onDecide, isOverride = false }: {
  skill: SkillItem
  decision: boolean | undefined
  onDecide: (add: boolean) => void
  isOverride?: boolean
}) {
  const statusLabel =
    isOverride ? 'Not detected by AI' :
    skill.status === 'can_add' ? 'In your profile' :
    skill.related_skill ? `You have: ${skill.related_skill}` : 'Partial match'

  const statusColor =
    isOverride ? 'text-orange-500' :
    skill.status === 'can_add' ? 'text-blue-500' : 'text-yellow-600'

  const rowBg =
    decision === true ? (isOverride ? 'bg-orange-50 border-orange-200' : 'bg-green-50 border-green-200') :
    decision === false ? 'bg-slate-50 border-slate-200' :
    'bg-white border-slate-200'

  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${rowBg}`}>
      <div className="min-w-0">
        <span className="font-medium text-sm text-slate-800">{skill.skill}</span>
        <span className={`ml-2 text-xs ${statusColor}`}>{statusLabel}</span>
      </div>
      <div className="flex gap-2 flex-shrink-0 ml-3">
        <button
          onClick={() => onDecide(true)}
          className={`text-xs px-3 py-1.5 rounded-md font-medium border transition-colors ${
            decision === true
              ? isOverride ? 'bg-orange-600 text-white border-orange-600' : 'bg-green-600 text-white border-green-600'
              : 'bg-white text-slate-600 border-slate-200 hover:border-green-400 hover:text-green-600'
          }`}
        >
          {isOverride ? 'Override' : 'Add'}
        </button>
        <button
          onClick={() => onDecide(false)}
          className={`text-xs px-3 py-1.5 rounded-md font-medium border transition-colors ${
            decision === false
              ? 'bg-slate-600 text-white border-slate-600'
              : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
          }`}
        >
          Skip
        </button>
      </div>
    </div>
  )
}
