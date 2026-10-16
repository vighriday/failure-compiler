# Landing v2

`Landing.html` and `Grid.html` preserve the supplied v2 design reference. They are source templates, not pages served by the app. The older landing version, editor runtime and reference screenshots are not production dependencies.

Run `node scripts/convert_landing.mjs` to regenerate `LandingView.tsx`, `SampleGridView.tsx` and their hover/focus styles. The converter uses htmlparser2 to preserve markup, inline styles, loops, conditions and event bindings as native React. Interaction logic lives in `web/src/landing/useLanding.ts` and `SampleGrid.tsx`.

GSAP, its React hook and ScrollTrigger manage animation, scroll progress and cleanup. Responsive and accessibility additions live in `web/src/landing/landing.css`. Fonts are self-hosted with the existing Fontsource packages.

The landing illustrations are labelled example previews. The confirmed-map workflow continues to use the Python validation gate, live SSE checker, and scored fixes.
