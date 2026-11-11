import { formatBytes } from './format'

export const DEFAULT_EXTENSIONS = ['.markdown', '.md', '.pdf', '.txt']

/** Fast client-side check for obvious problems. The server re-validates everything. */
export function precheckFile(file: File, maxBytes: number, extensions: string[] = DEFAULT_EXTENSIONS): string | null {
  const dot = file.name.lastIndexOf('.')
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : ''
  if (!extensions.includes(ext)) {
    const what = ext ? `${ext} files aren't` : "Files without an extension aren't"
    return `${what} supported. Use PDF, Markdown, or plain text.`
  }
  if (file.size === 0) return 'The file is empty.'
  if (file.size > maxBytes) {
    return `File is ${formatBytes(file.size)}; the maximum upload size is ${formatBytes(maxBytes)}.`
  }
  return null
}
