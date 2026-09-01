/* QUEDERA Brand Design Tokens — Tailwind preset
 * --------------------------------------------------------------
 * Companion to branding/quedera-tokens.css and
 * branding/quedera-palette.json. Any QUEDERA product scaffold
 * (Sentinel, Pulse, Duet, Atlas, Beacon) should spread this
 * into its tailwind.config:
 *
 *   const quedera = require("../branding/quedera-tailwind-preset.cjs");
 *   module.exports = { theme: { extend: { ...quedera.theme.extend } } };
 *
 * Tokens use `rgb(<channels> / <alpha-value>)` so Tailwind's
 * opacity modifiers compose natively (e.g. `bg-quedera-emerald/10`).
 *
 * RULE: palette codes only. No off-palette colours anywhere in
 * QUEDERA work. — MacWood, 2026-08-26 21:10 BST.
 * -------------------------------------------------------------- */

module.exports = {
  theme: {
    extend: {
      colors: {
        quedera: {
          navy: "rgb(13 24 42 / <alpha-value>)",
          "deep-blue": "rgb(30 58 138 / <alpha-value>)",
          cyan: "rgb(6 182 212 / <alpha-value>)",
          violet: "rgb(124 58 237 / <alpha-value>)",
          amber: "rgb(245 158 11 / <alpha-value>)",
          emerald: "rgb(16 185 129 / <alpha-value>)",
          surface: "rgb(242 244 247 / <alpha-value>)",
        },
      },
    },
  },
};
