import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
          950: "#1e1b4b",
        },
      },
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["DM Mono", "monospace"],
      },
      backgroundImage: {
        "mesh-gradient":
          "radial-gradient(at 40% 20%, hsla(249,100%,64%,0.4) 0px, transparent 50%), radial-gradient(at 80% 0%, hsla(265,100%,60%,0.3) 0px, transparent 50%), radial-gradient(at 0% 50%, hsla(230,100%,60%,0.2) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
};

export default config;
