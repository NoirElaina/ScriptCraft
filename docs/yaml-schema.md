# ScriptCraft 剧本 YAML Schema 设计文档

## 1. 设计目标

ScriptCraft 的目标是把 3 个章节以上的小说文本转换为可编辑、可校验、可继续打磨的剧本初稿。YAML Schema 是生成结果的结构约定，用于约束模型输出、驱动前端预览、支持后端校验，并为作者保留清晰的编辑入口。


## 2. 顶层结构

```yaml
schema_version: "1.0"
title: "雨夜来信"
metadata: {}
characters: []
locations: []
events: []
scenes: []
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | Schema 版本，用于兼容不同输出结构。 |
| `title` | string | 是 | 改编后的剧本标题。 |
| `metadata` | object | 是 | 来源、风格、语言等元信息。 |
| `characters` | array | 是 | 角色表。 |
| `locations` | array | 是 | 地点表。 |
| `events` | array | 是 | 从小说章节中抽取的关键剧情事件。 |
| `scenes` | array | 是 | 剧本场次列表。 |

## 3. metadata

```yaml
metadata:
  source_title: "雨夜来信"
  chapters_count: 3
  adaptation_style: "web_drama"
  language: "zh-CN"
  generated_at: "2026-06-05T12:00:00+08:00"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `source_title` | string | 是 | 原小说标题。 |
| `chapters_count` | number | 是 | 参与改编的章节数量。 |
| `adaptation_style` | string | 是 | 改编风格，例如 `web_drama`、`film`、`stage_play`。 |
| `language` | string | 是 | 输出语言。 |
| `generated_at` | string | 否 | 生成时间，使用 ISO 8601 格式。 |

设计原因：

- `metadata` 把剧本内容和生成上下文分离，保证预览、导出和校验逻辑能够复用同一份元信息。
- `adaptation_style` 让同一份小说可以生成短剧、影视剧本、舞台剧等不同版本。

## 4. characters

```yaml
characters:
  - id: "char_001"
    name: "林舟"
    aliases: ["小林"]
    role: "protagonist"
    description: "年轻记者，正在追查父亲失踪的真相。"
    motivation: "找到匿名来信背后的发信人。"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 角色唯一标识。 |
| `name` | string | 是 | 角色名称。 |
| `aliases` | array | 否 | 角色别名。 |
| `role` | string | 是 | 叙事职能，例如主角、反派、配角。 |
| `description` | string | 是 | 角色简述。 |
| `motivation` | string | 否 | 角色目标或行动动机。 |

设计原因：

- 使用 `id` 而不是直接用姓名引用角色，可以避免同名、别名和称呼变化导致的混乱。
- `motivation` 用于辅助角色一致性检查，判断对白和行动是否符合角色目标。

## 5. locations

```yaml
locations:
  - id: "loc_001"
    name: "老城区咖啡馆"
    description: "灯光昏暗，靠窗位置能看到雨夜街道。"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 地点唯一标识。 |
| `name` | string | 是 | 地点名称。 |
| `description` | string | 否 | 地点视觉或氛围描述。 |

设计原因：

- 地点独立成表，便于多个场次复用同一地点。
- `description` 为分镜、场景提示词和美术设定提供可复用的场景信息。

## 6. events

```yaml
events:
  - id: "event_001"
    source_chapter: "chapter_001"
    summary: "林舟收到匿名短信，被约到老城区咖啡馆。"
    involved_characters: ["char_001"]
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 事件唯一标识。 |
| `source_chapter` | string | 是 | 事件来源章节。 |
| `summary` | string | 是 | 事件摘要。 |
| `involved_characters` | array | 否 | 参与该事件的角色 ID。 |

设计原因：

- `events` 是小说章节和剧本场次之间的中间层。
- 先抽事件再生成场次，可以降低一次性生成整篇剧本的不稳定性。

## 7. scenes

```yaml
scenes:
  - id: "scene_001"
    title: "雨夜邀约"
    source_chapters: ["chapter_001"]
    source_events: ["event_001"]
    location_id: "loc_001"
    time_of_day: "night"
    characters: ["char_001"]
    dramatic_purpose: "建立悬念并引出主角目标。"
    summary: "林舟来到咖啡馆，等待匿名发信人出现。"
    beats: []
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 场次唯一标识。 |
| `title` | string | 是 | 场次标题。 |
| `source_chapters` | array | 是 | 场次来源章节 ID。 |
| `source_events` | array | 否 | 场次来源事件 ID。 |
| `location_id` | string | 是 | 场次地点 ID。 |
| `time_of_day` | string | 否 | 时间，例如 `morning`、`night`。 |
| `characters` | array | 是 | 出场角色 ID。 |
| `dramatic_purpose` | string | 否 | 该场戏在叙事中的作用。 |
| `summary` | string | 是 | 场次摘要。 |
| `beats` | array | 是 | 场次内的动作、对白、旁白等有序内容。 |

