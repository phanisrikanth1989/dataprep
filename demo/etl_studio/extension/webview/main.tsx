// ETL Studio webview entry (ticket 15). Fonts bundle locally via
// @fontsource -- no CDN inside the webview (the CSP enforces it).

import "@fontsource/archivo/latin-500.css";
import "@fontsource/archivo/latin-600.css";
import "@fontsource/archivo/latin-700.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@fontsource/ibm-plex-mono/latin-600.css";
import "./styles.css";

import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<App />);
}
