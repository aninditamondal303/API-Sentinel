import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { preloadAppPages } from "@/App";
import { server } from "./server";

// Signed-in pages are code-split with React.lazy. A cold dynamic import (including recharts) can take
// longer than Testing Library's 1 s default on a slow machine or container, leaving the Suspense
// fallback on screen. Load the chunks once up front so tests measure the UI, not module loading.
configure({ asyncUtilTimeout: 3000 });

beforeAll(async () => {
  server.listen({ onUnhandledFrame: "error" });
  await preloadAppPages();
}, 60_000);
afterEach(() => {
  // Unmount first so in-flight queries of a finished test cannot hit the next test's handlers.
  cleanup();
  server.resetHandlers();
  sessionStorage.clear();
});
afterAll(() => server.close());
