import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/300.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import App from "./App";
import { resetDemo } from "./api/client";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root")!);
if (window.location.pathname === "/demo") {
  const start = () => {
    root.render(<main className="report-screen"><p role="status">Preparing a clean start…</p></main>);
    resetDemo().then(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
      window.location.replace("/");
    }).catch(() => root.render(<main className="report-screen"><p role="alert">Could not reset the session. Check that the server is running.</p><button className="button button-primary" type="button" onClick={start}>Try again</button></main>));
  };
  start();
} else {
  root.render(<React.StrictMode><App /></React.StrictMode>);
}
