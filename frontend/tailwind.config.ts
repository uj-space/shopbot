import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        emeraldBrand: "#065f46",
        ivoryBg: "#fafaf7",
      },
    },
  },
  plugins: [],
};

export default config;
