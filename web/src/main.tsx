import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { PublicDemoPage } from "./PublicDemoPage";
import { selectEntryPoint } from "./public-route";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);

if (selectEntryPoint(window.location.pathname) === "public-demo") {
  root.render(
    <StrictMode>
      <PublicDemoPage />
    </StrictMode>,
  );
} else {
  import("./AuthenticatedRoot")
    .then(({ AuthenticatedRoot }) => {
      root.render(
        <StrictMode>
          <AuthenticatedRoot />
        </StrictMode>,
      );
    })
    .catch(() => {
      root.render(
        <div className="startup-status" role="alert">
          FreshSense could not start.
        </div>,
      );
    });
}
