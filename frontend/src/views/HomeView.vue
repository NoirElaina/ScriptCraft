<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Loader2, Sparkles } from '@lucide/vue'

import {
  getCurrentUser,
  logout,
  type AuthTokenResponse,
  type AuthUser,
} from '@/api/auth'
import { getAuthToken } from '@/api/client'
import {
  createProject,
  deleteProject,
  getProjectWorkspace,
  listProjects,
  parseProjectChapters,
  saveProjectScriptVersion,
  startProjectChapterAnalysisJob,
  startProjectScriptYamlJob,
  startProjectStoryElementsJob,
  updateProject,
  type AIRun,
  type ChapterAnalysis,
  type ProjectListItem,
  type ProjectWorkspaceResponse,
  type StoryElementsSnapshot,
} from '@/api/projects'
import AuthPanel from '@/components/auth/AuthPanel.vue'
import UserAccountMenu from '@/components/auth/UserAccountMenu.vue'
import ChapterPanel from '@/components/workspace/ChapterPanel.vue'
import EmptyProjectState from '@/components/workspace/EmptyProjectState.vue'
import NovelEditorPanel from '@/components/workspace/NovelEditorPanel.vue'
import PipelinePanel from '@/components/workspace/PipelinePanel.vue'
import ProjectSwitcher from '@/components/workspace/ProjectSwitcher.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { normalizeNovelText } from '@/lib/novel-text'

interface ChapterAnalysisLogItem {
  id: string
  status: 'running' | 'succeeded' | 'failed'
  message: string
  createdAt: string
}

const ACTIVE_PROJECT_STORAGE_PREFIX = 'scriptcraft.activeProjectId'
const WORKSPACE_POLL_INTERVAL_MS = 1800

const currentUser = ref<AuthUser>()
const projects = ref<ProjectListItem[]>([])
const workspace = ref<ProjectWorkspaceResponse>()
const projectTitle = ref('未命名小说')
const newProjectTitle = ref('')
const novelText = ref('')
const selectedChapterId = ref<string>()
const activeFlowTab = ref('pipeline')
const activeYamlTab = ref('preview')

const isLoadingProjects = ref(false)
const isCreatingProject = ref(false)
const isLoadingWorkspace = ref(false)
const isSavingProject = ref(false)
const isParsing = ref(false)
const isAnalyzingChapters = ref(false)
const isExtracting = ref(false)
const isGeneratingYaml = ref(false)
const isSavingYaml = ref(false)
const isDeletingProject = ref(false)
const isCheckingAuth = ref(true)
const isLoggingOut = ref(false)

const projectErrorMessage = ref('')
const workspaceErrorMessage = ref('')
const pipelineErrorMessage = ref('')
const chapterAnalysisLogs = ref<ChapterAnalysisLogItem[]>([])

const currentProject = computed(() => workspace.value?.project)
const chapters = computed(() => workspace.value?.chapters ?? [])
const chapterAnalyses = computed<ChapterAnalysis[]>(() => workspace.value?.chapter_analyses ?? [])
const storyElements = computed<StoryElementsSnapshot | undefined>(() => {
  return workspace.value?.story_elements ?? undefined
})
const scriptYaml = computed(() => workspace.value?.script_version?.yaml_content ?? '')
const scriptVersionName = computed(() => workspace.value?.script_version?.version_name)
const aiRuns = computed<AIRun[]>(() => workspace.value?.ai_runs ?? [])
const storyElementsCountLabel = computed(() => {
  if (!storyElements.value) return '元素未抽取'
  return `角色 ${storyElements.value.characters.length} / 地点 ${storyElements.value.locations.length} / 事件 ${storyElements.value.events.length}`
})

const chapterCoverageLabel = computed(() => {
  if (chapters.value.length === 0) return '未解析'
  return chapters.value.length >= 3 ? '符合 3 章要求' : '章节不足'
})

