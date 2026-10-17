export const routeLabel = (name: string) => /^route\s/i.test(name) ? name : `Route ${name}`;
