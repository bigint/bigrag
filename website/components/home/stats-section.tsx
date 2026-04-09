const stats = [
  {
    label: "Document formats",
    sublabel: "PDF, DOCX, images, and more",
    value: "15+",
  },
  {
    label: "Embedding models",
    sublabel: "OpenAI and Cohere",
    value: "6",
  },
  {
    label: "To deploy",
    sublabel: "Docker Compose",
    value: "5 min",
  },
];

export function StatsSection() {
  return (
    <section className="border-b border-fd-border bg-fd-card/50">
      <div className="mx-auto grid max-w-6xl gap-px sm:grid-cols-3">
        {stats.map((stat) => (
          <div
            className="flex flex-col items-center justify-center px-6 py-14 text-center"
            key={stat.label}
          >
            <p className="text-4xl font-bold tracking-tight text-fd-foreground md:text-5xl">
              {stat.value}
            </p>
            <p className="mt-2 text-sm font-medium text-fd-foreground">{stat.label}</p>
            <p className="text-xs text-fd-muted-foreground">{stat.sublabel}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
