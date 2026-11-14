import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
// Imported lazily so a test file's own `vi.mock("@/lib/api/client")` applies to the helpers too.
vi.mock("next/navigation", async () => (await import("./test-utils")).navigationMock);

const NODE_SIZE_PX = 100;

/** jsdom has no layout engine; React Flow and Radix need these browser APIs to mount. */
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

class DOMMatrixReadOnlyStub {
  readonly m22: number;
  constructor(transform?: string) {
    const scale = /scale\(([\d.]+)\)/.exec(transform ?? "")?.[1];
    this.m22 = scale ? Number(scale) : 1;
  }
}

function installLayoutStubs(): void {
  if (typeof window === "undefined") return;
  globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
  Object.assign(globalThis, { DOMMatrixReadOnly: DOMMatrixReadOnlyStub });
  Object.defineProperties(HTMLElement.prototype, {
    offsetHeight: { configurable: true, get: () => NODE_SIZE_PX },
    offsetWidth: { configurable: true, get: () => NODE_SIZE_PX },
  });
  Object.assign(SVGElement.prototype, {
    getBBox: () => ({ x: 0, y: 0, width: NODE_SIZE_PX, height: NODE_SIZE_PX }),
  });
  Object.assign(Element.prototype, {
    hasPointerCapture: () => false,
    releasePointerCapture: () => undefined,
    scrollIntoView: () => undefined,
  });
}

installLayoutStubs();

afterEach(async () => {
  cleanup();
  (await import("./test-utils")).resetNavigation();
});
