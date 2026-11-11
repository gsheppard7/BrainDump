import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverStub)

Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  configurable: true,
  value: () => {
    const noop = () => undefined
    return {
      setTransform: noop,
      clearRect: noop,
      fillRect: noop,
      beginPath: noop,
      moveTo: noop,
      lineTo: noop,
      stroke: noop,
      fill: noop,
      arc: noop,
      fillText: noop,
      createRadialGradient: () => ({ addColorStop: noop }),
    }
  },
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})
