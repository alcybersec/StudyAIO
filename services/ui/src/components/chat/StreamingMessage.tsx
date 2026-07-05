interface StreamingMessageProps {
  text: string
}

export function StreamingMessage({ text }: StreamingMessageProps) {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl rounded-bl-md px-4 py-3 bg-surface-0 max-w-[85%]">
        <div className="text-sm text-text whitespace-pre-wrap">
          {text}
          <span className="inline-block w-0.5 h-4 bg-peri animate-pulse ml-0.5 align-text-bottom" />
        </div>
      </div>
    </div>
  )
}
