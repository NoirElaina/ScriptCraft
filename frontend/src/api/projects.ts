import type { Chapter } from './chapters'
import { getAuthToken, requestJson } from './client'
import type { StoryCharacter, StoryEvent, StoryLocation } from './story-elements'

export interface Project {
  id: number
  owner_id: number | null
  title: string
  description: string
  status: string
  source_text: string
  created_at: string
  updated_at: string
}

export interface ProjectListItem {
  id: number
  owner_id: number | null
  title: string
  description: string
  status: string
  created_at: string
  updated_at: string
  chapter_count: number
  script_version_count: number
}

export interface ProjectListResponse {
  projects: ProjectListItem[]
}

export interface ProjectChaptersResponse {
  project_id: number
  title: string
  chapter_count: number
  chapters: Chapter[]
}

export interface ChapterAnalysis {
  id: number
  project_id: number
  chapter_id: number
  chapter_key: string
  chapter_index: number
  summary: string
  analysis: {
    chapter_id: string
    chapter_index: number
    heading: string
    title: string
    summary: string
    characters: Array<{
      name: string
      aliases: string[]
      role_in_chapter: string
      evidence: string
    }>
    locations: Array<{
      name: string
      description: string
      evidence: string
    }>
    events: Array<{
      summary: string
      event_type: string
      involved_characters: string[]
      evidence: string
    }>
    conflicts: string[]
    dialogue_candidates: string[]
    scene_candidates: Array<{
      title: string
      location: string
      characters: string[]
      summary: string
      dramatic_purpose: string
      beats: string[]
    }>
    continuity_notes: string[]
  }
  created_at: string
  updated_at: string
}

export interface ProjectChapterAnalysesResponse {
  project_id: number
  title: string
  ai_run_id: number
  chapter_analyses: ChapterAnalysis[]
}

export interface ChapterAnalysisStreamChapter {
  id: string
  index: number
  heading: string
  title: string
}

export type ChapterAnalysisStreamEvent =
  | {
      type: 'started'
      project_id: number
      title: string
      ai_run_id: number
      total: number
      message: string
    }
  | {
      type: 'chapter_started'
      project_id: number
      ai_run_id: number
      chapter: ChapterAnalysisStreamChapter
      progress: { current: number; total: number }
      message: string
    }
  | {
      type: 'chapter_completed'
      project_id: number
      ai_run_id: number
      chapter_analysis: ChapterAnalysis
      progress: { current: number; total: number }
      message: string
    }
  | {
      type: 'completed'
      project_id: number
      title: string
      ai_run_id: number
      chapter_analyses: ChapterAnalysis[]
      message: string
    }
  | {
      type: 'error'
      project_id?: number
      ai_run_id?: number
      status_code?: number
      message: string
    }

export interface StoryElementsSnapshot {
  id: number
  project_id: number
  characters: StoryCharacter[]
  locations: StoryLocation[]
  events: StoryEvent[]
  created_at: string
}

export interface ProjectStoryElementsResponse {
  project_id: number
  title: string
  ai_run_id: number
  story_elements: StoryElementsSnapshot
}

export interface ScriptVersion {
  id: number
  project_id: number
  version_name: string
  schema_version: string
  yaml_content: string
  created_at: string
  updated_at: string
}

export interface AIRun {
  id: number
  project_id: number | null
  task_type: string
  provider: string
  model: string
  status: string
  error_message: string
  duration_ms: number | null
  created_at: string
}

export interface ProjectScriptYamlResponse {
  project_id: number
  title: string
  ai_run_id: number
  script_version: ScriptVersion
}

export interface ProjectScriptVersionResponse {
  project_id: number
  title: string
  script_version: ScriptVersion
}

export interface ProjectWorkspaceResponse {
  project: Project
  chapters: Chapter[]
  chapter_analyses: ChapterAnalysis[]
  story_elements: StoryElementsSnapshot | null
  script_version: ScriptVersion | null
  ai_runs: AIRun[]
}

export async function listProjects(): Promise<ProjectListResponse> {
  return requestJson('/api/projects')
}

export async function createProject(title: string): Promise<Project> {
  return requestJson('/api/projects', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function updateProject(
  projectId: number,
  payload: Partial<Pick<Project, 'title' | 'description' | 'status' | 'source_text'>>,
): Promise<Project> {
  return requestJson(`/api/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteProject(projectId: number): Promise<void> {
  await requestJson(`/api/projects/${projectId}`, { method: 'DELETE' })
}

export async function getProjectWorkspace(projectId: number): Promise<ProjectWorkspaceResponse> {
  return requestJson(`/api/projects/${projectId}/workspace`)
}

export async function parseProjectChapters(
  projectId: number,
  sourceText: string,
): Promise<ProjectChaptersResponse> {
  return requestJson(`/api/projects/${projectId}/chapters`, {
    method: 'POST',
    body: JSON.stringify({ source_text: sourceText }),
  })
}

export async function extractProjectStoryElements(
  projectId: number,
): Promise<ProjectStoryElementsResponse> {
  return requestJson(`/api/projects/${projectId}/story-elements`, { method: 'POST' })
}

export async function analyzeProjectChapters(
  projectId: number,
): Promise<ProjectChapterAnalysesResponse> {
  return requestJson(`/api/projects/${projectId}/chapter-analyses`, { method: 'POST' })
}

export async function streamProjectChapterAnalyses(
  projectId: number,
  onEvent: (event: ChapterAnalysisStreamEvent) => void,
): Promise<void> {
  const token = getAuthToken()
  const response = await fetch(`/api/projects/${projectId}/chapter-analyses/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }
  if (!response.body) {
    throw new Error('浏览器不支持读取 AI 实时事件流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    buffer = consumeSseBuffer(buffer, onEvent)
  }

  buffer += decoder.decode()
  consumeSseBuffer(`${buffer}\n\n`, onEvent)
}

export async function generateProjectScriptYaml(
  projectId: number,
): Promise<ProjectScriptYamlResponse> {
  return requestJson(`/api/projects/${projectId}/script-yaml`, { method: 'POST' })
}

export async function saveProjectScriptVersion(
  projectId: number,
  payload: { version_name: string; yaml_content: string },
): Promise<ProjectScriptVersionResponse> {
  return requestJson(`/api/projects/${projectId}/script-versions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

async function readErrorMessage(response: Response): Promise<string> {
  const text = await response.text()
  if (!text) return '请求失败'

  try {
    const payload = JSON.parse(text) as { detail?: string }
    return payload.detail ?? text
  } catch {
    return text
  }
}

function consumeSseBuffer(
  buffer: string,
  onEvent: (event: ChapterAnalysisStreamEvent) => void,
): string {
  let remaining = buffer
  let boundary = remaining.indexOf('\n\n')

  while (boundary !== -1) {
    const rawMessage = remaining.slice(0, boundary)
    remaining = remaining.slice(boundary + 2)
    const event = parseSseMessage(rawMessage)
    if (event) {
      onEvent(event)
      if (event.type === 'error') {
        throw new Error(event.message)
      }
    }
    boundary = remaining.indexOf('\n\n')
  }

  return remaining
}

function parseSseMessage(rawMessage: string): ChapterAnalysisStreamEvent | undefined {
  const dataLines = rawMessage
    .replace(/\r\n/g, '\n')
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())

  if (dataLines.length === 0) return undefined

  return JSON.parse(dataLines.join('\n')) as ChapterAnalysisStreamEvent
}
