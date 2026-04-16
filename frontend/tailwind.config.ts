import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "sans-serif"],
        mono: ["JetBrains Mono", "Monaco", "Courier", "monospace"],
      },
      colors: {
        evlos: {
          50: "#E0E4EC",
          100: "#C1C8D9",
          200: "#A2ACC6",
          300: "#8491B3",
          400: "#6575A0",
          500: "#495A82",
          600: "#3B4967",
          700: "#2D384C",
          800: "#1D283C",
          900: "#101824",
        },
        success: {
          50: "#ECFDF5", 100: "#D1FAE5", 200: "#A7F3D0", 300: "#6EE7B7",
          400: "#34D399", 500: "#10B981", 600: "#059669", 700: "#047857",
          800: "#065F46", 900: "#064E3B",
        },
        warning: {
          50: "#FFFBEB", 100: "#FEF3C7", 200: "#FDE68A", 300: "#FCD34D",
          400: "#FBBF24", 500: "#F59E0B", 600: "#D97706", 700: "#B45309",
          800: "#92400E", 900: "#78350F",
        },
        danger: {
          50: "#FEF2F2", 100: "#FEE2E2", 200: "#FECACA", 300: "#FCA5A5",
          400: "#F87171", 500: "#EF4444", 600: "#DC2626", 700: "#B91C1C",
          800: "#991B1B", 900: "#7F1D1D",
        },
      },
      borderRadius: {
        DEFAULT: "0.5rem",
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        sm: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
        md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
        lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
        xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
