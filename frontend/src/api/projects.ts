import type { Chapter } from './chapters'
import { requestJson } from './client'
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

export interface ProjectWorkspaceResponse {
  project: Project
  chapters: Chapter[]
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

export async function generateProjectScriptYaml(
  projectId: number,
): Promise<ProjectScriptYamlResponse> {
  return requestJson(`/api/projects/${projectId}/script-yaml`, { method: 'POST' })
}
