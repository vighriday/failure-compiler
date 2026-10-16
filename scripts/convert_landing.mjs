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
  if (node.type === "text") return node.data.trim() ? `{${value(node.data, locals)}}` : "\n";
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
    if (a.value === "{{tab_read}}") content = `(readContent ?? ${content})`;
    if (a.value === "{{tab_test}}") content = `(testContent ?? ${content})`;
    return `{${value(a.value, locals)} && ${content}}`;
  }
  const tag = node.name === "dc-import" ? "SampleGrid" : node.name;
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
  if (a.role === "tab") {
    attrs.push('tabIndex={t.sel === "true" ? 0 : -1} aria-controls="landing-panel"');
  }
  if (a.role === "tablist") attrs.push('aria-label="Explore Failure Compiler" onKeyDown={v.onNavKeyDown}');
  if (tag === "button") attrs.push('type="button"');
  if (a["aria-disabled"]) attrs.push(`disabled={${value(a["aria-disabled"], locals)} === "true"}`);
  if (a.ref === "{{tabRef}}") attrs.push('id="landing-panel" role="tabpanel" tabIndex={-1}');
  if (tag === "textarea") attrs.push('data-plan-editor="true"');
  if (tag === "input" && a.type === "password") attrs.push('value={v.apiKey} onChange={v.onKey} autoComplete="off"');
  if (classes.length) attrs.push(`className=${JSON.stringify(classes.join(" "))}`);
  return `<${tag} ${attrs.join(" ")}${voids.has(tag) ? " />" : `>${kids()}</${tag}>`}`;
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
  writeFileSync(path.join(out, `${component}.tsx`), generated);
}
writeFileSync(path.join(out, "template-effects.css"), "/* Hover, active and focus states carried over from the supplied v2 design. */\n" + css.join("\n") + "\n");
console.log("Converted both templates and their interaction styles to native React.");
