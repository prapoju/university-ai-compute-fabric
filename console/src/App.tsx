import { CopilotConsole } from './CopilotConsole';

// One route: /helpdesk/copilot (story 1.7). Any other path is a plain not-found panel.
export function App() {
  if (window.location.pathname !== '/helpdesk/copilot') {
    return (
      <main className="page">
        <h1>Page not found</h1>
      </main>
    );
  }
  return <CopilotConsole />;
}
