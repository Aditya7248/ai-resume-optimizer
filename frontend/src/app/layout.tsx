import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'AI Resume Optimizer — Dynamics Monk',
  description: 'Tailor your resume to any job description with AI — ATS-optimized, template-preserved.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans`}>

        {/* ── Dynamics Monk Navbar ── */}
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
          <div className="max-w-7xl mx-auto px-6 py-0 flex items-center justify-start h-16">

            {/* Logo */}
            <a href="/" className="flex items-center gap-3 flex-shrink-0">
              <div className="w-10 h-10 rounded-lg bg-brand-500 flex items-center justify-center shadow-sm flex-shrink-0">
                <span className="text-white font-black text-base tracking-tight leading-none">DM</span>
              </div>
              <div className="leading-none">
                <span className="block font-black text-navy-800 text-base tracking-wider uppercase">
                  DYNAMiCS <span className="text-navy-600">MONK</span>
                </span>
                <span className="block text-[10px] font-semibold text-brand-500 tracking-widest uppercase mt-0.5">
                  AI Resume Optimizer
                </span>
              </div>
            </a>

          </div>
        </nav>

        {/* ── Page content ── */}
        <main className="min-h-screen">{children}</main>

        {/* ── Footer ── */}
        <footer className="bg-navy-800 text-white mt-16">
          <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-md bg-brand-500 flex items-center justify-center">
                <span className="text-white font-extrabold text-xs">DM</span>
              </div>
              <div>
                <span className="block font-extrabold text-xs tracking-wide uppercase">DYNAMiCS MONK</span>
                <span className="block text-navy-300 text-xs mt-0.5">AI Resume Optimizer</span>
              </div>
            </div>
            <p className="text-navy-300 text-xs text-center">
              © {new Date().getFullYear()} Dynamics Monk. All rights reserved. &nbsp;·&nbsp; Built with AI — no facts changed, ever.
            </p>
            <div className="flex gap-4 text-xs text-navy-300">
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <a href="#" className="hover:text-white transition-colors">Contact</a>
            </div>
          </div>
        </footer>

      </body>
    </html>
  )
}
