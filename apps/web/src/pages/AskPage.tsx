import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import { Link } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import { api, ApiError } from '../api'
import { Alert } from '../components/Alert'
import { KindTag } from '../components/KindTag'
import { Spinner } from '../components/StatusBadge'
import { useChat, useChats, useDeleteChat, useMeta } from '../hooks'
import { citationNumber, linkCitations } from '../lib/citations'
import { formatRelative } from '../lib/format'
import type { AskMode, AskPassage, ChatSessionSummary } from '../types'

const MODES: { value: AskMode; label: string; hint: string; example: string }[] = [
  {
    value: 'recall',
    label: 'Recall',
    hint: 'Find a fact or remember what you wrote',
    example: 'What have I written about my career goals?',
  },
  {
    value: 'plan',
    label: 'Plan',
    hint: 'Turn your notes into concrete next steps',
    example: 'Make a 4-week plan to build on the skills in my notes.',
  },
  {
    value: 'report',
    label: 'Report',
    hint: 'Summarise everything on a topic',
    example: 'Write a one-page summary of my interests and how they connect.',
  },
  {
    value: 'brainstorm',
    label: 'Brainstorm',
    hint: 'Generate ideas by connecting your notes',
    example: 'Brainstorm side-project ideas that combine two or more of my interests.',
  },
]

export interface AnswerState {
  question: string
  mode: AskMode
  text: string
  passages: AskPassage[]
  model?: string
  notice?: string | null
  citations?: number[]
  grounded?: boolean
  error?: string
  finished: boolean
  sessionId?: string
}

export function AskPage() {
  const meta = useMeta()
  const chats = useChats()
  const deleteChat = useDeleteChat()
  const queryClient = useQueryClient()
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<AskMode>('recall')
  const [answer, setAnswer] = useState<AnswerState | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const selected = useChat(selectedId)

  const running = answer !== null && !answer.finished
  const available = meta.data?.capabilities.grounded_chat ?? true
  const activeMode = MODES.find((m) => m.value === mode)!

  const showLive = selectedId === null
  const historyAnswer = selected.data ? sessionToAnswer(selected.data) : null

  const startNew = () => {
    setSelectedId(null)
    setAnswer(null)
    setQuestion('')
  }

  const openChat = (id: string) => {
    controller.current?.abort()
    setSelectedId(id)
    setAnswer(null)
  }

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    const q = question.trim()
    if (!q || running) return
    setSelectedId(null)
    const abort = new AbortController()
    controller.current = abort
    setAnswer({ question: q, mode, text: '', passages: [], finished: false })
    const update = (patch: (prev: AnswerState) => Partial<AnswerState>) =>
      setAnswer((prev) => (prev ? { ...prev, ...patch(prev) } : prev))
    try {
      await api.ask(
        q,
        mode,
        (event) => {
          switch (event.type) {
            case 'session':
              update(() => ({ sessionId: event.id }))
              break
            case 'meta':
              update(() => ({ model: event.model, notice: event.notice }))
              break
            case 'context':
              update(() => ({ passages: event.passages }))
              break
            case 'delta':
              update((prev) => ({ text: prev.text + event.text }))
              break
            case 'done':
              update(() => ({
                citations: event.citations,
                grounded: event.grounded,
                finished: true,
                sessionId: event.session_id ?? undefined,
              }))
              break
            case 'error':
              update(() => ({ error: event.message, finished: true }))
              break
          }
        },
        abort.signal,
      )
      update(() => ({ finished: true }))
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
    } catch (err) {
      if (abort.signal.aborted) {
        update(() => ({ finished: true, error: 'Stopped.' }))
        void queryClient.invalidateQueries({ queryKey: ['chats'] })
      } else {
        update(() => ({
          finished: true,
          error: err instanceof ApiError ? err.message : 'Something went wrong.',
        }))
      }
    }
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void submit()
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <HistoryPanel
        items={chats.data?.items ?? []}
        selectedId={selectedId}
        loading={chats.isLoading}
        onSelect={openChat}
        onNew={startNew}
        onDelete={(id) => {
          deleteChat.mutate(id, {
            onSuccess: () => {
              if (selectedId === id) startNew()
            },
          })
        }}
      />

      <div className="flex min-w-0 flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ask</h1>
          <p className="mt-1 text-sm text-stone-500">
            Ask questions, make plans, write reports, or brainstorm — answered from your own notes, with
            sources. Every answer is saved in History.
          </p>
        </div>

        {!available && meta.data && (
          <Alert tone="warning">
            Ask needs the local AI model.{' '}
            {meta.data.ai.message ?? 'Set CHAT_PROVIDER=ollama in .env and restart the API.'}
          </Alert>
        )}

        {showLive ? (
          <>
            <form
              onSubmit={submit}
              className="flex flex-col gap-3 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm"
            >
              <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Answer style">
                {MODES.map((m) => (
                  <button
                    key={m.value}
                    type="button"
                    role="radio"
                    aria-checked={mode === m.value}
                    onClick={() => setMode(m.value)}
                    title={m.hint}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      mode === m.value
                        ? 'bg-indigo-600 text-white'
                        : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
                <span className="ml-2 self-center text-xs text-stone-500">{activeMode.hint}</span>
              </div>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={activeMode.example}
                aria-label="Your question"
                rows={3}
                maxLength={2000}
                className="resize-y rounded-lg border border-stone-200 px-3 py-2 text-sm leading-relaxed outline-none placeholder:text-stone-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
              />
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setQuestion(activeMode.example)}
                  className="text-xs text-stone-500 hover:text-indigo-600"
                >
                  Try an example
                </button>
                {running ? (
                  <button
                    type="button"
                    onClick={() => controller.current?.abort()}
                    className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!question.trim() || !available}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Ask
                  </button>
                )}
              </div>
            </form>
            {answer && <AnswerView answer={answer} />}
          </>
        ) : selected.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-stone-500">
            <Spinner /> Loading conversation…
          </p>
        ) : selected.isError ? (
          <Alert>Couldn't load that conversation.</Alert>
        ) : historyAnswer ? (
          <AnswerView answer={historyAnswer} historic />
        ) : null}
      </div>
    </div>
  )
}

