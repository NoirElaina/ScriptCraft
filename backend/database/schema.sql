CREATE DATABASE IF NOT EXISTS scriptcraft
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE scriptcraft;

CREATE TABLE IF NOT EXISTS users (
  id INT NOT NULL AUTO_INCREMENT,
  username VARCHAR(80) NOT NULL,
  email VARCHAR(180) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS projects (
  id INT NOT NULL AUTO_INCREMENT,
  owner_id INT NULL,
  title VARCHAR(120) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(40) NOT NULL,
  source_text MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_projects_owner_id (owner_id),
  KEY ix_projects_title (title),
  KEY ix_projects_status (status),
  CONSTRAINT fk_projects_owner_id_users
    FOREIGN KEY (owner_id) REFERENCES users (id)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chapters (
  id INT NOT NULL AUTO_INCREMENT,
  project_id INT NOT NULL,
  chapter_index INT NOT NULL,
  chapter_key VARCHAR(80) NOT NULL,
  heading VARCHAR(120) NOT NULL,
  title VARCHAR(180) NOT NULL,
  content MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_chapters_project_index (project_id, chapter_index),
  KEY ix_chapters_project_id (project_id),
  KEY ix_chapters_chapter_index (chapter_index),
  CONSTRAINT fk_chapters_project_id_projects
    FOREIGN KEY (project_id) REFERENCES projects (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chapter_analyses (
  id INT NOT NULL AUTO_INCREMENT,
  project_id INT NOT NULL,
  chapter_id INT NOT NULL,
  chapter_key VARCHAR(80) NOT NULL,
  chapter_index INT NOT NULL,
  summary TEXT NOT NULL,
  analysis JSON NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_chapter_analyses_project_chapter (project_id, chapter_id),
  KEY ix_chapter_analyses_project_id (project_id),
  KEY ix_chapter_analyses_chapter_id (chapter_id),
  KEY ix_chapter_analyses_chapter_key (chapter_key),
  KEY ix_chapter_analyses_chapter_index (chapter_index),
  CONSTRAINT fk_chapter_analyses_project_id_projects
    FOREIGN KEY (project_id) REFERENCES projects (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_chapter_analyses_chapter_id_chapters
    FOREIGN KEY (chapter_id) REFERENCES chapters (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS story_elements (
  id INT NOT NULL AUTO_INCREMENT,
  project_id INT NOT NULL,
  characters JSON NOT NULL,
  locations JSON NOT NULL,
  events JSON NOT NULL,
  scenes JSON NOT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_story_elements_project_id (project_id),
  CONSTRAINT fk_story_elements_project_id_projects
    FOREIGN KEY (project_id) REFERENCES projects (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS script_versions (
  id INT NOT NULL AUTO_INCREMENT,
  project_id INT NOT NULL,
  version_name VARCHAR(120) NOT NULL,
  schema_version VARCHAR(40) NOT NULL,
  yaml_content MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_script_versions_project_id (project_id),
  CONSTRAINT fk_script_versions_project_id_projects
    FOREIGN KEY (project_id) REFERENCES projects (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_runs (
  id INT NOT NULL AUTO_INCREMENT,
  project_id INT NULL,
  task_type VARCHAR(80) NOT NULL,
  provider VARCHAR(80) NOT NULL,
  model VARCHAR(120) NOT NULL,
  status VARCHAR(40) NOT NULL,
  input_payload JSON NOT NULL,
  output_payload JSON NULL,
  error_message TEXT NOT NULL,
  duration_ms INT NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_ai_runs_project_id (project_id),
  KEY ix_ai_runs_task_type (task_type),
  KEY ix_ai_runs_status (status),
  CONSTRAINT fk_ai_runs_project_id_projects
    FOREIGN KEY (project_id) REFERENCES projects (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
