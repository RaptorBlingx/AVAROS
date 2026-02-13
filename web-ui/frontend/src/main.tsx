import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { ThemeProvider } from "./components/common/ThemeProvider";
import { HiveMindProvider } from "./contexts/HiveMindContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <ThemeProvider>
    <HiveMindProvider>
      <App />
    </HiveMindProvider>
  </ThemeProvider>,
);
