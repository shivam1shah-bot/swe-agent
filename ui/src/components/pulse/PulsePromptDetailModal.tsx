import { fmtCost, fmtTokens, fmtTime, modelShort } from '@/types/pulse'
import { PulseTag } from './PulseTag'
import { PulseTokenBreakdownChart } from './PulseTokenBreakdownChart'
import { Dialog, DialogContent, DialogTitle, DialogClose } from '@/components/ui/dialog'
import type { PulsePromptDetail } from '@/types/pulse'

interface PulsePromptDetailModalProps {
  prompt: (PulsePromptDetail & { branch?: string }) | null
  open: boolean
  onClose: () => void
}

export function PulsePromptDetailModal({ prompt, open, onClose }: PulsePromptDetailModalProps) {
  const hasTokenBreakdown = prompt
    ? (prompt.input_tokens || 0) + (prompt.output_tokens || 0) +
      (prompt.cache_read_tokens || 0) + (prompt.cache_creation_tokens || 0) > 0
    : false

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }} containerClassName="max-w-none w-[min(720px,92vw)]">
      <DialogContent className="rounded-2xl p-7 relative">
        {prompt ? (
          <>
            {/* Close button */}
            <DialogClose
              onClick={onClose}
              className="absolute top-4 right-4 w-7 h-7 rounded-md bg-muted border border-border text-muted-foreground flex items-center justify-center hover:bg-accent hover:text-foreground transition-all cursor-pointer opacity-100"
            />

            {/* Title */}
            <DialogTitle className="text-base mb-1.5 pr-10 leading-relaxed">
              {prompt.prompt}
            </DialogTitle>

            {/* Meta tags */}
            <div className="flex items-center gap-2 mb-5 flex-wrap">
              {prompt.turn_type && <PulseTag type={prompt.turn_type} />}
              {prompt.model && <PulseTag type="model">{modelShort(prompt.model)}</PulseTag>}
              <span className="font-mono text-[11px] text-muted-foreground">
                {prompt.repo && `${prompt.repo}`}
                {prompt.branch && ` \u00b7 ${prompt.branch}`}
                {prompt.author && ` \u00b7 ${prompt.author}`}
                {prompt.timestamp && ` \u00b7 ${fmtTime(prompt.timestamp)}`}
              </span>
            </div>

            {/* Token Breakdown */}
            <div className="mb-5">
              <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.1em] mb-2">
                Token Breakdown
              </h3>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Total Tokens', val: prompt.total_tokens ? fmtTokens(prompt.total_tokens) : '\u2014' },
                  { label: 'Cost', val: fmtCost(prompt.cost_usd || 0), color: 'text-amber-500' },
                  { label: 'Input Tokens', val: hasTokenBreakdown ? fmtTokens(prompt.input_tokens || 0) : '\u2014' },
                  { label: 'Output Tokens', val: hasTokenBreakdown ? fmtTokens(prompt.output_tokens || 0) : '\u2014', color: hasTokenBreakdown ? 'text-green-500' : '' },
                  { label: 'Cache Read', val: hasTokenBreakdown ? fmtTokens(prompt.cache_read_tokens || 0) : '\u2014' },
                  { label: 'Cache Creation', val: hasTokenBreakdown ? fmtTokens(prompt.cache_creation_tokens || 0) : '\u2014' },
                ].map(t => (
                  <div key={t.label} className="bg-muted rounded-lg p-3">
                    <div className="text-[10px] text-muted-foreground mb-1">{t.label}</div>
                    <div className={`font-mono text-base font-semibold ${t.color || 'text-foreground'}`}>
                      {t.val}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Token chart */}
            {hasTokenBreakdown && (
              <div className="mb-5">
                <PulseTokenBreakdownChart
                  input={prompt.input_tokens}
                  output={prompt.output_tokens}
                  cacheRead={prompt.cache_read_tokens}
                  cacheCreation={prompt.cache_creation_tokens}
                />
              </div>
            )}

            {/* AI Response Preview */}
            {prompt.assistant_preview?.trim() && (
              <div className="mb-5">
                <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.1em] mb-2">
                  AI Response Preview
                </h3>
                <div className="bg-muted rounded-lg p-3.5 text-xs text-muted-foreground leading-relaxed border-l-[3px] border-l-blue-500">
                  {prompt.assistant_preview}
                </div>
              </div>
            )}

            {/* Details */}
            <div>
              <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.1em] mb-2">
                Details
              </h3>
              <div className="flex flex-wrap gap-2 text-xs">
                {prompt.tools_used && prompt.tools_used.length > 0 && (
                  <span className="text-muted-foreground">Tools: {prompt.tools_used.join(', ')}</span>
                )}
                {prompt.skill_invoked && (
                  <span className="text-purple-500">Skill: {prompt.skill_invoked}</span>
                )}
              </div>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