const chapterAnalysisLabel = computed(() => {
  if (chapters.value.length === 0) return '无章节分析'
  return `章节分析 ${chapterAnalyses.value.length}/${chapters.value.length}`
})
const isBackendAnalyzingChapters = computed(() => {
  return (
    currentProject.value?.status === 'chapter_analysis_running' ||
    aiRuns.value.some((run) => run.task_type === 'chapter_analysis' && run.status === 'running')
  )
})
const isBackendExtractingStoryElements = computed(() => {
  return (
    currentProject.value?.status === 'story_elements_running' ||
    aiRuns.value.some((run) => run.task_type === 'story_elements' && run.status === 'running')
  )
})
const isBackendGeneratingScriptYaml = computed(() => {
  return (
    currentProject.value?.status === 'script_yaml_running' ||
    aiRuns.value.some((run) => run.task_type === 'script_yaml' && run.status === 'running')
  )
})
const isChapterAnalysisBusy = computed(() => isAnalyzingChapters.value || isBackendAnalyzingChapters.value)
const isStoryElementsBusy = computed(() => isExtracting.value || isBackendExtractingStoryElements.value)
const isScriptYamlBusy = computed(() => isGeneratingYaml.value || isBackendGeneratingScriptYaml.value)
const isLocalAiTaskRunning = computed(() => {
  return isAnalyzingChapters.value || isExtracting.value || isGeneratingYaml.value
})
const isBackendAiTaskRunning = computed(() => {
  return (
    isBackendAnalyzingChapters.value ||
    isBackendExtractingStoryElements.value ||
    isBackendGeneratingScriptYaml.value
  )
})
const isAiTaskRunning = computed(() => isLocalAiTaskRunning.value || isBackendAiTaskRunning.value)

const editorErrorMessage = computed(() => {
  return workspaceErrorMessage.value || pipelineErrorMessage.value
})

let workspacePollTimer: number | undefined
const isPollingWorkspace = ref(false)

onMounted(() => {
  void restoreAuthSession()
})

onBeforeUnmount(() => {
  stopWorkspacePolling()
})

watch(
  [() => currentProject.value?.id, isBackendAiTaskRunning],
  ([projectId, isRunning]) => {
    stopWorkspacePolling()
    if (projectId && isRunning) {
      startWorkspacePolling(projectId)
    }
  },
  { immediate: true },
)

async function restoreAuthSession() {
  if (!getAuthToken()) {
    isCheckingAuth.value = false
    return
  }

  try {
    currentUser.value = await getCurrentUser()
    const loadedProjects = await loadProjectList()
    await restoreActiveProject(loadedProjects)
  } catch {
    resetWorkspace()
  } finally {
    isCheckingAuth.value = false
  }
}

async function handleAuthenticated(result: AuthTokenResponse) {
  currentUser.value = result.user
  resetWorkspace()
  const loadedProjects = await loadProjectList()
  await restoreActiveProject(loadedProjects)
}

async function handleLogout() {
  isLoggingOut.value = true

  try {
    await logout()
  } finally {
    forgetActiveProject()
    currentUser.value = undefined
    resetWorkspace()
    projects.value = []
    isLoggingOut.value = false
  }
}

function showAiRunHistory() {
  activeFlowTab.value = 'pipeline'
}

async function loadProjectList(): Promise<ProjectListItem[]> {
  if (!currentUser.value) return []

  projectErrorMessage.value = ''
  isLoadingProjects.value = true

  try {
    const result = await listProjects()
    projects.value = result.projects
    return result.projects
  } catch (error) {
    projectErrorMessage.value = error instanceof Error ? error.message : '项目列表加载失败'
    if (projectErrorMessage.value.includes('登录')) {
      currentUser.value = undefined
      resetWorkspace()
    }
    return []
  } finally {
    isLoadingProjects.value = false
  }
}

