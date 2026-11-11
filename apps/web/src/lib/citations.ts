const CITATION = /\[(\d+(?:\s*,\s*\d+)*)\]/g

/** Turn "[2]" / "[1, 3]" into Markdown links "#cite-N" for passages that exist. */
export function linkCitations(markdown: string, passageCount: number): string {
  return markdown.replace(CITATION, (whole, numbers: string) => {
    const valid = numbers
      .split(',')
      .map((n) => Number(n.trim()))
      .filter((n) => n >= 1 && n <= passageCount)
    if (!valid.length) return whole
    return valid.map((n) => `[\\[${n}\\]](#cite-${n})`).join('')
  })
}

export function citationNumber(href: string | undefined): number | null {
  const match = href?.match(/^#cite-(\d+)$/)
  return match ? Number(match[1]) : null
}
