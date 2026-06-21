'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Download, FileText, BarChart3, CheckCircle2,
  AlertTriangle, TrendingUp, Loader2, RotateCcw, Tag, RefreshCw
} from 'lucide-react'
import { getDownloadUrl } from '@/lib/api'
import type { OptimizationResult, ATSScoreBreakdown } from '@/lib/types'

function buildDownloadName(originalFilename: string, suffix: string, ext: string): string {
  // Strip extension, sanitize, append suffix
  const base = originalFilename.replace(/\.[^/.]+$/, '')   // remove .pdf / .docx
  const safe = base.replace(/[^a-zA-Z0-9_\-. ]/g, '').replace(/\s+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  return `${safe || 'resume'}${suffix}.${ext}`
}

export default function ResultPage() {
  const router = useRouter()
  const [result, setResult] = useState<OptimizationResult | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [resumeFilename, setResumeFilename] = useState('resume')

  useEffect(() => {
    const r = sessionStorage.getItem('result')
    const s = sessionStorage.getItem('session_id')
    if (!r || !s) { router.push('/'); return }
    setResult(JSON.parse(r))
    setSessionId(s)
    setResumeFilename(sessionStorage.getItem('resume_filename') || 'resume')
  }, [])

  if (!result) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-6 h-6 animate-spin text-brand-700" />
      </div>
    )
  }

  const atsImprovement = result.ats_score_after.total - result.ats_score_before.total
  const matchImprovement = result.match_score_after - result.match_score_before

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* Success Header */}
      <div className="text-center py-6">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-8 h-8 text-green-600" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Resume Optimized!</h1>
        <p className="text-slate-500 text-sm mt-1">Your resume has been tailored and is ready to download.</p>
      </div>

      {/* Score Improvement */}
      <div className="card p-5">
        <h2 className="section-title flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-brand-700" /> Score Improvement
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <ImprovementCard
            label="ATS Compatibility"
            before={result.ats_score_before.total}
            after={result.ats_score_after.total}
            max={100}
            unit="/100"
            improvement={atsImprovement}
          />
          <ImprovementCard
            label="Match Score"
            before={result.match_score_before}
            after={result.match_score_after}
            max={100}
            unit="%"
            improvement={matchImprovement}
          />
        </div>
      </div>

      {/* ATS Breakdown */}
      <div className="card p-5">
        <h2 className="section-title flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-brand-700" /> ATS Score Breakdown
        </h2>
        <ATSBreakdownTable before={result.ats_score_before} after={result.ats_score_after} />
        <p className="text-xs text-slate-400 mt-3 italic">
          Scores based on industry-standard ATS behavior (Workday, Taleo, Greenhouse, Lever).
          Not a guarantee for any specific system.
        </p>
      </div>

      {/* What Changed */}
      <div className="grid grid-cols-2 gap-4">
        {result.skills_added.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Skills Added</h3>
            <div className="flex flex-wrap gap-1.5">
              {result.skills_added.map(s => (
                <span key={s} className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">{s}</span>
              ))}
            </div>
          </div>
        )}
        {result.sections_rewritten.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Sections Rewritten</h3>
            <div className="space-y-1">
              {result.sections_rewritten.map(s => (
                <div key={s} className="text-xs text-slate-600 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3 h-3 text-green-500" /> {s}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Keywords Injected */}
      {result.keywords_injected && result.keywords_injected.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
            <Tag className="w-3.5 h-3.5 text-brand-700" /> JD Keywords Woven In
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {result.keywords_injected.map(k => (
              <span key={k} className="text-xs bg-brand-50 text-brand-700 border border-brand-200 px-2 py-0.5 rounded-full font-medium">{k}</span>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">These JD keywords were naturally incorporated into your resume.</p>
        </div>
      )}

      {/* Known Gaps */}
      {result.known_gaps.length > 0 && (
        <div className="card p-4 border-yellow-200 bg-yellow-50">
          <h3 className="text-sm font-semibold text-yellow-800 mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" /> Known Gaps (acknowledged)
          </h3>
          <div className="space-y-1">
            {result.known_gaps.map(g => (
              <p key={g} className="text-xs text-yellow-700">{g}</p>
            ))}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {result.suggestions.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-2">Suggestions for Further Improvement</h3>
          <ul className="space-y-1.5">
            {result.suggestions.map((s, i) => (
              <li key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                <span className="text-brand-700 font-bold mt-0.5">→</span> {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Downloads */}
      <div className="card p-5">
        <h2 className="section-title flex items-center gap-2">
          <Download className="w-4 h-4 text-brand-700" /> Download Files
        </h2>
        <div className="space-y-3">
          {result.pdf_filename && (
            <DownloadButton
              label="Optimized Resume (PDF)"
              sub="Ready to send — professional layout preserved"
              url={getDownloadUrl(sessionId, 'pdf')}
              filename={buildDownloadName(resumeFilename, '_optimized', 'pdf')}
              color="green"
            />
          )}
          {result.docx_filename && !result.docx_filename.endsWith('.html') && (
            <DownloadButton
              label="Optimized Resume (DOCX)"
              sub="Word document — fully editable"
              url={getDownloadUrl(sessionId, 'docx')}
              filename={buildDownloadName(resumeFilename, '_optimized', 'docx')}
              color="brand"
            />
          )}
          {result.docx_filename && result.docx_filename.endsWith('.html') && !result.pdf_filename && (
            <a
              href={getDownloadUrl(sessionId, 'docx')}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between px-4 py-3 rounded-lg transition-colors bg-brand-700 hover:bg-brand-800 text-white"
            >
              <div>
                <div className="font-semibold text-sm">Optimized Resume (HTML)</div>
                <div className="text-xs opacity-75">Opens in browser → press Ctrl+P / ⌘+P → Save as PDF</div>
              </div>
              <Download className="w-5 h-5 flex-shrink-0" />
            </a>
          )}
          <DownloadButton
            label="Optimization Report (PDF)"
            sub="ATS scores, changes made, known gaps"
            url={getDownloadUrl(sessionId, 'report')}
            filename={buildDownloadName(resumeFilename, '_optimization_report', 'pdf')}
            color="slate"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pb-6">
        <button
          onClick={() => {
            // Keep session_id + analysis in sessionStorage, just go back to review
            sessionStorage.removeItem('result')
            router.push('/review')
          }}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" /> Re-optimize with Different Settings
        </button>
        <button
          onClick={() => {
            sessionStorage.clear()
            router.push('/')
          }}
          className="btn-secondary flex items-center gap-2 text-slate-500"
        >
          <RotateCcw className="w-4 h-4" /> Optimize Another Resume
        </button>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ImprovementCard({ label, before, after, max, unit, improvement }: {
  label: string; before: number; after: number; max: number; unit: string; improvement: number
}) {
  const afterPct = (after / max) * 100
  const beforePct = (before / max) * 100
  return (
    <div className="bg-slate-50 rounded-lg p-4">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">{label}</div>
      <div className="flex items-end gap-2 mb-3">
        <span className="text-2xl font-bold text-brand-700">{after.toFixed(0)}{unit}</span>
        <span className="text-sm text-slate-400 mb-0.5">from {before.toFixed(0)}{unit}</span>
      </div>
      {/* Progress bars */}
      <div className="space-y-1.5">
        <div>
          <div className="h-1.5 bg-slate-200 rounded-full">
            <div className="h-1.5 bg-slate-400 rounded-full" style={{ width: `${beforePct}%` }} />
          </div>
          <div className="text-xs text-slate-400 mt-0.5">Before</div>
        </div>
        <div>
          <div className="h-1.5 bg-slate-200 rounded-full">
            <div className="h-1.5 bg-brand-700 rounded-full transition-all" style={{ width: `${afterPct}%` }} />
          </div>
          <div className="text-xs text-brand-700 mt-0.5 font-medium">After (+{improvement.toFixed(0)})</div>
        </div>
      </div>
    </div>
  )
}

function ATSBreakdownTable({ before, after }: { before: ATSScoreBreakdown; after: ATSScoreBreakdown }) {
  const rows = [
    { label: 'Keyword Match', max: 30, b: before.keyword_match, a: after.keyword_match },
    { label: 'Section Completeness', max: 20, b: before.section_completeness, a: after.section_completeness },
    { label: 'Format Parsability', max: 20, b: before.format_parsability, a: after.format_parsability },
    { label: 'Keyword Placement', max: 15, b: before.keyword_placement, a: after.keyword_placement },
    { label: 'Date Consistency', max: 10, b: before.date_consistency, a: after.date_consistency },
    { label: 'File Health', max: 5, b: before.file_health, a: after.file_health },
  ]
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-100 text-xs text-slate-500 uppercase tracking-wide">
            <th className="text-left py-2 px-3 font-semibold">Signal</th>
            <th className="text-center py-2 px-3 font-semibold">Max</th>
            <th className="text-center py-2 px-3 font-semibold">Before</th>
            <th className="text-center py-2 px-3 font-semibold">After</th>
            <th className="text-center py-2 px-3 font-semibold">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.label} className="border-b border-slate-100">
              <td className="py-2 px-3 text-slate-700">{row.label}</td>
              <td className="py-2 px-3 text-center text-slate-400">{row.max}</td>
              <td className="py-2 px-3 text-center text-slate-600">{row.b.toFixed(0)}</td>
              <td className="py-2 px-3 text-center font-semibold text-brand-700">{row.a.toFixed(0)}</td>
              <td className={`py-2 px-3 text-center text-xs font-bold
                ${row.a - row.b > 0 ? 'text-green-600' : row.a - row.b < 0 ? 'text-red-500' : 'text-slate-400'}`}>
                {row.a - row.b > 0 ? '+' : ''}{(row.a - row.b).toFixed(0)}
              </td>
            </tr>
          ))}
          <tr className="bg-brand-50 font-bold">
            <td className="py-2 px-3 text-brand-800">Total</td>
            <td className="py-2 px-3 text-center text-brand-800">100</td>
            <td className="py-2 px-3 text-center text-slate-600">{before.total.toFixed(0)}</td>
            <td className="py-2 px-3 text-center text-brand-700">{after.total.toFixed(0)}</td>
            <td className="py-2 px-3 text-center text-green-600">+{(after.total - before.total).toFixed(0)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function DownloadButton({ label, sub, url, filename, color }: {
  label: string; sub: string; url: string; filename: string; color: 'brand' | 'green' | 'slate'
}) {
  const colors = {
    brand: 'bg-brand-700 hover:bg-brand-800 text-white',
    green: 'bg-green-600 hover:bg-green-700 text-white',
    slate: 'bg-slate-700 hover:bg-slate-800 text-white',
  }
  return (
    <a
      href={url}
      download={filename}
      className={`flex items-center justify-between px-4 py-3 rounded-lg transition-colors ${colors[color]}`}
    >
      <div>
        <div className="font-semibold text-sm">{label}</div>
        <div className="text-xs opacity-75">{sub}</div>
      </div>
      <Download className="w-5 h-5 flex-shrink-0" />
    </a>
  )
}
