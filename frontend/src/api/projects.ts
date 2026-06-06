import type { Chapter } from './chapters'
import { requestJson } from './client'

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

export interface ProjectAITaskJobResponse {
  project_id: number
  title: string
  ai_run: AIRun
}

export interface StoryCharacter {
  id: string
  name: string
  aliases: string[]
  role: string
  description: string
  motivation: string
}

export interface StoryLocation {
  id: string
  name: string
  description: string
}

export interface StoryEvent {
  id: string
  source_chapter: string
  summary: string
  involved_characters: string[]
}

export interface StoryElementsSnapshot {
  id: number
  project_id: number
  characters: StoryCharacter[]
  locations: StoryLocation[]
  events: StoryEvent[]
  created_at: string
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

export async function startProjectStoryElementsJob(
  projectId: number,
): Promise<ProjectAITaskJobResponse> {
  return requestJson(`/api/projects/${projectId}/story-elements/jobs`, { method: 'POST' })
}

export async function startProjectChapterAnalysisJob(
  projectId: number,
): Promise<ProjectAITaskJobResponse> {
  return requestJson(`/api/projects/${projectId}/chapter-analyses/jobs`, { method: 'POST' })
}

export async function startProjectScriptYamlJob(
  projectId: number,
): Promise<ProjectAITaskJobResponse> {
  return requestJson(`/api/projects/${projectId}/script-yaml/jobs`, { method: 'POST' })
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