async function handleCreateProject() {
  projectErrorMessage.value = ''
  isCreatingProject.value = true

  try {
    const project = await createProject(newProjectTitle.value.trim() || '未命名小说')
    newProjectTitle.value = ''
    await loadProjectList()
    await openProject(project.id)
  } catch (error) {
    projectErrorMessage.value = error instanceof Error ? error.message : '项目创建失败'
  } finally {
    isCreatingProject.value = false
  }
}

async function openProject(projectId: number) {
  workspaceErrorMessage.value = ''
  pipelineErrorMessage.value = ''
  isLoadingWorkspace.value = true

  try {
    const result = await getProjectWorkspace(projectId)
    applyWorkspace(result)
    rememberActiveProject(result.project.id)
  } catch (error) {
    workspaceErrorMessage.value = error instanceof Error ? error.message : '项目打开失败'
  } finally {
    isLoadingWorkspace.value = false
  }
}

async function refreshWorkspace() {
  const projectId = currentProject.value?.id
  if (!projectId) return

  await openProject(projectId)
  await loadProjectList()
}

async function refreshWorkspaceSnapshot(projectId: number) {
  if (!currentUser.value || isPollingWorkspace.value) return

  isPollingWorkspace.value = true
  try {
    const result = await getProjectWorkspace(projectId)
    if (currentProject.value?.id === projectId || !currentProject.value) {
      applyWorkspace(result, { preserveSelectedChapter: true })
      rememberActiveProject(result.project.id)
    }
    await loadProjectList()
  } catch (error) {
    workspaceErrorMessage.value = error instanceof Error ? error.message : '工作台状态同步失败'
  } finally {
    isPollingWorkspace.value = false
  }
}

function startWorkspacePolling(projectId: number) {
  stopWorkspacePolling()
  workspacePollTimer = window.setInterval(() => {
    void refreshWorkspaceSnapshot(projectId)
  }, WORKSPACE_POLL_INTERVAL_MS)
}

function stopWorkspacePolling() {
  if (!workspacePollTimer) return

  window.clearInterval(workspacePollTimer)
  workspacePollTimer = undefined
}

async function handleSaveProject() {
  const project = currentProject.value
  if (!project) return

  workspaceErrorMessage.value = ''
  isSavingProject.value = true

  try {
    const sourceText = tidyDraftText()
    const updatedProject = await updateProject(project.id, {
      title: projectTitle.value.trim() || '未命名小说',
      source_text: sourceText,
    })
    workspace.value = workspace.value ? { ...workspace.value, project: updatedProject } : workspace.value
    projectTitle.value = updatedProject.title
    await loadProjectList()
  } catch (error) {
    workspaceErrorMessage.value = error instanceof Error ? error.message : '项目保存失败'
  } finally {
    isSavingProject.value = false
  }
}

async function handleDeleteProject(project: ProjectListItem) {
  if (!window.confirm(`删除项目「${project.title}」？`)) return

  projectErrorMessage.value = ''
  isDeletingProject.value = true

  try {
    await deleteProject(project.id)
    if (currentProject.value?.id === project.id) {
      forgetActiveProject(project.id)
      workspace.value = undefined
      projectTitle.value = '未命名小说'
      novelText.value = ''
      selectedChapterId.value = undefined
    }
    await loadProjectList()
  } catch (error) {
    projectErrorMessage.value = error instanceof Error ? error.message : '项目删除失败'
  } finally {
    isDeletingProject.value = false
  }
}

async function handleParseProjectChapters() {
  const project = currentProject.value
  if (!project) return

  workspaceErrorMessage.value = ''
  pipelineErrorMessage.value = ''
  isParsing.value = true

  try {
    const sourceText = tidyDraftText()
    await updateProject(project.id, {
      title: projectTitle.value.trim() || '未命名小说',
      source_text: sourceText,
    })
    const result = await parseProjectChapters(project.id, sourceText)
    selectedChapterId.value = result.chapters[0]?.id
    await refreshWorkspace()
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '章节解析失败'
  } finally {
    isParsing.value = false
  }
}

