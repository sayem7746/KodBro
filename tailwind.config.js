/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      colors: {
        // Palette from design: warm reds, cream, navy, steel blue
        maroon: '#702827',
        red: '#D43B35',
        coral: '#EE665E',
        cream: '#FDF6EE',
        navy: '#2E4456',
        steel: '#517897',
        sky: '#97BBD6',
      },
    },
  },
  plugins: [],
};
