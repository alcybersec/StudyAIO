interface LevelDisplayProps {
  level: number
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-12 w-12 text-sm',
  lg: 'h-16 w-16 text-lg',
}

export function LevelDisplay({ level, size = 'md' }: LevelDisplayProps) {
  return (
    <div
      className={`${sizeClasses[size]} flex items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 font-bold ring-2 ring-indigo-200 dark:ring-indigo-800`}
    >
      {level}
    </div>
  )
}