async function handleAnalyzeProjectChapters() {
  const project = currentProject.value
  if (!project) return

  pipelineErrorMessage.value = ''
  chapterAnalysisLogs.value = []
  isAnalyzingChapters.value = true
  activeFlowTab.value = 'pipeline'

  try {
    const result = await startProjectChapterAnalysisJob(project.id)
    appendChapterAnalysisLog('running', `章节分析任务已启动：${result.ai_run.status}`)
    await refreshWorkspaceSnapshot(project.id)
    startWorkspacePolling(project.id)
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '章节分析失败'
  } finally {
    isAnalyzingChapters.value = false
  }
}

async function handleExtractStoryElements() {
  const project = currentProject.value
  if (!project) return

  pipelineErrorMessage.value = ''
  isExtracting.value = true
  activeFlowTab.value = 'pipeline'

  try {
    await startProjectStoryElementsJob(project.id)
    await refreshWorkspaceSnapshot(project.id)
    startWorkspacePolling(project.id)
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '故事元素抽取失败'
  } finally {
    isExtracting.value = false
  }
}

async function handleGenerateScriptYaml() {
  const project = currentProject.value
  if (!project) return

  pipelineErrorMessage.value = ''
  isGeneratingYaml.value = true

  try {
    await startProjectScriptYamlJob(project.id)
    await refreshWorkspaceSnapshot(project.id)
    startWorkspacePolling(project.id)
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '剧本 YAML 生成失败'
  } finally {
    isGeneratingYaml.value = false
  }
}

async function handleSaveScriptYaml(yamlContent: string, versionName: string) {
  const project = currentProject.value
  if (!project) return

  pipelineErrorMessage.value = ''
  isSavingYaml.value = true

  try {
    const result = await saveProjectScriptVersion(project.id, {
      version_name: versionName,
      yaml_content: yamlContent,
    })
    if (workspace.value && workspace.value.project.id === project.id) {
      workspace.value = { ...workspace.value, script_version: result.script_version }
    }
    activeFlowTab.value = 'yaml'
    activeYamlTab.value = 'preview'
    await loadProjectList()
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '剧本 YAML 保存失败'
  } finally {
    isSavingYaml.value = false
  }
}

function applyWorkspace(
  result: ProjectWorkspaceResponse,
  options: { preserveSelectedChapter?: boolean } = {},
) {
  const previousSelectedChapterId = selectedChapterId.value
  workspace.value = result
  projectTitle.value = result.project.title
  novelText.value = normalizeNovelText(result.project.source_text)
  selectedChapterId.value =
    options.preserveSelectedChapter &&
    previousSelectedChapterId &&
    result.chapters.some((chapter) => chapter.id === previousSelectedChapterId)
      ? previousSelectedChapterId
      : result.chapters[0]?.id

  syncChapterAnalysisLogs(result)
}

function syncChapterAnalysisLogs(result: ProjectWorkspaceResponse) {
  const latestChapterAnalysisRun = result.ai_runs.find((run) => run.task_type === 'chapter_analysis')
  if (!latestChapterAnalysisRun) return

  const isRunning =
    result.project.status === 'chapter_analysis_running' || latestChapterAnalysisRun.status === 'running'
  if (!isRunning) {
    if (latestChapterAnalysisRun.status === 'succeeded') {
      chapterAnalysisLogs.value = [
        ...result.chapter_analyses.map((analysis) => chapterAnalysisLogFromRecord(analysis)),
        {
          id: `run-${latestChapterAnalysisRun.id}-succeeded`,
          status: 'succeeded',
          message: '全部章节分析完成',
          createdAt: latestChapterAnalysisRun.created_at,
        },
      ]
    }
    if (latestChapterAnalysisRun.status === 'failed') {
      chapterAnalysisLogs.value = [
        ...result.chapter_analyses.map((analysis) => chapterAnalysisLogFromRecord(analysis)),
        {
          id: `run-${latestChapterAnalysisRun.id}-failed`,
          status: 'failed',
          message: latestChapterAnalysisRun.error_message || '章节分析失败',
          createdAt: latestChapterAnalysisRun.created_at,
        },
      ]
    }
    return
  }

  chapterAnalysisLogs.value = [
    ...result.chapter_analyses.map((analysis) => chapterAnalysisLogFromRecord(analysis)),
    {
      id: `run-${latestChapterAnalysisRun.id}-running-${result.chapter_analyses.length}`,
      status: 'running',
      message: `章节分析进行中：已完成 ${result.chapter_analyses.length}/${result.chapters.length} 章`,
      createdAt: latestChapterAnalysisRun.created_at,
    },
  ]
}