设计原因：

- 剧本按场组织，而不是按小说章节组织，所以 `scenes` 是最终剧本的核心。
- `source_chapters` 保留溯源关系，作者可以据此核对场次与原文的对应关系。
- `dramatic_purpose` 明确场次的叙事作用，便于判断某场戏是否具有保留价值。

## 8. beats

```yaml
beats:
  - type: "action"
    content: "林舟推门进入咖啡馆，雨水顺着伞尖滴落。"
  - type: "dialogue"
    speaker_id: "char_001"
    content: "你到底是谁？"
  - type: "narration"
    content: "手机屏幕亮起，新的短信只有四个字：别回头。"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | string | 是 | 节拍类型。 |
| `speaker_id` | string | 当 `type=dialogue` 时必填 | 说话角色 ID。 |
| `content` | string | 是 | 节拍内容。 |

支持的 `type`：

- `action`：动作或画面描述。
- `dialogue`：角色对白。
- `narration`：旁白或叙述。
- `transition`：转场提示。
- `sound`：声音提示。

设计原因：

- `beats` 保留场次内部顺序，适合前端逐条编辑。
- 区分动作、对白、旁白后，系统可以导出不同剧本格式，并支持对白占比、角色出场统计等分析。

## 9. 完整示例

```yaml
schema_version: "1.0"
title: "雨夜来信"
metadata:
  source_title: "雨夜来信"
  chapters_count: 3
  adaptation_style: "web_drama"
  language: "zh-CN"
characters:
  - id: "char_001"
    name: "林舟"
    aliases: ["小林"]
    role: "protagonist"
    description: "年轻记者，正在追查父亲失踪的真相。"
    motivation: "找到匿名来信背后的发信人。"
locations:
  - id: "loc_001"
    name: "老城区咖啡馆"
    description: "灯光昏暗，靠窗位置能看到雨夜街道。"
events:
  - id: "event_001"
    source_chapter: "chapter_001"
    summary: "林舟收到匿名短信，被约到老城区咖啡馆。"
    involved_characters: ["char_001"]
scenes:
  - id: "scene_001"
    title: "雨夜邀约"
    source_chapters: ["chapter_001"]
    source_events: ["event_001"]
    location_id: "loc_001"
    time_of_day: "night"
    characters: ["char_001"]
    dramatic_purpose: "建立悬念并引出主角目标。"
    summary: "林舟来到咖啡馆，等待匿名发信人出现。"
    beats:
      - type: "action"
        content: "林舟推门进入咖啡馆，雨水顺着伞尖滴落。"
      - type: "dialogue"
        speaker_id: "char_001"
        content: "你到底是谁？"
      - type: "narration"
        content: "手机屏幕亮起，新的短信只有四个字：别回头。"
```

## 10. 校验规则

系统按以下规则校验生成结果：

- 顶层必须包含 `schema_version`、`title`、`metadata`、`characters`、`locations`、`events`、`scenes`。
- 每个 `character.id`、`location.id`、`event.id`、`scene.id` 必须唯一。
- `scene.location_id` 必须存在于 `locations`。
- `scene.characters` 中的角色 ID 必须存在于 `characters`。
- `scene.source_events` 中的事件 ID 必须存在于 `events`。
- `dialogue` 类型的 beat 必须包含 `speaker_id`。
- `speaker_id` 必须存在于 `characters`。
- 每个 scene 至少包含一个 beat。

## 11. 版本兼容说明

当前 Schema 以“角色、地点、事件、场次、节拍”为核心结构，优先保证小说到剧本初稿的可追溯和可编辑。`schema_version` 用于标识结构版本；当输出结构升级时，系统应保留旧版本的读取能力，避免影响已经生成的剧本版本。

本版本暂不把幕结构、镜头语言和人物关系图作为必填字段。它们更适合作为独立编辑能力接入，避免基础剧本初稿过早承载过多格式要求。
