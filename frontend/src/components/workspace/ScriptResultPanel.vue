<script setup lang="ts">
import { FileCode2, Loader2, RefreshCw } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import ScriptYamlPanel from './ScriptYamlPanel.vue'

defineProps<{
  scriptYaml: string
  projectTitle: string
  scriptVersionName?: string
  hasStoryElements: boolean
  isGeneratingYaml: boolean
  isSavingYaml: boolean
  isRepairingYaml: boolean
  isLoadingWorkspace: boolean
  errorMessage?: string
  repairedYamlContent?: string
  repairedYamlRevision?: number
}>()

const activeYamlTab = defineModel<string>('activeYamlTab', { required: true })

const emit = defineEmits<{
  refresh: []
  generateScriptYaml: []
  saveScriptYaml: [yamlContent: string, versionName: string]
  repairScriptYaml: [yamlContent: string, validationError: string]
}>()
</script>

<template>
  <Card class="flex min-h-0 flex-col overflow-hidden">
    <CardHeader class="shrink-0">
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle class="flex items-center gap-2 text-base">
            <FileCode2 class="size-4" />
            剧本结果
          </CardTitle>
          <CardDescription>查看、编辑、导出和预演生成后的 YAML 剧本。</CardDescription>
        </div>
        <Button size="sm" variant="outline" :disabled="isLoadingWorkspace" @click="emit('refresh')">
          <Loader2 v-if="isLoadingWorkspace" class="size-4 animate-spin" />
          <RefreshCw v-else class="size-4" />
        </Button>
      </div>
    </CardHeader>

    <CardContent class="min-h-0 flex-1 overflow-hidden">
      <ScriptYamlPanel
        v-model:active-yaml-tab="activeYamlTab"
        :script-yaml="scriptYaml"
        :project-title="projectTitle"
        :script-version-name="scriptVersionName"
        :has-story-elements="hasStoryElements"
        :is-generating-yaml="isGeneratingYaml"
        :is-saving-yaml="isSavingYaml"
        :is-repairing-yaml="isRepairingYaml"
        :error-message="errorMessage"
        :repaired-yaml-content="repairedYamlContent"
        :repaired-yaml-revision="repairedYamlRevision"
        @generate="emit('generateScriptYaml')"
        @save="(yamlContent, versionName) => emit('saveScriptYaml', yamlContent, versionName)"
        @repair="(yamlContent, validationError) => emit('repairScriptYaml', yamlContent, validationError)"
      />
    </CardContent>
  </Card>
</template>
