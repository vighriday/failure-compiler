import type { ReactNode } from "react";
import LandingView from "./LandingView";
import { useLanding, type LandingProps } from "./useLanding";
import "./template-effects.css";
import "./landing.css";

export default function LandingPage(props: LandingProps & { readContent?: ReactNode; testContent?: ReactNode; error?: string }) {
  const values = useLanding(props);
  return <>
    <a className="skip-to-content" href="#landing-panel" onClick={(event) => {
      event.preventDefault();
      const panel = document.getElementById("landing-panel");
      panel?.focus({ preventScroll: true });
      panel?.scrollIntoView({ block: "start", behavior: "instant" });
    }}>Skip to content</a>
    <LandingView v={values} readContent={props.readContent} testContent={props.testContent} />
  </>;
}
