# Cover artwork prompts

Tool: built-in `image_gen`.

These two files are cover artwork. Website screenshots are captured separately and preserve the real interface and placeholder notices.

## thumbnail.png

```text
Use case: ads-marketing
Asset type: 16:9 landscape project thumbnail for Failure Compiler, preferably 1536 x 864 or larger in the same ratio.
Primary request: Create polished cover artwork for the real project, matching the attached app reference. This is editorial cover art, not a simulated product screenshot.
Input image 1: style reference only, a real screenshot of our app. Match its warm paper palette, IBM Plex style typography, precise pen-stroke marks, fine rules, restrained layout and generous whitespace.
Composition: Large left-aligned title in the left half; a beautiful triangular matrix illustration in the right half. Keep wide safe margins and excellent legibility when reduced to a small thumbnail. No navigation bars, no browser chrome. Background flat warm off-white #F6F4EE, warm sheet #FBFAF6, ink #1A1916, green #1E6B47, red #B23A2E, rules #DAD6CB.
Text, verbatim and no other text:
"Failure"
"Compiler"
"Crash-test a plan"
"before Saturday does."
"100 scenarios"
"3 hidden pairs"
Typography: Large strong clean IBM Plex Sans-like title, small IBM Plex Mono-like numbers. Near-black main title. The two-line tagline beneath it should be readable, calm and direct. Place the two small metadata labels along a thin bottom rule.
Illustration: A precise, minimal triangular matrix of small pale paper cells, green check marks, one red diagonal cross and three circled red off-diagonal crosses. Use gray dash marks to suggest dimmed cells. This matrix is a graphic motif, not a labeled screen or a claim of exact rendered cell count. A restrained fine brick-red pen underline can connect the title to a highlighted circled cross.
Finish: Print-quality crisp graphic design, flat frontal composition, subtle near-invisible paper grain, understated and distinctive, consistent with a volunteer coordinator's run sheet.
Avoid: gradients, glows, stock laptop mockups, robots, extra slogans, badges, awards, AI/provider claims, photoreal props, people, icons unrelated to scheduling, fake UI, tiny gibberish labels, watermarks.
```

## cover-square.png

```text
Use case: ads-marketing
Asset type: square project cover, 1:1 aspect ratio, for the Failure Compiler submission gallery and social sharing.
Primary request: Create a square companion to the supplied landscape cover. Use the same warm-paper editorial identity and the same restrained typographic voice. Recompose it properly for a square rather than squeezing or cropping it.
Input image 1: style reference, the approved landscape artwork from this set.
Layout: generous safe margins. In the upper portion, a very large two-line title. A thin brick-red hand-drawn underline under "Compiler". In the lower portion, a simple triangular matrix of green checks with three circled off-diagonal red crosses and one ordinary diagonal red cross. The matrix is illustrative cover artwork, never a screenshot. Keep enough clean space for the short tagline and small footer.
Exact text, verbatim, no extra text:
"Failure"
"Compiler"
"Crash-test a plan before Saturday does."
"100 scenarios"
"3 hidden pairs"
Use IBM Plex Sans-like typography for the title and tagline; IBM Plex Mono-like typography for the footer labels. The tagline may wrap across two readable lines.
Palette: #F6F4EE warm paper, #FBFAF6 sheet, #1A1916 ink, #1E6B47 green, #B23A2E red, #DAD6CB fine rules. Use subtle near-invisible paper grain.
Keep the title strong and legible at small square thumbnail sizes. Minimal, crisp, calm graphic design. All lettering must be correct, especially "Compiler" and "scenarios".
Avoid: photographic objects, 3D, gradients, shadows, glows, robots, awards, invented features, fake product windows, tiny labels, watermarks, provider names or additional copy.
```

## Card crop revision

Tool: built-in `image_gen`, editing the original saved covers. Only composition scale and surrounding paper margins were requested to change.

### thumbnail.png revision

```text
Edit target: the supplied Failure Compiler landscape thumbnail.
Change only the scale and canvas framing so it fits a tightly cropped project card. Preserve the title, tagline, colors, matrix illustration and exact wording from the original. Do not redesign or add anything.
Output a landscape 3:2 image, approximately 1200 x 800 pixels. Uniformly SHRINK the ENTIRE existing composition to about 68% of the canvas width, including its footer, then center it both horizontally and vertically. Extend the warm off-white paper background around it. Leave very generous EMPTY paper padding: at least 16% of canvas width on the left and right, and at least 20% of canvas height above and below the entire artwork. There must be no title, caption, footer number or matrix cell near an outside edge.
All important content should fit inside the central 68% width and 60% height. This must survive centered 3:2, 16:9 and square card crops without cutting off Failure, Compiler or the footer.
Keep these exact original words:
"Failure"
"Compiler"
"Crash-test a plan"
"before Saturday does."
"100 scenarios"
"3 hidden pairs"
Keep a clear readable hierarchy, but the artwork and typography should be visibly smaller than in the supplied original. Flat warm paper, near-black ink, deep green checks, brick-red crosses and underline. No frame, no browser UI, no extra labels, no new graphics, no watermark.
```

### cover-square.png revision

```text
Edit target: the supplied Failure Compiler square cover. Use case: precise-object-edit.
Change ONLY the scale and framing so every element survives a tightly cropped project card. Preserve all original title letters, tagline, colors, triangular grid and footer wording. Do not redesign or add anything.
Output a SQUARE 1:1 image, approximately 1024 x 1024. Uniformly shrink the ENTIRE existing composition, including title, tagline, matrix and footer, until the full artwork occupies no more than the CENTRAL 54% OF THE CANVAS HEIGHT. Center this shrunken artwork horizontally and vertically. Extend the same warm off-white paper background around it. Leave at least 23% of canvas height completely empty at BOTH top and bottom. Leave generous blank sides too. This substantial empty padding is intentional and required: the square will be center-cropped to a landscape 3:2 or 16:9 card. Nothing may get cut off in that crop.
Keep exact original words:
"Failure"
"Compiler"
"Crash-test a plan"
"before Saturday does."
"100 scenarios"
"3 hidden pairs"
Preserve the original stacked title above the grid, green checks, red crosses, fine underline and thin footer rule, with the whole poster clearly smaller and surrounded by blank paper. All typography and footer labels inside the central safe area. No border, extra text, browser UI, watermark or added graphics.
```
