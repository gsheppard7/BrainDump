import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { GraphEdge, GraphNode } from '../types'

interface SimNode extends GraphNode {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedId: string | null
  onSelect: (id: string | null) => void
}

function nodeRadius(node: GraphNode): number {
  const base = 14
  const boost = Math.min(18, Math.sqrt(Math.max(node.char_count, 1) / 400))
  return base + boost
}

export function BrainCanvas({ nodes, edges, selectedId, onSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const navigate = useNavigate()
  const sim = useRef<SimNode[]>([])
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null)
  const hover = useRef<string | null>(null)
  const [size, setSize] = useState({ w: 800, h: 520 })

  useEffect(() => {
    const el = canvasRef.current?.parentElement
    if (!el) return
    const sync = () => {
      const width = el.clientWidth || 800
      setSize({ w: width, h: Math.max(420, Math.min(640, width * 0.62)) })
    }
    sync()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(sync)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const { w, h } = size
    const existing = new Map(sim.current.map((n) => [n.id, n]))
    sim.current = nodes.map((node, i) => {
      const prev = existing.get(node.id)
      const angle = (i / Math.max(nodes.length, 1)) * Math.PI * 2
      const ring = Math.min(w, h) * 0.28
      return {
        ...node,
        x: prev?.x ?? w / 2 + Math.cos(angle) * ring,
        y: prev?.y ?? h / 2 + Math.sin(angle) * ring,
        vx: prev?.vx ?? 0,
        vy: prev?.vy ?? 0,
        radius: nodeRadius(node),
      }
    })
  }, [nodes, size])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext?.('2d')
    if (!ctx) return
    let frame = 0
    let alive = true
    const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const stepForces = () => {
      const { w, h } = size
      const list = sim.current
      const byId = new Map(list.map((n) => [n.id, n]))

      for (const a of list) {
        if (drag.current?.id === a.id) continue
        a.vx += (w / 2 - a.x) * 0.003
        a.vy += (h / 2 - a.y) * 0.003
        for (const b of list) {
          if (a === b) continue
          const dx = a.x - b.x
          const dy = a.y - b.y
          const dist = Math.max(24, Math.hypot(dx, dy))
          const force = 900 / (dist * dist)
          a.vx += (dx / dist) * force
          a.vy += (dy / dist) * force
        }
      }
      for (const edge of edges) {
        const a = byId.get(edge.source)
        const b = byId.get(edge.target)
        if (!a || !b) continue
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.max(1, Math.hypot(dx, dy))
        const ideal = 110 + (1 - edge.weight) * 80
        const pull = (dist - ideal) * 0.01 * edge.weight
        const fx = (dx / dist) * pull
        const fy = (dy / dist) * pull
        if (drag.current?.id !== a.id) {
          a.vx += fx
          a.vy += fy
        }
        if (drag.current?.id !== b.id) {
          b.vx -= fx
          b.vy -= fy
        }
      }
      for (const n of list) {
        if (drag.current?.id === n.id) continue
        n.vx *= 0.86
        n.vy *= 0.86
        n.x += n.vx
        n.y += n.vy
        n.x = Math.min(w - n.radius, Math.max(n.radius, n.x))
        n.y = Math.min(h - n.radius, Math.max(n.radius, n.y))
      }
      return byId
    }

    const draw = (byId: Map<string, SimNode>) => {
      const { w, h } = size
      const list = sim.current
      const dpr = window.devicePixelRatio || 1
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
        canvas.style.width = `${w}px`
        canvas.style.height = `${h}px`
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      }
      ctx.clearRect(0, 0, w, h)

      const glow = ctx.createRadialGradient(w / 2, h / 2, 20, w / 2, h / 2, Math.max(w, h) * 0.55)
      glow.addColorStop(0, 'rgba(99, 102, 241, 0.07)')
      glow.addColorStop(1, 'rgba(250, 250, 249, 0)')
      ctx.fillStyle = glow
      ctx.fillRect(0, 0, w, h)

      for (const edge of edges) {
        const a = byId.get(edge.source)
        const b = byId.get(edge.target)
        if (!a || !b) continue
        const hot =
          selectedId === a.id ||
          selectedId === b.id ||
          hover.current === a.id ||
          hover.current === b.id
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = hot
          ? `rgba(79, 70, 229, ${0.35 + edge.weight * 0.45})`
          : `rgba(120, 113, 108, ${0.12 + edge.weight * 0.35})`
        ctx.lineWidth = hot ? 2.2 : 1 + edge.weight
        ctx.stroke()
      }

      for (const n of list) {
        const active = selectedId === n.id || hover.current === n.id
        const indexed = n.embedding_status === 'done'
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.radius + (active ? 3 : 0), 0, Math.PI * 2)
        ctx.fillStyle = n.kind === 'note' ? '#eef2ff' : '#ecfdf5'
        ctx.fill()
        ctx.lineWidth = active ? 2.5 : 1.5
        ctx.strokeStyle = active
          ? '#4f46e5'
          : indexed
            ? n.kind === 'note'
              ? '#818cf8'
              : '#34d399'
            : '#d6d3d1'
        ctx.stroke()

        if (n.embedding_status === 'pending') {
          ctx.beginPath()
          ctx.arc(n.x + n.radius * 0.65, n.y - n.radius * 0.65, 3.5, 0, Math.PI * 2)
          ctx.fillStyle = '#f59e0b'
          ctx.fill()
        }

        ctx.fillStyle = '#1c1917'
        ctx.font = `${active ? '600' : '500'} 12px ui-sans-serif, system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        const label = n.title.length > 28 ? `${n.title.slice(0, 27)}…` : n.title
        ctx.fillText(label, n.x, n.y + n.radius + 6)
      }
    }

    const tick = () => {
      if (!alive) return
      draw(stepForces())
      if (!reduced) frame = requestAnimationFrame(tick)
    }
    // Settle briefly even when motion is reduced / under test.
    for (let i = 0; i < 40; i++) stepForces()
    tick()
    return () => {
      alive = false
      cancelAnimationFrame(frame)
    }
  }, [edges, selectedId, size])

  const pick = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const x = clientX - rect.left
    const y = clientY - rect.top
    let best: SimNode | null = null
    let bestDist = Infinity
    for (const n of sim.current) {
      const d = Math.hypot(n.x - x, n.y - y)
      if (d <= n.radius + 8 && d < bestDist) {
        best = n
        bestDist = d
      }
    }
    return best
  }

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label="Knowledge graph of your sources"
      className="block w-full cursor-grab rounded-2xl border border-stone-200 bg-stone-50 touch-none active:cursor-grabbing"
      onPointerDown={(e) => {
        const node = pick(e.clientX, e.clientY)
        if (!node) {
          onSelect(null)
          return
        }
        const canvas = canvasRef.current!
        const rect = canvas.getBoundingClientRect()
        drag.current = { id: node.id, dx: node.x - (e.clientX - rect.left), dy: node.y - (e.clientY - rect.top) }
        onSelect(node.id)
        canvas.setPointerCapture(e.pointerId)
      }}
      onPointerMove={(e) => {
        const node = pick(e.clientX, e.clientY)
        hover.current = node?.id ?? null
        if (!drag.current) return
        const canvas = canvasRef.current!
        const rect = canvas.getBoundingClientRect()
        const target = sim.current.find((n) => n.id === drag.current!.id)
        if (!target) return
        target.x = e.clientX - rect.left + drag.current.dx
        target.y = e.clientY - rect.top + drag.current.dy
        target.vx = 0
        target.vy = 0
      }}
      onPointerUp={(e) => {
        drag.current = null
        canvasRef.current?.releasePointerCapture(e.pointerId)
      }}
      onDoubleClick={(e) => {
        const node = pick(e.clientX, e.clientY)
        if (node) navigate(`/sources/${node.id}`)
      }}
    />
  )
}
