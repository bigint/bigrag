import { LogOut, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AccountActiveSessionsSectionProps {
  readonly pending: boolean;
  readonly onSignOutEverywhere: () => void;
}

export const AccountActiveSessionsSection = ({
  pending,
  onSignOutEverywhere,
}: AccountActiveSessionsSectionProps) => (
  <div className="mt-5 border-border border-t pt-4">
    <h3 className="flex items-center gap-2 text-base font-semibold tracking-normal">
      <ShieldAlert className="size-3.5 text-warning" />
      Active sessions
    </h3>
    <p className="mt-1 text-sm text-muted-foreground">
      Sign out of every browser or device where this account is logged in.
    </p>
    <div className="mt-4 flex flex-col gap-3 rounded-md border border-border bg-muted/25 p-3">
      <p className="text-sm text-muted-foreground">
        This revokes all refresh tokens immediately. You'll need to log in again on every device,
        including this one.
      </p>
      <Button
        className="shrink-0"
        disabled={pending}
        onClick={onSignOutEverywhere}
        variant="outline"
      >
        <LogOut className="size-3.5" />
        {pending ? "Signing out…" : "Sign out everywhere"}
      </Button>
    </div>
  </div>
);
