import type { ReactNode } from "react";
import LandingView from "./LandingView";
import { useLanding, type LandingProps } from "./useLanding";
import "./template-effects.css";
import "./landing.css";

export default function LandingPage(props: LandingProps & { readContent?: ReactNode; testContent?: ReactNode; error?: string }) {
  const values = useLanding(props);
  return <>
    <a className="skip-to-content" href="#landing-panel">Skip to content</a>
    <LandingView v={values} readContent={props.readContent} testContent={props.testContent} />
  </>;
}
