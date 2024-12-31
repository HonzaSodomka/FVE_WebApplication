import { Button } from "@/components/ui/button"

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-slate-100">
      <div className="space-y-8 text-center">
        <h1 className="text-4xl font-bold text-slate-900">
          Welcome to FVE Web App
        </h1>
        
        <div className="flex gap-4 justify-center">
          <Button variant="default">
            Primary Button 1
          </Button>
          <Button variant="secondary">
            Secondary Button
          </Button>
          <Button variant="outline">
            Outline Button
          </Button>
        </div>
      </div>
    </main>
  )
}