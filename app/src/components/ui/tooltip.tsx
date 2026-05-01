"use client";

import { Tooltip as BaseTooltip } from "@base-ui/react/tooltip";
import type { ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  align?: "start" | "center" | "end";
}

export const Tooltip = ({ content, children, side = "top", align = "center" }: TooltipProps) => {
  if (!content) return <>{children}</>;
  return (
    <BaseTooltip.Provider>
      <BaseTooltip.Root>
        <BaseTooltip.Trigger render={children as React.JSX.Element} />
        <BaseTooltip.Portal>
          <BaseTooltip.Positioner align={align} side={side} sideOffset={6}>
            <BaseTooltip.Popup className="rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background">
              {content}
            </BaseTooltip.Popup>
          </BaseTooltip.Positioner>
        </BaseTooltip.Portal>
      </BaseTooltip.Root>
    </BaseTooltip.Provider>
  );
};
