import { cn } from '@/lib/cn'
import { useLineTokens } from '@/lib/useHighlight'

export function CodeBlock({ code, language, className }: { code: string; language: string; className?: string }) {
  const tokens = useLineTokens(code, language)
  const lines = tokens ?? code.split('\n').map((line) => [{ content: line, style: undefined }])

  return (
    <pre className={cn('overflow-x-auto px-3 py-2.5 font-mono text-[12.5px] leading-5 scrollbar-thin', className)}>
      <code>
        {lines.map((line, index) => (
          <div key={index} className="whitespace-pre">
            {line.length === 0
              ? ' '
              : line.map((token, tokenIndex) => (
                  <span key={tokenIndex} className="shiki-token" style={token.style}>
                    {token.content}
                  </span>
                ))}
          </div>
        ))}
      </code>
    </pre>
  )
}
