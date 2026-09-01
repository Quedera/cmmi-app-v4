/** @type {import('tailwindcss').Config} */
const quederaPreset = require("../../branding/quedera-tailwind-preset.cjs");

module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      ...quederaPreset.theme.extend,
    },
  },
  plugins: [],
};