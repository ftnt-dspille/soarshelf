<script lang="ts">
  import { STATUS_LABEL, type SubmissionStatus } from '$lib/api';
  let { status }: { status: SubmissionStatus } = $props();
  const TONE: Record<SubmissionStatus, string> = {
    checking: 'bg-info-soft text-info',
    rejected: 'bg-block-soft text-block',
    'in-review': 'bg-warn-soft text-warn',
    publishing: 'bg-accent-soft text-accent-text',
    published: 'bg-ok-soft text-ok',
    error: 'bg-block-soft text-block'
  };
</script>

<span class="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium {TONE[status]}">
  <span class="size-1.5 rounded-full bg-current {status === 'checking' || status === 'publishing' ? 'animate-pulse' : ''}" aria-hidden="true"></span>
  {STATUS_LABEL[status]}
</span>
