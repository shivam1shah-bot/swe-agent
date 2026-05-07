import { fmtCost, fmtTokens } from '@/types/pulse'
import { Dialog, DialogContent, DialogTitle, DialogClose } from '@/components/ui/dialog'
import type { PulseContributor } from '@/types/pulse'

interface PulseContributorsModalProps {
  repo: string
  contributors: PulseContributor[] | undefined
  open: boolean
  onClose: () => void
}

export function PulseContributorsModal({ repo, contributors, open, onClose }: PulseContributorsModalProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }} containerClassName="max-w-none w-[min(560px,92vw)]">
      <DialogContent className="rounded-2xl p-7 relative">
        {/* Close button */}
        <DialogClose
          onClick={onClose}
          className="absolute top-4 right-4 w-7 h-7 rounded-md bg-muted border border-border text-muted-foreground flex items-center justify-center hover:bg-accent hover:text-foreground transition-all cursor-pointer opacity-100"
        />

        <DialogTitle className="text-base mb-1 pr-10">
          Contributors
        </DialogTitle>
        <p className="text-[11px] text-muted-foreground mb-5 font-mono">{repo}</p>

        {contributors?.length ? (
          <div className="bg-muted rounded-xl overflow-hidden border border-border">
            <div className="grid grid-cols-[1fr_80px_90px_80px] px-4 py-2.5 border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
              <span>Email</span>
              <span className="text-right">Prompts</span>
              <span className="text-right">Tokens</span>
              <span className="text-right">Cost</span>
            </div>
            {contributors.map((c) => (
              <div
                key={c.email}
                className="grid grid-cols-[1fr_80px_90px_80px] items-center px-4 py-3 border-b border-border last:border-b-0"
              >
                <div className="text-sm text-foreground truncate">{c.email}</div>
                <div className="font-mono text-sm text-foreground text-right">{c.prompts}</div>
                <div className="font-mono text-sm text-blue-500 text-right">{fmtTokens(c.tokens)}</div>
                <div className="font-mono text-sm font-semibold text-amber-500 text-right">{fmtCost(c.cost_usd)}</div>
              </div>
            ))}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
