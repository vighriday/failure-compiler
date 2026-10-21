/** Convert the supplied design templates to checked-in React, without a runtime HTML interpreter. */
import { parseDocument } from "htmlparser2";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const source = path.join(root, "design", "landing-v2");
const out = path.join(root, "web", "src", "landing");
mkdirSync(out, { recursive: true });
const css = [];
const mappings = { class: "className", for: "htmlFor", tabindex: "tabIndex", inputmode: "inputMode", spellcheck: "spellCheck", autocomplete: "autoComplete", "stroke-width": "strokeWidth", "stroke-linecap": "strokeLinecap", "stroke-linejoin": "strokeLinejoin", "fill-rule": "fillRule", "clip-rule": "clipRule" };
const voids = new Set(["input", "br", "hr", "img", "meta", "link"]);
const expr = (value, locals) => /^(true|false|null|\d+)$/.test(value) || locals.has(value.split(".")[0]) ? value : `v.${value}`;
function value(text, locals) {
  const exact = /^\{\{([^{}]+)\}\}$/.exec(text);
  if (exact) return expr(exact[1], locals);
  if (!text.includes("{{")) return JSON.stringify(text);
  return "`" + text.replace(/[`\\$]/g, "\\$&").replace(/\{\{(.+?)\}\}/g, (_, key) => "${" + expr(key, locals) + "}") + "`";
}
function render(node, locals = new Set()) {
  if (node.type === "text") {
    const text = node.data
      .replace("Suggested by AI, tested by the checker.", "Hand-written example suggestion. This preview does not run the checker.")
      .replace("This is a sample reading we wrote for the example. With your own key, AI writes it.", "Hand-written design preview. Start the example to review its facts and run the live checker.")
      .replace("Free to try. No sign-up, no AI key, and we never store your plan.", "No sign-up. The example needs no AI key. No plan is saved to disk.")
      .replace("We never store your plan. Close the tab and it’s gone.", "Plans stay in memory for this local session. Nothing is saved to disk.")
      .replace("Your plan goes to the AI company only to be read.", "Live reading sends your plan to the selected AI provider. The example works without a key.")
      .replace("12:00 noon", "Noon: families waiting.");
    return text.trim() ? `{${value(text, locals)}}` : "\n";
  }
  if (node.type !== "tag") return "";
  const a = node.attribs;
  const kids = (scope = locals) => node.children.map(child => render(child, scope)).join("");
  if (node.name === "helmet") return "";
  if (node.name === "sc-for") {
    const next = new Set([...locals, a.as]);
    return `{${value(a.list, locals)}.map((${a.as}, index) => <Fragment key={index}>${kids(next)}</Fragment>)}`;
  }
  if (node.name === "sc-if") {
    let content = `<>${kids()}</>`;
    const notice = '<div className="sample-notice"><span>Interactive design preview of the locked example. No live checker is running here.</span><button type="button" onClick={v.tryExample}>Start the live example →</button></div>';
    if (a.value === "{{tab_read}}") content = `(readContent ?? <>${notice}${content}</>)`;
    if (a.value === "{{tab_test}}") content = `(testContent ?? <>${notice}${content}</>)`;
    return `{${value(a.value, locals)} && ${content}}`;
  }
  const minutePicker = node.name === "input" && a["aria-label"] === "Minutes";
  const tag = node.name === "dc-import" ? "SampleGrid" : minutePicker ? "select" : node.name;
  const attrs = [];
  const classes = [];
  if (node.parent?.name === "x-dc" && tag === "div") classes.push("landing-root");
  for (const [key, text] of Object.entries(a)) {
    if (key.startsWith("hint-") || key === "name" && tag === "SampleGrid") continue;
    if (key === "class") { classes.push(text); continue; }
    if (key === "style") {
      const declarations = text.split(/;(?![^()]*\))/).filter(Boolean).map(part => {
        const colon = part.indexOf(":");
        const property = part.slice(0, colon).trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        return `${JSON.stringify(property)}: ${value(part.slice(colon + 1).trim(), locals)}`;
      });
      attrs.push(`style={{${declarations.join(", ")}} as CSSProperties}`);
    } else if (key.startsWith("style-")) {
      const name = `landing-effect-${css.length}`;
      const pseudo = key.slice(6) === "focus" ? "focus-visible" : key.slice(6);
      classes.push(name);
      css.push(`.${name}:${pseudo} { ${text.split(";").map(p => p + " !important").join(";")} }`);
    } else if (key === "aria-disabled") attrs.push(`aria-disabled={${value(text, locals)} === "true"}`);
    else if (key === "tabindex") attrs.push(`tabIndex={${Number(text)}}`);
    else attrs.push(`${mappings[key] ?? key}={${value(text, locals)}}`);
  }
  if (a.role === "button") attrs.push('onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.currentTarget.click(); } }}');
  if (a.role === "button") attrs.push('data-sample-state={c.type} data-sample-row={c.r} data-sample-column={c.c}');
  if (a.role === "tab") {
    attrs.push('tabIndex={t.sel === "true" ? 0 : -1} aria-controls="landing-panel"');
  }
  if (a.role === "tablist") attrs.push('aria-label="Explore Failure Compiler" onKeyDown={v.onNavKeyDown}');
  if (a.onMouseEnter && !a.onFocus) attrs.push(`onFocus={${value(a.onMouseEnter, locals)}}`);
  if (a.onMouseLeave && !a.onBlur) attrs.push(`onBlur={${value(a.onMouseLeave, locals)}}`);
  if (a.onMouseEnter && !a.role && tag === "div") attrs.push('tabIndex={0}');
  if (tag === "button") attrs.push('type="button"');
  if (a["aria-disabled"]) attrs.push(`disabled={${value(a["aria-disabled"], locals)} === "true"}`);
  if (a.ref === "{{tabRef}}") attrs.push('id="landing-panel" role="tabpanel" tabIndex={-1}');
  if (tag === "textarea") attrs.push('data-plan-editor="true"');
  if (tag === "input" && a.type === "password") attrs.push('value={v.apiKey} onChange={v.onKey} autoComplete="off"');
  if (a.onClick === "{{toggleKey}}") attrs.push('aria-expanded={v.keyOpen} aria-controls="landing-key"');
  if (a.onClick === "{{goTop}}") attrs.push('aria-label="Failure Compiler home"');
  if (tag === "input" && a.type === "password") attrs.push('id="landing-key"');
  if (a["data-header"]) attrs.push('aria-label="Site header"');
  if (tag === "svg" && !a["aria-label"]) attrs.push('aria-hidden="true"');
  if (tag === "span" && node.children.length === 1 && node.children[0].type === "text" && /^[→↓›]$/.test(node.children[0].data.trim())) attrs.push('aria-hidden="true"');
  if (classes.length) attrs.push(`className=${JSON.stringify(classes.join(" "))}`);
  let content = minutePicker ? '<option value="45">45 minutes</option><option value="60">60 minutes</option><option value="90">90 minutes</option>' : kids();
  if (a["data-screen-label"] === "05 Start") content += '{v.error && <p className="landing-error" role="alert">{v.error}</p>}{v.text.length > 4000 && <p className="landing-error" role="alert">Your plan has {v.charText} characters. Keep it under 4,000 before reading.</p>}';
  return `<${tag} ${attrs.join(" ")}${voids.has(tag) ? " />" : `>${content}</${tag}>`}`;
}
for (const [file, component, type] of [["Landing.html", "LandingView", "LandingValues"], ["Grid.html", "SampleGridView", "SampleGridValues"]]) {
  const doc = parseDocument(readFileSync(path.join(source, file), "utf8"), { xmlMode: true, decodeEntities: true });
  const find = (nodes) => nodes.flatMap(n => n.name === "x-dc" ? [n] : n.children ? find(n.children) : []);
  const template = find(doc.children)[0];
  if (!template) throw new Error(`Missing template in ${file}`);
  const imports = component === "LandingView" ? 'import SampleGrid from "./SampleGrid";\nimport type { LandingValues } from "./useLanding";\n' : 'import type { SampleGridValues } from "./SampleGrid";\n';
  const slots = component === "LandingView" ? ", readContent, testContent" : "";
  const props = component === "LandingView" ? "; readContent?: ReactNode; testContent?: ReactNode" : "";
  const generated = `// Generated by scripts/convert_landing.mjs from the supplied v2 design.\nimport { Fragment, type CSSProperties${component === "LandingView" ? ", type ReactNode" : ""} } from "react";\n${imports}\nexport default function ${component}({ v${slots} }: { v: ${type}${props} }) {\n  return <>${template.children.map(n => render(n)).join("")}</>;\n}\n`;
  const accessible = generated.replaceAll('#77736A', '#57544C')
    .replace('{"Failure"}<span', '{"Failure "}<span')
    .replace('aria-label={"Break the page"}', 'aria-label={"Break the page: breaks. ← click"}')
    .replace('aria-label={"Run the crash test again"}', 'aria-label={"Rerun the crash test"}')
    .replace('as CSSProperties}>{"← click"}', 'as CSSProperties} aria-hidden="true">{"← click"}');
  writeFileSync(path.join(out, `${component}.tsx`), accessible);
}
writeFileSync(path.join(out, "template-effects.css"), "/* Hover, active and focus states carried over from the supplied v2 design. */\n" + css.join("\n") + "\n");
console.log("Converted both templates and their interaction styles to native React.");
