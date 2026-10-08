import { Button } from '@/components/ui/button'

export default function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-4xl font-bold tracking-tight">StudyForge</h1>
      <p className="text-muted-foreground">
        A study agent for engineering students that can't make up numbers.
      </p>
      <Button disabled>Coming soon</Button>
    </main>
  )
}
