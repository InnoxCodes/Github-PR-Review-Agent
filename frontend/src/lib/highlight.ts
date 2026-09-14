import type { CSSProperties } from 'react'
import type { Hunk } from './types'

export interface Token {
  content: string
  style?: CSSProperties
}

type ShikiHighlighter = Awaited<ReturnType<typeof import('shiki/bundle/full').createHighlighter>>

const THEMES = { light: 'github-light-default', dark: 'github-dark-default' } as const

// Backend language ids (app/diff/classify.py) -> shiki grammar ids.
const LANGUAGE_ALIASES: Record<string, string> = {
  shell: 'shellscript',
  protobuf: 'proto',
  text: 'text',
}

let highlighterPromise: Promise<ShikiHighlighter> | null = null
const loadedLanguages = new Map<string, Promise<string>>()

function getHighlighter(): Promise<ShikiHighlighter> {
  // Loaded lazily so the ~landing page never pays for grammars; the JS regex engine avoids
  // shipping the Oniguruma WASM binary.
  highlighterPromise ??= Promise.all([import('shiki/bundle/full'), import('shiki/engine/javascript')]).then(
    ([{ createHighlighter }, { createJavaScriptRegexEngine }]) =>
      createHighlighter({
        themes: [THEMES.light, THEMES.dark],
        langs: [],
        engine: createJavaScriptRegexEngine({ forgiving: true }),
      }),
  )
  return highlighterPromise
}

async function ensureLanguage(highlighter: ShikiHighlighter, language: string): Promise<string> {
  const id = LANGUAGE_ALIASES[language] ?? language
  if (id === 'text') return 'text'
  let pending = loadedLanguages.get(id)
  if (!pending) {
    pending = highlighter
      .loadLanguage(id as Parameters<ShikiHighlighter['loadLanguage']>[0])
      .then(() => id)
      .catch(() => 'text')
    loadedLanguages.set(id, pending)
  }
  return pending
}

export async function tokenizeLines(code: string, language: string): Promise<Token[][]> {
  const plain = () => code.split('\n').map((line) => [{ content: line }])
  try {
    const highlighter = await getHighlighter()
    const lang = await ensureLanguage(highlighter, language)
    if (lang === 'text') return plain()
    const { tokens } = highlighter.codeToTokens(code, {
      lang: lang as Parameters<ShikiHighlighter['codeToTokens']>[1]['lang'],
      themes: THEMES,
      defaultColor: false,
    })
    return tokens.map((line) =>
      line.map((token) => ({ content: token.content, style: token.htmlStyle as CSSProperties | undefined })),
    )
  } catch {
    return plain()
  }
}

/**
 * Highlight a hunk with real grammar context. Old and new sides are tokenized as two
 * contiguous excerpts (context+deleted, context+added), then mapped back line by line —
 * so a multi-line string or comment that spans a change still colours correctly.
 */
export async function tokenizeHunks(hunks: Hunk[], language: string): Promise<Token[][][]> {
  return Promise.all(
    hunks.map(async (hunk) => {
      const newSide = hunk.lines.filter((line) => line.type !== 'delete').map((line) => line.content)
      const oldSide = hunk.lines.filter((line) => line.type !== 'add').map((line) => line.content)
      const [newTokens, oldTokens] = await Promise.all([
        tokenizeLines(newSide.join('\n'), language),
        oldSide.length === newSide.length && oldSide.every((line, i) => line === newSide[i])
          ? Promise.resolve(null)
          : tokenizeLines(oldSide.join('\n'), language),
      ])

      let newIndex = 0
      let oldIndex = 0
      return hunk.lines.map((line) => {
        if (line.type === 'add') return newTokens[newIndex++] ?? [{ content: line.content }]
        if (line.type === 'delete') return (oldTokens ?? newTokens)[oldIndex++] ?? [{ content: line.content }]
        oldIndex++
        return newTokens[newIndex++] ?? [{ content: line.content }]
      })
    }),
  )
}
