import { setupServer } from "msw/node";

/** Unit tests only: each test registers the responses it needs with server.use(...). */
export const server = setupServer();