function chapterAnalysisLogFromRecord(analysis: ChapterAnalysis): ChapterAnalysisLogItem {
  return {
    id: `analysis-${analysis.id}`,
    status: 'succeeded',
    message: `第 ${analysis.chapter_index} 章分析完成`,
    createdAt: analysis.updated_at,
  }
}

function appendChapterAnalysisLog(status: ChapterAnalysisLogItem['status'], message: string) {
  chapterAnalysisLogs.value = [
    ...chapterAnalysisLogs.value,
    {
      id: `${Date.now()}-${chapterAnalysisLogs.value.length}`,
      status,
      message,
      createdAt: new Date().toISOString(),
    },
  ]
}

function clearDraftText() {
  novelText.value = ''
  pipelineErrorMessage.value = ''
  chapterAnalysisLogs.value = []
}

function tidyDraftText(): string {
  const sourceText = normalizeNovelText(novelText.value)
  novelText.value = sourceText
  return sourceText
}

function resetWorkspace() {
  workspace.value = undefined
  projectTitle.value = '未命名小说'
  newProjectTitle.value = ''
  novelText.value = ''
  selectedChapterId.value = undefined
  activeFlowTab.value = 'pipeline'
  activeYamlTab.value = 'preview'
  projectErrorMessage.value = ''
  workspaceErrorMessage.value = ''
  pipelineErrorMessage.value = ''
}

async function restoreActiveProject(projectList: ProjectListItem[]) {
  if (!currentUser.value || projectList.length === 0 || currentProject.value) return

  const projectId = readRememberedProjectId()
  if (projectId && projectList.some((project) => project.id === projectId)) {
    await openProject(projectId)
    return
  }

  if (projectId) {
    forgetActiveProject(projectId)
  }

  if (projectList.length === 1) {
    const onlyProject = projectList[0]
    if (onlyProject) {
      await openProject(onlyProject.id)
    }
  }
}

function activeProjectStorageKey(): string | undefined {
  return currentUser.value ? `${ACTIVE_PROJECT_STORAGE_PREFIX}.${currentUser.value.id}` : undefined
}

function readRememberedProjectId(): number | undefined {
  const key = activeProjectStorageKey()
  if (!key) return undefined

  const rawValue = window.localStorage.getItem(key)
  const projectId = rawValue ? Number(rawValue) : Number.NaN
  return Number.isInteger(projectId) && projectId > 0 ? projectId : undefined
}

function rememberActiveProject(projectId: number) {
  const key = activeProjectStorageKey()
  if (!key) return

  window.localStorage.setItem(key, String(projectId))
}

function forgetActiveProject(projectId?: number) {
  const key = activeProjectStorageKey()
  if (!key) return

  if (projectId && readRememberedProjectId() !== projectId) return

  window.localStorage.removeItem(key)
}
</script>

