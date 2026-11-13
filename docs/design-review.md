# Design review v1 — awaiting approval

Three high-fidelity browser-renderable pages: `/design/#explorer`, `/design/#deals`, `/design/#admin` on the localhost development server (port 18780). All data and service states are explicitly illustrative. These are review mockups, not completed website features. No authenticated or live operational claims should be inferred.

Palette: espresso background, walnut navigation, chestnut panels, aged bronze frames, antique gold actions, warm ivory text. Serif headings, restrained density, readable explanations of freshness, asking prices, uncertainty and reference values.

2026-11-13: Chromium 1.56.1 Playwright image rendered all three at 1440×1100 and 390×844. Six screenshots generated under ignored artifacts/design. Navigation and invitation/filter explanation dialogs verified; no browser errors or document horizontal overflow. Reproduce with scripts/verify-design.cjs in matching Playwright container on the project network. Developer visually inspected all three desktop renders. Explicit approval requested asynchronously; pending. Final player-facing design is gated on this approval, while backend and desktop infrastructure continue.
