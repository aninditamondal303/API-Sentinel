import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { AppRoutes, Providers, createQueryClient } from "@/App";
import { saveSession } from "@/auth/token";
import { jwt } from "./fixtures";

export function signIn(): void {
  saveSession(jwt(), 3600);
}

export function renderApp(path: string) {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false, staleTime: 0 }, mutations: { retry: false } });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Providers client={client}><AppRoutes /></Providers>
    </MemoryRouter>,
  );
}

export function renderWithProviders(ui: ReactElement, path = "/") {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } });
  return render(<MemoryRouter initialEntries={[path]}><Providers client={client}>{ui}</Providers></MemoryRouter>);
}