<template>
  <main class="h-screen overflow-hidden bg-muted/30 text-foreground">
    <section
      class="mx-auto flex h-full w-full max-w-[1700px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8"
    >
      <header
        class="shrink-0 flex flex-col gap-3 border-b bg-background/80 pb-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="flex items-center gap-3">
          <div class="flex size-9 items-center justify-center rounded-lg border bg-card">
            <Sparkles class="size-4" />
          </div>
          <div>
            <h1 class="text-xl font-semibold tracking-normal">ScriptCraft</h1>
            <p class="text-sm text-muted-foreground">AI 小说转剧本工作台</p>
          </div>
        </div>
        <div v-if="currentUser" class="flex flex-col items-stretch gap-2 sm:items-end">
          <div class="flex flex-wrap items-center justify-end gap-2">
            <ProjectSwitcher
              v-model:new-project-title="newProjectTitle"
              :projects="projects"
              :current-project-id="currentProject?.id"
              :current-project-title="currentProject?.title"
              :is-loading-projects="isLoadingProjects"
              :is-creating-project="isCreatingProject"
              :is-deleting-project="isDeletingProject"
              :error-message="projectErrorMessage"
              @refresh="loadProjectList"
              @create="handleCreateProject"
              @open="openProject"
              @delete-project="handleDeleteProject"
            />
            <UserAccountMenu
              :user="currentUser"
              :is-logging-out="isLoggingOut"
              @show-runs="showAiRunHistory"
              @logout="handleLogout"
            />
          </div>
          <div class="flex flex-wrap justify-end gap-2">
            <Badge variant="secondary">{{ projects.length }} 个项目</Badge>
            <Badge variant="outline">{{ chapters.length }} 章</Badge>
            <Badge variant="outline">{{ chapterAnalysisLabel }}</Badge>
            <Badge variant="outline">{{ storyElementsCountLabel }}</Badge>
            <Badge variant="outline">{{ scriptVersionName ?? '无剧本版本' }}</Badge>
          </div>
        </div>
      </header>

      <div class="min-h-0 flex-1">
        <div v-if="isCheckingAuth" class="flex h-full items-center justify-center">
          <Loader2 class="size-6 animate-spin text-muted-foreground" />
        </div>

        <div v-else-if="!currentUser" class="flex h-full items-center justify-center">
          <AuthPanel @authenticated="handleAuthenticated" />
        </div>

        <EmptyProjectState v-else-if="!currentProject" />

        <div v-else class="grid h-full min-h-0 gap-4 xl:grid-cols-[420px_minmax(0,1fr)_420px]">
          <NovelEditorPanel
            v-model:project-title="projectTitle"
            v-model:novel-text="novelText"
            :current-project-title="currentProject.title"
            :error-message="editorErrorMessage"
            :is-loading-workspace="isLoadingWorkspace"
            :is-parsing="isParsing"
            :is-saving-project="isSavingProject"
            @parse-chapters="handleParseProjectChapters"
            @save-project="handleSaveProject"
            @clear-draft="clearDraftText"
          />

          <ChapterPanel
            v-model:selected-chapter-id="selectedChapterId"
            :chapters="chapters"
            :chapter-analyses="chapterAnalyses"
            :chapter-coverage-label="chapterCoverageLabel"
          />

          <PipelinePanel
            v-model:active-flow-tab="activeFlowTab"
            v-model:active-yaml-tab="activeYamlTab"
            :chapters-length="chapters.length"
            :chapter-analyses-length="chapterAnalyses.length"
            :story-elements="storyElements"
            :script-yaml="scriptYaml"
            :project-title="currentProject.title"
            :script-version-name="scriptVersionName"
            :ai-runs="aiRuns"
            :chapter-analysis-logs="chapterAnalysisLogs"
            :is-loading-workspace="isLoadingWorkspace"
            :is-analyzing-chapters="isChapterAnalysisBusy"
            :is-extracting="isStoryElementsBusy"
            :is-generating-yaml="isScriptYamlBusy"
            :is-ai-task-running="isAiTaskRunning"
            :is-saving-yaml="isSavingYaml"
            @refresh="refreshWorkspace"
            @analyze-chapters="handleAnalyzeProjectChapters"
            @extract-story-elements="handleExtractStoryElements"
            @generate-script-yaml="handleGenerateScriptYaml"
            @save-script-yaml="handleSaveScriptYaml"
          />
        </div>
      </div>
    </section>
  </main>
</template>
