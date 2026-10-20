import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthGate } from "./auth/AuthGate";
import { AuthProvider } from "./auth/AuthProvider";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGate>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthGate>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
