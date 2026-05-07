interface PlaceholderPageProps {
  title: string
  description?: string
}

export function PlaceholderPage({ title, description = "Coming soon..." }: PlaceholderPageProps) {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="text-muted-foreground">{description}</p>
    </div>
  )
}