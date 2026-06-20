import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import { AppShell } from "./components/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { RunView } from "./pages/RunView";
import { RunHistory } from "./pages/RunHistory";
import { Composer } from "./pages/Composer";
import { Library } from "./pages/Library";
import { ErrorPage } from "./pages/ErrorPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "compose", element: <Composer /> },
      { path: "compose/:crewId", element: <Composer /> },
      { path: "run/:runId", element: <RunView /> },
      { path: "runs", element: <RunHistory /> },
      { path: "library", element: <Library /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
