'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Briefcase, Layout, ChevronRight, AlertCircle, X, Eye } from 'lucide-react'
import { uploadFiles, analyzeSession } from '@/lib/api'
import type { AnalysisResult } from '@/lib/types'

// ── Template preview HTML with sample data ────────────────────────────────────

const MODERN_PREVIEW = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:Calibri,Arial,sans-serif;font-size:10.5pt;color:#2d2d2d;background:#fff}
.page{width:210mm;min-height:297mm;padding:12mm 14mm}
.header{border-bottom:3px solid #1a56db;padding-bottom:10px;margin-bottom:14px}
.name{font-size:22pt;font-weight:700;color:#1a56db}
.contact{display:flex;flex-wrap:wrap;gap:12px;margin-top:6px;font-size:9pt;color:#555}
.section{margin-bottom:14px}
.section-title{font-size:11pt;font-weight:700;color:#1a56db;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #c7d7f9;padding-bottom:3px;margin-bottom:8px}
.summary{font-size:10pt;color:#444;line-height:1.5}
.skills-grid{display:flex;flex-wrap:wrap;gap:6px}
.skill-tag{background:#eef2ff;color:#1a56db;border-radius:4px;padding:2px 9px;font-size:9pt;font-weight:600}
.exp-header{display:flex;justify-content:space-between;align-items:baseline}
.exp-title{font-size:10.5pt;font-weight:700;color:#1e293b}
.exp-company{font-size:10pt;color:#1a56db;font-weight:600}
.exp-dates{font-size:9pt;color:#666}
.bullets{margin-top:5px;padding-left:16px}
.bullets li{font-size:9.5pt;color:#444;margin-bottom:3px;line-height:1.4}
.edu-degree{font-weight:700;font-size:10pt}
.edu-inst{color:#1a56db;font-size:9.5pt}
</style></head><body><div class="page">
<div class="header"><div class="name">Alex Johnson</div>
<div class="contact"><span>✉ alex@email.com</span><span>📞 +1 (555) 000-1234</span><span>📍 San Francisco, CA</span><span>🔗 linkedin.com/in/alexjohnson</span></div></div>
<div class="section"><div class="section-title">Professional Summary</div>
<div class="summary">Senior Software Engineer with 5+ years building scalable web applications. Deep expertise in React, Node.js, and AWS cloud infrastructure. Led cross-functional teams to deliver products used by 1M+ users globally.</div></div>
<div class="section"><div class="section-title">Core Skills</div>
<div class="skills-grid"><span class="skill-tag">React</span><span class="skill-tag">Node.js</span><span class="skill-tag">TypeScript</span><span class="skill-tag">PostgreSQL</span><span class="skill-tag">AWS</span><span class="skill-tag">Docker</span><span class="skill-tag">GraphQL</span><span class="skill-tag">Kubernetes</span></div></div>
<div class="section"><div class="section-title">Professional Experience</div>
<div style="margin-bottom:12px"><div class="exp-header"><div><span class="exp-title">Senior Software Engineer</span> &nbsp;·&nbsp; <span class="exp-company">TechCorp Inc.</span></div><span class="exp-dates">Jan 2021 – Present</span></div>
<ul class="bullets"><li>Led development of microservices architecture serving 2M+ daily active users</li><li>Reduced API latency by 40% through Redis caching and query optimization</li><li>Mentored team of 4 junior engineers; conducted weekly code reviews</li></ul></div>
<div><div class="exp-header"><div><span class="exp-title">Software Engineer</span> &nbsp;·&nbsp; <span class="exp-company">StartupXYZ</span></div><span class="exp-dates">Jul 2019 – Dec 2020</span></div>
<ul class="bullets"><li>Built React dashboard used by 50,000 enterprise customers</li><li>Integrated Stripe payments and reduced checkout abandonment by 18%</li></ul></div></div>
<div class="section"><div class="section-title">Education</div>
<div><div class="edu-degree">B.S. Computer Science</div><span class="edu-inst">Stanford University</span> · Stanford, CA · 2019</div></div>
</div></body></html>`

const CLASSIC_PREVIEW = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Times New Roman',Times,serif;font-size:11pt;color:#1a1a1a;background:#fff}
.page{width:210mm;min-height:297mm;padding:15mm 18mm}
.name{font-size:20pt;font-weight:700;text-align:center;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px}
.contact{text-align:center;font-size:9.5pt;color:#444;margin-bottom:14px}
.contact span{margin:0 8px}
.divider{border:none;border-top:2px solid #1a1a1a;margin:10px 0}
.section{margin-bottom:14px}
.section-title{font-size:11pt;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #1a1a1a;padding-bottom:2px;margin-bottom:8px}
.summary{font-size:10pt;color:#333;line-height:1.6;text-align:justify}
.skills-list{font-size:10pt;color:#333;line-height:1.8}
.exp-header{display:flex;justify-content:space-between}
.exp-title{font-weight:700;font-size:11pt}
.exp-company{font-style:italic;font-size:10pt;color:#333}
.exp-dates{font-size:9.5pt;color:#555;text-align:right}
.bullets{margin-top:5px;padding-left:18px}
.bullets li{font-size:10pt;color:#333;margin-bottom:4px;line-height:1.5}
.edu-degree{font-weight:700;font-size:11pt}
.edu-inst{font-style:italic;font-size:10pt}
</style></head><body><div class="page">
<div class="name">Alex Johnson</div>
<div class="contact"><span>alex@email.com</span><span>|</span><span>+1 (555) 000-1234</span><span>|</span><span>San Francisco, CA</span><span>|</span><span>linkedin.com/in/alexjohnson</span></div>
<hr class="divider">
<div class="section"><div class="section-title">Professional Summary</div>
<div class="summary">Senior Software Engineer with 5+ years of demonstrated expertise in designing and deploying scalable web applications. Proven track record of leading cross-functional teams and delivering enterprise-grade solutions that serve millions of users.</div></div>
<div class="section"><div class="section-title">Technical Skills</div>
<div class="skills-list"><strong>Languages:</strong> TypeScript, JavaScript, Python, SQL &nbsp;|&nbsp; <strong>Frameworks:</strong> React, Node.js, GraphQL &nbsp;|&nbsp; <strong>Cloud:</strong> AWS, Docker, Kubernetes</div></div>
<div class="section"><div class="section-title">Professional Experience</div>
<div style="margin-bottom:10px"><div class="exp-header"><div><div class="exp-title">Senior Software Engineer</div><div class="exp-company">TechCorp Inc., San Francisco, CA</div></div><div class="exp-dates">January 2021 – Present</div></div>
<ul class="bullets"><li>Architected microservices platform serving 2M+ daily active users with 99.9% uptime</li><li>Reduced API response time by 40% through strategic caching and database optimization</li><li>Led and mentored a team of four engineers, improving sprint velocity by 25%</li></ul></div>
<div><div class="exp-header"><div><div class="exp-title">Software Engineer</div><div class="exp-company">StartupXYZ, New York, NY</div></div><div class="exp-dates">July 2019 – December 2020</div></div>
<ul class="bullets"><li>Developed React-based enterprise dashboard adopted by 50,000 customers</li><li>Implemented Stripe payment integration reducing checkout abandonment by 18%</li></ul></div></div>
<div class="section"><div class="section-title">Education</div>
<div><div class="edu-degree">Bachelor of Science in Computer Science</div><div class="edu-inst">Stanford University · Stanford, California · Graduated May 2019</div></div></div>
</div></body></html>`

const MINIMAL_PREVIEW = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:Helvetica,Arial,sans-serif;font-size:10pt;color:#1a1a1a;background:#fff}
.page{width:210mm;min-height:297mm;padding:14mm 16mm}
.name{font-size:20pt;font-weight:300;letter-spacing:3px;text-transform:uppercase;margin-bottom:3px}
.title-bar{font-size:10pt;color:#777;letter-spacing:1px;margin-bottom:14px;font-weight:400}
.row{display:grid;grid-template-columns:100px 1fr;gap:12px;margin-bottom:14px;align-items:start}
.label{font-size:8pt;color:#aaa;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;padding-top:2px;border-top:1px solid #eee;padding-top:6px}
.content{font-size:10pt;color:#333;line-height:1.5;border-top:1px solid #eee;padding-top:6px}
.skills-row{display:flex;flex-wrap:wrap;gap:5px}
.skill{font-size:9pt;border:1px solid #ddd;padding:2px 8px;border-radius:2px;color:#555}
.exp-entry{margin-bottom:10px}
.exp-top{display:flex;justify-content:space-between;margin-bottom:2px}
.exp-role{font-weight:600;font-size:10pt}
.exp-dates{font-size:9pt;color:#888}
.exp-company{font-size:9.5pt;color:#777;margin-bottom:4px}
.bullets{padding-left:14px}
.bullets li{font-size:9.5pt;color:#444;margin-bottom:3px;line-height:1.4}
</style></head><body><div class="page">
<div class="name">Alex Johnson</div>
<div class="title-bar">Senior Software Engineer &nbsp;·&nbsp; alex@email.com &nbsp;·&nbsp; +1 (555) 000-1234 &nbsp;·&nbsp; San Francisco, CA</div>
<div class="row"><div class="label">Profile</div>
<div class="content">Senior Software Engineer with 5+ years crafting scalable web products. Focused on clean architecture, team leadership, and measurable performance improvements.</div></div>
<div class="row"><div class="label">Skills</div>
<div class="content"><div class="skills-row"><span class="skill">React</span><span class="skill">Node.js</span><span class="skill">TypeScript</span><span class="skill">PostgreSQL</span><span class="skill">AWS</span><span class="skill">Docker</span><span class="skill">GraphQL</span></div></div></div>
<div class="row"><div class="label">Experience</div>
<div class="content">
<div class="exp-entry"><div class="exp-top"><span class="exp-role">Senior Software Engineer</span><span class="exp-dates">2021 – Present</span></div>
<div class="exp-company">TechCorp Inc. &nbsp;·&nbsp; San Francisco, CA</div>
<ul class="bullets"><li>Led microservices architecture for 2M+ daily active users</li><li>40% API latency reduction via caching &amp; DB optimization</li></ul></div>
<div class="exp-entry"><div class="exp-top"><span class="exp-role">Software Engineer</span><span class="exp-dates">2019 – 2020</span></div>
<div class="exp-company">StartupXYZ &nbsp;·&nbsp; New York, NY</div>
<ul class="bullets"><li>Built React enterprise dashboard for 50K customers</li><li>Stripe integration — 18% checkout abandonment reduction</li></ul></div></div></div>
<div class="row"><div class="label">Education</div>
<div class="content"><strong>B.S. Computer Science</strong><br>Stanford University &nbsp;·&nbsp; 2019</div></div>
</div></body></html>`

const PREBUILT_TEMPLATES = [
  {
    id: 'modern',
    name: 'Modern',
    desc: 'Blue accents, skill tags, ATS-friendly layout',
    accent: '#1a56db',
    preview: MODERN_PREVIEW,
  },
  {
    id: 'classic',
    name: 'Classic',
    desc: 'Traditional serif, formal & conservative layout',
    accent: '#1a1a1a',
    preview: CLASSIC_PREVIEW,
  },
  {
    id: 'minimal',
    name: 'Minimal',
    desc: 'Clean side-label grid, lots of whitespace',
    accent: '#888',
    preview: MINIMAL_PREVIEW,
  },
]

type TemplateMode = 'keep' | 'upload' | 'prebuilt'

type JDMode = 'file' | 'text'

export default function HomePage() {
  const router = useRouter()
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [jdFile, setJdFile] = useState<File | null>(null)
  const [jdMode, setJdMode] = useState<JDMode>('file')
  const [jdText, setJdText] = useState('')
  const [templateFile, setTemplateFile] = useState<File | null>(null)
  const [templateChoice, setTemplateChoice] = useState<string | null>(null)
  const [templateMode, setTemplateMode] = useState<TemplateMode>('keep')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<'upload' | 'analyzing'>('upload')
  const [previewTemplate, setPreviewTemplate] = useState<typeof PREBUILT_TEMPLATES[0] | null>(null)

  // When switching JD mode, clear the other input
  function switchJdMode(mode: JDMode) {
    setJdMode(mode)
    if (mode === 'file') setJdText('')
    else setJdFile(null)
  }

  // Resolve the effective JD file — either the uploaded file or a File built from pasted text
  function resolvedJdFile(): File | null {
    if (jdMode === 'file') return jdFile
    const trimmed = jdText.trim()
    if (!trimmed) return null
    return new File([trimmed], 'job_description.txt', { type: 'text/plain' })
  }

  const jdReady = jdMode === 'file' ? !!jdFile : jdText.trim().length >= 50

  const canProceed =
    resumeFile &&
    jdReady &&
    (templateMode === 'keep' ||
     (templateMode === 'upload' && !!templateFile) ||
     (templateMode === 'prebuilt' && !!templateChoice))

  async function handleStart() {
    if (!canProceed) return
    setLoading(true)
    setError(null)
    setStep('analyzing')

    try {
      const effectiveJd = resolvedJdFile()!
      const { session_id } = await uploadFiles(
        resumeFile!,
        effectiveJd,
        templateMode === 'upload' ? templateFile : null,
        templateMode === 'prebuilt' ? templateChoice : null,
      )
      const analysis: AnalysisResult = await analyzeSession(session_id)
      sessionStorage.setItem('analysis', JSON.stringify(analysis))
      sessionStorage.setItem('session_id', session_id)
      sessionStorage.setItem('template_choice', templateChoice || '')
      sessionStorage.setItem('resume_filename', resumeFile!.name)
      router.push('/review')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Upload failed. Please check your files and try again.')
      setStep('upload')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* ── Hero Banner (Dynamics Monk navy) ── */}
      <div className="bg-navy-800 relative overflow-hidden">
        {/* Subtle circuit/wave decoration */}
        <div className="absolute inset-0 opacity-10"
          style={{background: 'radial-gradient(ellipse at 70% 50%, #f05a1a 0%, transparent 60%), radial-gradient(ellipse at 20% 80%, #3b82f6 0%, transparent 50%)'}} />
        <div className="relative max-w-3xl mx-auto px-4 py-12 text-center">
          <h1 className="text-4xl font-extrabold text-white mb-3 leading-tight">
            AI Resume <span className="text-brand-400">Optimizer</span>
          </h1>
          <p className="text-navy-200 text-base max-w-xl mx-auto leading-relaxed">
            Upload your resume and a job description. Our AI rewrites your content for
            maximum ATS compatibility — without changing a single fact.
          </p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8">

      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2 mb-8 text-sm">
        {['Upload', 'Review & Confirm', 'Download'].map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
              ${i === 0 ? 'bg-brand-500 text-white' : 'bg-slate-200 text-slate-500'}`}>
              {i + 1}
            </div>
            <span className={i === 0 ? 'text-brand-500 font-semibold' : 'text-slate-400'}>{s}</span>
            {i < 2 && <ChevronRight className="w-4 h-4 text-slate-300" />}
          </div>
        ))}
      </div>

      <div className="space-y-5">

        {/* Resume Upload */}
        <FileUploadCard
          label="Your Resume"
          sublabel="PDF or DOCX"
          icon={<FileText className="w-5 h-5 text-brand-500" />}
          file={resumeFile}
          onFile={setResumeFile}
          accept={{
            'application/pdf': ['.pdf'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
          }}
        />

        {/* JD — File upload OR paste text */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-brand-500" />
              <span className="font-semibold text-slate-800">Job Description</span>
            </div>
            {/* Mode toggle */}
            <div className="flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5">
              <button
                onClick={() => switchJdMode('file')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  jdMode === 'file' ? 'bg-white text-brand-500 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Upload File
              </button>
              <button
                onClick={() => switchJdMode('text')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  jdMode === 'text' ? 'bg-white text-brand-500 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Paste Text
              </button>
            </div>
          </div>

          {jdMode === 'file' ? (
            <FileUploadCard
              label=""
              sublabel="PDF, DOCX, or .txt"
              icon={<Briefcase className="w-5 h-5 text-brand-500" />}
              file={jdFile}
              onFile={setJdFile}
              accept={{
                'application/pdf': ['.pdf'],
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
                'text/plain': ['.txt'],
              }}
              compact
            />
          ) : (
            <div>
              <textarea
                value={jdText}
                onChange={e => setJdText(e.target.value)}
                placeholder="Paste the full job description here…"
                rows={8}
                className={`w-full border-2 rounded-lg px-4 py-3 text-sm text-slate-700 placeholder-slate-400 resize-y focus:outline-none focus:border-brand-400 transition-colors ${
                  jdText.trim().length > 0 && jdText.trim().length < 50
                    ? 'border-yellow-300 bg-yellow-50'
                    : jdText.trim().length >= 50
                    ? 'border-green-400 bg-green-50'
                    : 'border-slate-200 bg-white'
                }`}
              />
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-xs text-slate-400">
                  {jdText.trim().length < 50 && jdText.trim().length > 0
                    ? `Too short — paste the full JD (${jdText.trim().length}/50 chars min)`
                    : jdText.trim().length >= 50
                    ? `✓ ${jdText.trim().length} characters`
                    : 'Minimum 50 characters'}
                </span>
                {jdText.trim().length > 0 && (
                  <button
                    onClick={() => setJdText('')}
                    className="text-xs text-slate-400 hover:text-red-500 transition-colors"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Template Section */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Layout className="w-5 h-5 text-brand-500" />
            <span className="font-semibold text-slate-800">Output Template</span>
          </div>

          {/* 3-way tab */}
          <div className="grid grid-cols-3 gap-2 mb-5 p-1 bg-slate-100 rounded-lg">
            {(
              [
                { key: 'keep', label: 'Keep My Format' },
                { key: 'upload', label: 'Upload Template' },
                { key: 'prebuilt', label: 'Pre-built' },
              ] as { key: TemplateMode; label: string }[]
            ).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => {
                  setTemplateMode(key)
                  setTemplateChoice(null)
                  setTemplateFile(null)
                }}
                className={`py-2 rounded-md text-sm font-medium transition-colors ${
                  templateMode === key
                    ? 'bg-white text-brand-500 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Keep My Format */}
          {templateMode === 'keep' && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 space-y-3">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-blue-900">Your design, our words</p>
                  <p className="text-xs text-blue-700 mt-0.5 leading-relaxed">
                    We rewrite only the text content — every font, colour, spacing, and layout
                    element in your resume stays exactly as-is.
                  </p>
                </div>
              </div>
              <div className="flex gap-4 text-xs text-blue-600 pl-11">
                <span className="flex items-center gap-1">✓ Font &amp; colours preserved</span>
                <span className="flex items-center gap-1">✓ Layout unchanged</span>
                <span className="flex items-center gap-1">✓ Spacing intact</span>
              </div>
            </div>
          )}

          {/* Upload Template */}
          {templateMode === 'upload' && (
            <div className="space-y-3">
              <p className="text-xs text-slate-500">
                Upload a DOCX file with <code className="bg-slate-100 px-1 rounded">{'{{PLACEHOLDER}}'}</code> tags.
                We'll inject your optimized content while keeping the template design.
              </p>
              <FileUploadCard
                label=""
                sublabel="DOCX only — must contain {{PLACEHOLDER}} tags"
                icon={<Upload className="w-5 h-5 text-brand-500" />}
                file={templateFile}
                onFile={setTemplateFile}
                accept={{
                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
                }}
                compact
              />
            </div>
          )}

          {/* Pre-built Templates */}
          {templateMode === 'prebuilt' && (
            <div>
              <p className="text-xs text-slate-500 mb-3">
                Click a template to preview it. Select one for your optimized resume.
              </p>
              <div className="grid grid-cols-3 gap-4">
                {PREBUILT_TEMPLATES.map((t) => (
                  <div key={t.id} className="flex flex-col">
                    {/* Thumbnail button — height is set on the inner clip-div so all
                        browsers reliably clip at exactly 180px regardless of iframe content */}
                    <button
                      onClick={() => setPreviewTemplate(t)}
                      className={`relative rounded-lg border-2 transition-all group block w-full p-0 ${
                        templateChoice === t.id
                          ? 'border-brand-500 ring-2 ring-brand-200'
                          : 'border-slate-200 hover:border-brand-300'
                      }`}
                    >
                      {/* Inner clip container — THIS is what controls the 180px height */}
                      <div style={{ height: '180px', overflow: 'hidden', position: 'relative' }}>
                        <iframe
                          srcDoc={t.preview}
                          style={{
                            display: 'block',
                            width: '794px',
                            height: '1123px',
                            transform: 'scale(0.205)',
                            transformOrigin: 'top left',
                            border: 'none',
                            pointerEvents: 'none',
                          }}
                          title={`${t.name} template preview`}
                        />
                        {/* Hover overlay */}
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                          <span className="opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 text-slate-700 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1 shadow">
                            <Eye className="w-3 h-3" /> Preview
                          </span>
                        </div>
                        {templateChoice === t.id && (
                          <div className="absolute top-2 right-2 w-5 h-5 bg-brand-500 rounded-full flex items-center justify-center">
                            <svg viewBox="0 0 12 10" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="1,5 4,8 11,1" />
                            </svg>
                          </div>
                        )}
                      </div>
                    </button>

                    {/* Name + description + select — min-height ensures all three cards
                        have the same text-area height even when descriptions wrap differently */}
                    <div className="text-center mt-2 flex flex-col" style={{ minHeight: '80px' }}>
                      <p className="text-sm font-semibold text-slate-800">{t.name}</p>
                      <p className="text-xs text-slate-400 leading-tight mt-0.5 flex-1">{t.desc}</p>
                      <button
                        onClick={() => setTemplateChoice(t.id)}
                        className={`w-full text-xs py-1.5 rounded-md font-medium border transition-colors mt-2 ${
                          templateChoice === t.id
                            ? 'bg-brand-500 text-white border-brand-500'
                            : 'bg-white text-slate-600 border-slate-200 hover:border-brand-400 hover:text-brand-500'
                        }`}
                      >
                        {templateChoice === t.id ? '✓ Selected' : 'Select'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* CTA */}
        <button
          onClick={handleStart}
          disabled={!canProceed || loading}
          className="btn-primary w-full flex items-center justify-center gap-2 text-base py-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            step === 'analyzing' ? (
              <><Spinner /> Analyzing your documents...</>
            ) : (
              <><Spinner /> Uploading...</>
            )
          ) : (
            <>Analyze & Continue <ChevronRight className="w-4 h-4" /></>
          )}
        </button>
      </div>

      {/* Template Preview Modal */}
      {previewTemplate && (
        <TemplatePreviewModal
          template={previewTemplate}
          selected={templateChoice === previewTemplate.id}
          onSelect={() => {
            setTemplateChoice(previewTemplate.id)
            setPreviewTemplate(null)
          }}
          onClose={() => setPreviewTemplate(null)}
        />
      )}
      </div>
    </div>
  )
}

// ── Template Preview Modal ─────────────────────────────────────────────────────

function TemplatePreviewModal({
  template, selected, onSelect, onClose,
}: {
  template: typeof PREBUILT_TEMPLATES[0]
  selected: boolean
  onSelect: () => void
  onClose: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col overflow-hidden"
        style={{ maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <div>
            <h2 className="text-base font-bold text-slate-900">{template.name} Template</h2>
            <p className="text-xs text-slate-500 mt-0.5">{template.desc}</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4 text-slate-600" />
          </button>
        </div>

        {/* Preview iframe */}
        <div className="flex-1 overflow-hidden relative bg-slate-100 p-4">
          <div
            className="mx-auto bg-white shadow-lg rounded overflow-hidden"
            style={{ width: '595px', height: '842px' }}
          >
            <iframe
              srcDoc={template.preview}
              style={{
                width: '794px',
                height: '1123px',
                transform: 'scale(0.75)',
                transformOrigin: 'top left',
                border: 'none',
              }}
              title={`${template.name} full preview`}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-slate-200">
          <p className="text-xs text-slate-500">
            Sample resume — your actual content will be used.
          </p>
          <button
            onClick={onSelect}
            className={`btn-primary flex items-center gap-2 ${selected ? 'opacity-60' : ''}`}
          >
            {selected ? '✓ Selected' : 'Use This Template'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── File Upload Card ───────────────────────────────────────────────────────────

function FileUploadCard({
  label, sublabel, icon, file, onFile, accept, compact = false,
}: {
  label: string
  sublabel: string
  icon: React.ReactNode
  file: File | null
  onFile: (f: File) => void
  accept: Record<string, string[]>
  compact?: boolean
}) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => { if (accepted[0]) onFile(accepted[0]) },
    accept,
    maxFiles: 1,
  })

  return (
    <div className={compact ? '' : 'card p-5'}>
      {!compact && label && (
        <div className="flex items-center gap-2 mb-3">
          {icon}
          <span className="font-semibold text-slate-800">{label}</span>
          <span className="text-xs text-slate-400 ml-1">({sublabel})</span>
        </div>
      )}

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:border-brand-400 hover:bg-slate-50'}
          ${file ? 'border-green-400 bg-green-50' : ''}`}
      >
        <input {...getInputProps()} />
        {file ? (
          <div className="flex items-center justify-center gap-2 text-green-700">
            <FileText className="w-4 h-4" />
            <span className="text-sm font-medium">{file.name}</span>
            <span className="text-xs text-green-500">({(file.size / 1024).toFixed(0)} KB)</span>
          </div>
        ) : (
          <div className="text-slate-400">
            <Upload className="w-5 h-5 mx-auto mb-1" />
            <p className="text-sm">
              {isDragActive ? 'Drop here...' : 'Drag & drop or click to upload'}
            </p>
            <p className="text-xs mt-0.5">{sublabel}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
  )
}
