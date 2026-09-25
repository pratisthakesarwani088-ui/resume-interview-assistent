/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        surface: {
          DEFAULT: "#0E1116",
          raised: "#151A21",
          border: "#232A34",
        },
        accent: {
          DEFAULT: "#5B8CFF",
          hover: "#4472F0",
          soft: "#1B2540",
        },
      },
    },
  },
  plugins: [],
};
