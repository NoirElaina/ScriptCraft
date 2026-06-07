export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: '草稿',
    chapters_ready: '章节完成',
    chapter_analysis_running: '章节分析中',
    chapter_analysis_failed: '章节分析失败',
    chapter_analyses_ready: '章节分析完成',
    story_elements_running: '元素抽取中',
    story_elements_failed: '元素抽取失败',
    story_elements_ready: '元素完成',
    script_yaml_running: '剧本生成中',
    script_yaml_failed: '剧本生成失败',
    script_ready: '剧本完成',
  }
  return labels[status] ?? status
}

export function taskLabel(taskType: string): string {
  const labels: Record<string, string> = {
    chapter_analysis: '章节分析',
    story_elements: '故事元素',
    script_yaml: '剧本 YAML',
    script_yaml_repair: '剧本 YAML 修复',
  }
  return labels[taskType] ?? taskType
}

export function runStatusClass(status: string): string {
  const classes: Record<string, string> = {
    succeeded: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    failed: 'border-destructive/30 bg-destructive/10 text-destructive',
    running: 'border-sky-200 bg-sky-50 text-sky-700',
  }
  return classes[status] ?? 'border-muted bg-muted text-muted-foreground'
}

export function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