function sessionToAnswer(session: {
  mode: AskMode
  messages: {
    role: string
    content: string
    citations: number[] | null
    passages: AskPassage[] | null
    grounded: boolean | null
    model: string | null
    notice: string | null
    error_message: string | null
  }[]
}): AnswerState | null {
  const user = session.messages.find((m) => m.role === 'user')
  const assistant = [...session.messages].reverse().find((m) => m.role === 'assistant')
  if (!user) return null
  return {
    question: user.content,
    mode: session.mode,
    text: assistant?.content ?? '',
    passages: assistant?.passages ?? [],
    citations: assistant?.citations ?? undefined,
    grounded: assistant?.grounded ?? undefined,
    model: assistant?.model ?? undefined,
    notice: assistant?.notice,
    error: assistant?.error_message ?? undefined,
    finished: true,
  }
}

function HistoryPanel({
  items,
  selectedId,
  loading,
  onSelect,
  onNew,
  onDelete,
}: {
  items: ChatSessionSummary[]
  selectedId: string | null
  loading: boolean
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}) {
  return (
    <aside className="flex flex-col gap-2 lg:sticky lg:top-20 lg:self-start">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-xs font-semibold tracking-wide text-stone-500 uppercase">History</h2>
        <button
          type="button"
          onClick={onNew}
          className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
        >
          New
        </button>
      </div>
      {loading && <p className="px-1 text-xs text-stone-400">Loading…</p>}
      {!loading && items.length === 0 && (
        <p className="rounded-xl border border-dashed border-stone-200 px-3 py-4 text-xs text-stone-400">
          Answers you get will show up here so you can reopen them later.
        </p>
      )}
      <ul className="flex max-h-48 flex-col gap-1 overflow-y-auto lg:max-h-[calc(100vh-8rem)]">
        {items.map((item) => {
          const active = selectedId === item.id
          return (
            <li key={item.id} className="group relative">
              <button
                type="button"
                aria-label={item.title}
                onClick={() => onSelect(item.id)}
                className={`w-full rounded-xl px-3 py-2 text-left transition ${
                  active ? 'bg-indigo-50 ring-1 ring-indigo-200' : 'hover:bg-stone-100'
                }`}
              >
                <span className="line-clamp-2 text-sm font-medium text-stone-800">{item.title}</span>
                <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-stone-400">
                  <span className="capitalize">{item.mode}</span>
                  <span>·</span>
                  <span>{formatRelative(item.updated_at)}</span>
                </span>
              </button>
              <button
                type="button"
                aria-label={`Delete “${item.title}”`}
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(item.id)
                }}
                className="absolute top-2 right-2 hidden rounded px-1.5 py-0.5 text-[10px] font-medium text-stone-400 hover:bg-white hover:text-rose-600 group-hover:block"
              >
                Delete
              </button>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

export function AnswerView({ answer, historic = false }: { answer: AnswerState; historic?: boolean }) {
  const cited = new Set(answer.citations ?? [])
  const byNumber = new Map(answer.passages.map((p) => [p.n, p]))
  const sourceLink = (p: AskPassage) =>
    `/sources/${p.source_id}?${new URLSearchParams({ q: answer.question, chunk: String(p.chunk_ordinal) })}`

  const components: Components = {
    a: ({ href, children }) => {
      const n = citationNumber(href)
      const passage = n !== null ? byNumber.get(n) : undefined
      if (!passage) return <span>{children}</span>
      return (
        <Link
          to={sourceLink(passage)}
          title={`${passage.title}${passage.page ? `, p. ${passage.page}` : ''}`}
          className="mx-0.5 rounded bg-indigo-50 px-1 text-[0.8em] font-medium text-indigo-700 no-underline hover:bg-indigo-100"
        >
          {n}
        </Link>
      )
    },
  }

  const waiting = !answer.finished && !answer.text
  return (
    <section className="flex flex-col gap-4" aria-label="Answer">
      {historic && (
        <p className="rounded-xl bg-stone-100 px-3 py-2 text-sm text-stone-600">
          <span className="font-medium text-stone-800">You asked:</span> {answer.question}
        </p>
      )}
      <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-stone-500">
          <span className="font-medium text-stone-700">{historic ? 'Saved answer' : 'Answer'}</span>
          {answer.model && <span>· {answer.model} (local)</span>}
          <span className="capitalize">· {answer.mode}</span>
          {answer.finished && answer.grounded && (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">
              Cites {cited.size} source passage{cited.size === 1 ? '' : 's'}
            </span>
          )}
        </div>
        {answer.notice && <Alert tone="warning">{answer.notice}</Alert>}
        {waiting && (
          <p className="flex items-center gap-2 text-sm text-stone-500">
            <Spinner />
            {answer.passages.length
              ? `Reading ${answer.passages.length} relevant passages… (the first answer takes longer while the model loads)`
              : 'Searching your library…'}
          </p>
        )}
        {answer.text && (
          <div className="answer-prose text-[15px] leading-7 text-stone-800">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={components}
              disallowedElements={['img']}
              unwrapDisallowed
            >
              {linkCitations(answer.text, answer.passages.length)}
            </ReactMarkdown>
            {!answer.finished && (
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-indigo-400 align-middle" />
            )}
          </div>
        )}
        {answer.error && (
          <div className="mt-3">
            <Alert>{answer.error}</Alert>
          </div>
        )}
        {answer.finished && !answer.error && answer.passages.length > 0 && !answer.grounded && (
          <div className="mt-3">
            <Alert tone="warning">This answer doesn't cite any of your notes — treat it with caution.</Alert>
          </div>
        )}
        {answer.finished && answer.passages.length > 0 && (
          <p className="mt-4 text-xs text-stone-400">
            Generated on your Mac from your notes. Local models make mistakes — check the cited sources.
          </p>
        )}
      </div>

      {answer.passages.length > 0 && (
        <PassageList title="Sources">
          {answer.passages.map((p) => (
            <li key={p.chunk_id}>
              <Link
                to={sourceLink(p)}
                className={`flex gap-3 rounded-lg px-3 py-2 transition hover:bg-stone-100 ${
                  answer.finished && !cited.has(p.n) ? 'opacity-55' : ''
                }`}
              >
                <span className="mt-0.5 w-6 shrink-0 text-right text-xs font-semibold text-indigo-700">
                  {p.n}
                </span>
                <KindTag kind={p.kind} fileType={p.file_type} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{p.title}</span>
                  <span className="line-clamp-2 text-xs text-stone-500">{p.excerpt}</span>
                </span>
                <span className="shrink-0 text-right text-xs text-stone-400">
                  {p.page ? `p. ${p.page} · ` : ''}
                  {formatRelative(p.created_at)}
                  {answer.finished && !cited.has(p.n) && <span className="block">not cited</span>}
                </span>
              </Link>
            </li>
          ))}
        </PassageList>
      )}
    </section>
  )
}

function PassageList({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h2 className="mb-2 px-1 text-sm font-semibold text-stone-700">{title}</h2>
      <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 bg-white">{children}</ul>
    </div>
  )
}
