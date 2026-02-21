/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        // KodBro logo palette: cyan-blue → indigo → purple
        cyan: '#00BFFF',
        blue: '#0095E0',
        indigo: '#6366F1',
        violet: '#7C3AED',
        purple: '#8B5CF6',
        slate: '#1E293B',
        cream: '#F8FAFC',
        steel: '#64748B',
        navy: '#1E293B', // alias for slate (dark text)
        red: '#EF4444',  // for terminal close dot, errors
      },
    },
  },
  plugins: [],
};
