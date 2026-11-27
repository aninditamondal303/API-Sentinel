import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SLOW_REQUEST_MS, SlowServerNotice } from "./SlowServerNotice";

describe("SlowServerNotice", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("stays hidden while the request is still within the threshold", () => {
    render(<SlowServerNotice active />);
    act(() => vi.advanceTimersByTime(SLOW_REQUEST_MS - 1));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("explains the wait once the request passes the threshold", () => {
    render(<SlowServerNotice active />);
    act(() => vi.advanceTimersByTime(SLOW_REQUEST_MS));
    expect(screen.getByRole("status")).toHaveTextContent("Starting the server");
  });

  it("disappears when the request finishes", () => {
    const { rerender } = render(<SlowServerNotice active />);
    act(() => vi.advanceTimersByTime(SLOW_REQUEST_MS));
    expect(screen.getByRole("status")).toBeInTheDocument();
    rerender(<SlowServerNotice active={false} />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("never appears when no request is pending", () => {
    render(<SlowServerNotice active={false} />);
    act(() => vi.advanceTimersByTime(SLOW_REQUEST_MS * 2));
    expect(screen.queryByRole("status")).toBeNull();
  });
});
