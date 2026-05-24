import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import { ArrowUpRight, BookOpen, KeyRound, MessageCircle } from "lucide-react";

const QUICK_ACTIONS = [
  {
    description: "Test retrieval with citations",
    href: "/chat",
    icon: MessageCircle,
    title: "Run a query",
  },
  {
    description: "Add and organize documents",
    href: "/collections",
    icon: BookOpen,
    title: "Manage collections",
  },
  {
    description: "Create scoped client access",
    href: "/api-keys",
    icon: KeyRound,
    title: "Mint API key",
  },
] as const;

export const QuickActions = () => (
  <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
    {QUICK_ACTIONS.map((action) => (
      <QuickAction key={action.href} {...action} />
    ))}
  </div>
);

const QuickAction = ({
  description,
  href,
  icon: Icon,
  title,
}: {
  description: string;
  href: string;
  icon: LucideIcon;
  title: string;
}) => (
  <Link
    to={href}
    className="group flex items-center gap-3 rounded-xl border border-border bg-background p-4 hover:border-hover-border"
  >
    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground group-hover:bg-primary group-hover:text-primary-foreground">
      <Icon className="size-4" />
    </div>
    <div className="min-w-0 flex-1">
      <div className="text-sm font-semibold">{title}</div>
      <div className="truncate text-xs text-muted-foreground">{description}</div>
    </div>
    <ArrowUpRight className="size-4 text-muted-foreground" />
  </Link>
);
