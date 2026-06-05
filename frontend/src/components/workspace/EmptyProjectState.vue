<script setup lang="ts">
import { Database } from '@lucide/vue'
</script>

<template>
  <div class="flex min-h-0 items-center justify-center rounded-lg border bg-background">
    <div class="max-w-sm space-y-3 p-8 text-center">
      <div class="mx-auto flex size-11 items-center justify-center rounded-lg border bg-card">
        <Database class="size-5" />
      </div>
      <p class="text-base font-medium">打开一个项目</p>
      <p class="text-sm leading-6 text-muted-foreground">
        左侧新建或选择项目后，工作台会载入项目保存的章节、AI 抽取结果和剧本版本。
      </p>
    </div>
  </div>
</template>
