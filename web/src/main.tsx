import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import {
  createDarkTheme,
  createLightTheme,
  FluentProvider,
  type BrandVariants,
} from "@fluentui/react-components";

import { App, ConfigurationRequired } from "./App";
import { createMsalClient } from "./auth";
import { readRuntimeConfig } from "./config";
import "./styles.css";

const freshSenseBrand: BrandVariants = {
  10: "#071508",
  20: "#102814",
  30: "#173A1F",
  40: "#1C4D28",
  50: "#216132",
  60: "#26753D",
  70: "#2C8948",
  80: "#359D55",
  90: "#4BAC68",
  100: "#66BA7C",
  110: "#7FC790",
  120: "#98D3A4",
  130: "#B0DFB8",
  140: "#C8EACC",
  150: "#E0F4E1",
  160: "#F1FAF1",
};

const lightTheme = createLightTheme(freshSenseBrand);
const darkTheme = createDarkTheme(freshSenseBrand);

function useDarkMode() {
  const [isDark, setIsDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setIsDark(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return isDark;
}

function Root() {
  const isDark = useDarkMode();
  const runtime = useMemo(() => readRuntimeConfig(), []);
  const [client, setClient] = useState<ReturnType<typeof createMsalClient> | null>(
    null,
  );
  const [startupError, setStartupError] = useState<string | null>(null);

  useEffect(() => {
    if (!runtime.config) return;
    const msal = createMsalClient(runtime.config);
    msal
      .initialize()
      .then(() => setClient(msal))
      .catch(() => setStartupError("Microsoft sign-in could not be initialized."));
  }, [runtime.config]);

  return (
    <FluentProvider theme={isDark ? darkTheme : lightTheme} className="provider">
      {!runtime.config ? (
        <ConfigurationRequired missing={runtime.missing} />
      ) : startupError ? (
        <ConfigurationRequired missing={[]} error={startupError} />
      ) : !client ? (
        <div className="startup-status" role="status">
          Preparing secure sign-in...
        </div>
      ) : (
        <MsalProvider instance={client}>
          <App config={runtime.config} />
        </MsalProvider>
      )}
    </FluentProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
