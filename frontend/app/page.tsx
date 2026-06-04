import { Button } from '@/components/ui/button'

function DiscordIcon() {
  return (
    <svg viewBox="0 0 127.14 96.36" fill="currentColor" className="size-4" aria-hidden="true">
      <path d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0a105.89 105.89 0 0 0-26.25 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15zM42.45 65.69C36.18 65.69 31 60 31 53s5-12.74 11.43-12.74S54 46 53.89 53s-5.1 12.69-11.44 12.69zm42.24 0C78.41 65.69 73.25 60 73.25 53s5-12.74 11.44-12.74S96.23 46 96.12 53s-5.04 12.69-11.43 12.69z" />
    </svg>
  )
}

export default function LoginPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background px-6">
      <div className="flex w-full max-w-sm flex-col items-center gap-10">
        {/* Logo */}
        <div className="flex flex-col items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-card text-3xl shadow-sm">
            ⏰
          </div>
          <div className="space-y-1.5 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">Reminder Bot</h1>
            <p className="text-sm text-muted-foreground">
              All your Discord reminders, in one place.
            </p>
          </div>
        </div>

        {/* Auth */}
        <a href={`${apiUrl}/auth/login`} className="w-full">
          <Button size="lg" className="w-full gap-2.5">
            <DiscordIcon />
            Continue with Discord
          </Button>
        </a>
      </div>
    </main>
  )
}
