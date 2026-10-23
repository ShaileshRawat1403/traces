import * as Dialog from "@radix-ui/react-dialog";
import type { RefObject } from "react";
import { ClaimEvidence } from "./ClaimPage";

/** Evidence drawer: right-side panel on desktop, bottom sheet on phones. Open state lives in the URL (?claim=). */
export function EvidenceDrawer({
  repoId,
  sha,
  claimId,
  onClose,
  returnFocus,
}: {
  repoId: string;
  sha: string;
  claimId: string | null;
  onClose: () => void;
  /** The control that opened the drawer. Focus returns there on close (the drawer has no Radix trigger). */
  returnFocus?: RefObject<HTMLElement | null>;
}) {
  return (
    <Dialog.Root open={!!claimId} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content
          className="fixed inset-x-0 bottom-0 z-50 flex max-h-[88dvh] flex-col rounded-t-lg border-t border-line bg-canvas shadow-xl focus:outline-none md:inset-y-0 md:left-auto md:right-0 md:max-h-none md:w-[min(560px,92vw)] md:rounded-none md:border-l md:border-t-0"
          data-testid="evidence-drawer"
          onCloseAutoFocus={(e) => {
            const el = returnFocus?.current;
            if (el && el.isConnected) {
              e.preventDefault();
              el.focus();
            }
          }}
        >
          <div className="flex items-center gap-2 border-b border-line bg-surface px-4 py-2">
            <div className="mx-auto h-1 w-10 rounded bg-line-strong md:hidden" aria-hidden="true" />
            <Dialog.Title className="text-sm font-semibold md:mr-auto">Evidence</Dialog.Title>
            <Dialog.Description className="sr-only">Status, checks, provenance and pinned source lines for one claim.</Dialog.Description>
            <Dialog.Close className="tap rounded-md border border-line-strong px-3 text-sm">Close</Dialog.Close>
          </div>
          <div className="overflow-y-auto p-4">{claimId ? <ClaimEvidence repoId={repoId} sha={sha} claimId={claimId} inDrawer /> : null}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
