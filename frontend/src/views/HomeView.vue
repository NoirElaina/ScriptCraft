<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
  extractProjectStoryElements,
  generateProjectScriptYaml,
  getProjectWorkspace,
  listProjects,
  parseProjectChapters,
  updateProject,
  type AIRun,
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
const isExtracting = ref(false)
const isGeneratingYaml = ref(false)
const isDeletingProject = ref(false)
const isCheckingAuth = ref(true)
const isLoggingOut = ref(false)

const projectErrorMessage = ref('')
const workspaceErrorMessage = ref('')
const pipelineErrorMessage = ref('')

const currentProject = computed(() => workspace.value?.project)
const chapters = computed(() => workspace.value?.chapters ?? [])
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

const editorErrorMessage = computed(() => {
  return workspaceErrorMessage.value || pipelineErrorMessage.value
})

onMounted(() => {
  void restoreAuthSession()
})

async function restoreAuthSession() {
  if (!getAuthToken()) {
    isCheckingAuth.value = false
    return
  }

  try {
    currentUser.value = await getCurrentUser()
    await loadProjectList()
  } catch {
    resetWorkspace()
  } finally {
    isCheckingAuth.value = false
  }
}

async function handleAuthenticated(result: AuthTokenResponse) {
  currentUser.value = result.user
  resetWorkspace()
  await loadProjectList()
}

async function handleLogout() {
  isLoggingOut.value = true

  try {
    await logout()
  } finally {
    currentUser.value = undefined
    resetWorkspace()
    projects.value = []
    isLoggingOut.value = false
  }
}

function showAiRunHistory() {
  activeFlowTab.value = 'pipeline'
}

async function loadProjectList() {
  if (!currentUser.value) return

  projectErrorMessage.value = ''
  isLoadingProjects.value = true

  try {
    const result = await listProjects()
    projects.value = result.projects
  } catch (error) {
    projectErrorMessage.value = error instanceof Error ? error.message : '项目列表加载失败'
    if (projectErrorMessage.value.includes('登录')) {
      currentUser.value = undefined
      resetWorkspace()
    }
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

async function handleExtractStoryElements() {
  const project = currentProject.value
  if (!project) return

  pipelineErrorMessage.value = ''
  isExtracting.value = true

  try {
    await extractProjectStoryElements(project.id)
    await refreshWorkspace()
    activeFlowTab.value = 'pipeline'
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '故事元素抽取失败'
    await refreshWorkspace()
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
    await generateProjectScriptYaml(project.id)
    await refreshWorkspace()
    activeFlowTab.value = 'yaml'
    activeYamlTab.value = 'preview'
  } catch (error) {
    pipelineErrorMessage.value = error instanceof Error ? error.message : '剧本 YAML 生成失败'
    await refreshWorkspace()
  } finally {
    isGeneratingYaml.value = false
  }
}

function applyWorkspace(result: ProjectWorkspaceResponse) {
  workspace.value = result
  projectTitle.value = result.project.title
  novelText.value = normalizeNovelText(result.project.source_text)
  selectedChapterId.value = result.chapters[0]?.id
}

function clearDraftText() {
  novelText.value = ''
  pipelineErrorMessage.value = ''
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
            :chapter-coverage-label="chapterCoverageLabel"
          />

          <PipelinePanel
            v-model:active-flow-tab="activeFlowTab"
            v-model:active-yaml-tab="activeYamlTab"
            :chapters-length="chapters.length"
            :story-elements="storyElements"
            :script-yaml="scriptYaml"
            :script-version-name="scriptVersionName"
            :ai-runs="aiRuns"
            :is-loading-workspace="isLoadingWorkspace"
            :is-extracting="isExtracting"
            :is-generating-yaml="isGeneratingYaml"
            @refresh="refreshWorkspace"
            @extract-story-elements="handleExtractStoryElements"
            @generate-script-yaml="handleGenerateScriptYaml"
          />
        </div>
      </div>
    </section>
  </main>
</template>
