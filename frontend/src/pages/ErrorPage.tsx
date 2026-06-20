import { Link, useRouteError } from "react-router-dom";
import { Button } from "../components/ui";

export function ErrorPage() {
  const error = useRouteError();
  const message =
    error instanceof Error ? error.message : "This view hit an unexpected error.";
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-8 text-center">
      <p className="font-mono text-label text-signal">crewforge · error</p>
      <h1 className="text-display font-semibold text-ink">Something came off the rails</h1>
      <p className="max-w-md text-body text-muted">{message}</p>
      <Link to="/">
        <Button variant="primary">Back to dashboard</Button>
      </Link>
    </div>
  );
}
