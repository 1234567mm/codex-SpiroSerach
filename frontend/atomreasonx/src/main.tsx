import React from "react";
import ReactDOM from "react-dom/client";
import { AppShell } from "./AppShell";
import fixture from "./fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "./contracts/types";

const workspace = fixture as unknown as AtomReasonXWorkspaceState;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppShell workspace={workspace} />
  </React.StrictMode>
);
