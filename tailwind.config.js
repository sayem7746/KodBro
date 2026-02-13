/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        // Palette from design: warm reds, cream, navy, steel blue
        maroon: '#7F2220',
        red: '#D13E3B',
        cream: '#F8F2E4',
        navy: '#22374F',
        steel: '#85A9CB',
      },
    },
  },
  plugins: [],
};
