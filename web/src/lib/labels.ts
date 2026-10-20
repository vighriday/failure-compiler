export const routeLabel = (name: string) => /^route\s/i.test(name) ? name : `Route ${name}`;
export const providerLabel = (name: string) => ({gemini: "Gemini", groq: "Groq"}[name] ?? name);
