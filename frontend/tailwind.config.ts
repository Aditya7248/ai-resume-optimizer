import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dynamics Monk brand palette
        brand: {
          50:  '#fff4ee',
          100: '#ffe6d5',
          200: '#ffc9a8',
          300: '#ffa270',
          400: '#ff7038',
          500: '#f05a1a',   // primary orange
          600: '#e04510',
          700: '#c73a0e',   // hover orange
          800: '#a42f0c',
          900: '#85260a',
        },
        navy: {
          50:  '#eef1f8',
          100: '#d5ddf0',
          200: '#b0bee4',
          300: '#7e96d0',
          400: '#516cb8',
          500: '#2f4d9e',
          600: '#233b82',
          700: '#1c2f68',
          800: '#162349',   // main nav/footer navy
          900: '#0f1830',   // darkest
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
export default config
