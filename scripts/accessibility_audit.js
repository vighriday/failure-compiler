async () => {
  const result = await axe.run(document, {runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}});
  const rgb = value => { const numbers = value.match(/[\d.]+/g)?.map(Number) ?? [0, 0, 0, 0]; return [...numbers.slice(0, 3), numbers[3] ?? 1]; };
  const blend = (fg, bg, alpha = fg[3]) => fg.slice(0, 3).map((n, i) => n * alpha + bg[i] * (1 - alpha));
  const lum = color => color.map(n => n / 255).map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0);
  const manual = [], small = [];
  let minimum = 100, count = 0;
  const inspect = (element, text, box) => {
    if (!box.width || !box.height || !text.trim()) return;
    const style = getComputedStyle(element), ancestors = [];
    let opacity = 1;
    for (let item = element; item; item = item.parentElement) {
      const current = getComputedStyle(item);
      if (current.display === "none" || current.visibility === "hidden") return;
      opacity *= Number(current.opacity);
      ancestors.push(current);
    }
    if (opacity < .01) return;
    if (parseFloat(style.fontSize) < 12) small.push({text: text.slice(0, 80), size: style.fontSize});
    let background = [255, 255, 255];
    for (const current of ancestors.reverse()) background = blend(rgb(current.backgroundColor), background);
    if (element instanceof SVGElement) {
      // SVG text can sit on a painted sibling rectangle rather than a CSS background.
      const x = box.left + box.width / 2, y = box.top + box.height / 2;
      for (const rect of element.closest("svg").querySelectorAll("rect")) {
        const bounds = rect.getBoundingClientRect();
        if ((rect.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING) && x >= bounds.left && x <= bounds.right && y >= bounds.top && y <= bounds.bottom)
          background = blend(rgb(getComputedStyle(rect).fill), background);
      }
    }
    const color = rgb(element instanceof SVGElement ? style.fill === "none" ? style.color : style.fill : style.color);
    const foreground = blend(color, background, color[3] * opacity);
    const values = [lum(foreground), lum(background)].sort((a, b) => b - a);
    const ratio = (values[0] + .05) / (values[1] + .05);
    minimum = Math.min(minimum, ratio); count++;
    if (ratio < 4.5) manual.push({text: text.trim().slice(0, 100), ratio, color: style.color, background, html: element.outerHTML.slice(0, 200)});
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim() || node.parentElement.closest("script, style")) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    inspect(node.parentElement, node.textContent, range.getBoundingClientRect());
  }
  document.querySelectorAll("input, textarea, select").forEach(element => inspect(element, element instanceof HTMLSelectElement ? element.selectedOptions[0]?.text ?? "" : element.value || element.placeholder, element.getBoundingClientRect()));
  return {
    violations: result.violations.map(v => ({id: v.id, nodes: v.nodes.map(n => ({html: n.html.slice(0, 300), reason: n.failureSummary}))})),
    incomplete: result.incomplete.map(v => ({id: v.id, nodes: v.nodes.map(n => ({html: n.html.slice(0, 300), reason: n.failureSummary}))})),
    small, manual_contrast: {count, minimum, failures: manual}
  };
}
