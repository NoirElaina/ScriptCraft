# ScriptCraft 剧本 YAML Schema

## 1. 设计目标

ScriptCraft 的 YAML 不只保存“剧本文字”，还保存一层可执行的分镜调度。作者拿到结果后，可以继续编辑角色、地点、事件、场次、节拍，也可以直接在工作台里预演某一场戏的镜头、人物站位、动作和对白。

因此 Schema 拆成两层：

- `scenes`：剧本正文层，记录场次、对白、动作、旁白等可编辑文本。
- `storyboard`：导演调度层，引用 `scenes.beats`，描述画布如何播放这一场戏。

这样设计的原因是：剧本文本和画面调度不是同一个东西。把它们分开，作者可以改台词而不丢分镜，也可以单独调整镜头和动作。

## 2. 生成策略

ScriptCraft 采用章节流式生成，而不是把整本小说一次性交给模型。

生成时，后端按章节顺序循环：章节分析带入前文短记忆；故事元素按当前章增量归并角色、地点和事件；剧本阶段再用当前章节分析、全局元素表和剧本短记忆生成本章场景计划，并生成本章 `scenes` 与对应 `storyboard.scenes`。最终 YAML 由后端合并各章片段并统一校验。

这样设计是为了支持长篇文本：即使作者一次导入很多章节，模型每次也只处理当前章和必要记忆，避免上下文膨胀、角色引用漂移和整本剧本反复重写。

## 3. 顶层结构

```yaml
schema_version: "2.0"
title: "雨夜来信"
metadata: {}
characters: []
locations: []
events: []
scenes: []
storyboard:
  scenes: []
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | 当前版本固定为 `2.0`。 |
| `title` | string | 是 | 剧本标题。 |
| `metadata` | object | 是 | 来源、语言、改编风格等信息。 |
| `characters` | array | 是 | 角色表。 |
| `locations` | array | 是 | 地点表。 |
| `events` | array | 是 | 从小说章节抽取出的关键事件。 |
| `scenes` | array | 是 | 剧本场次正文。 |
| `storyboard` | object | 是 | 画布预演所需的导演调度。 |

## 4. metadata

```yaml
metadata:
  source_title: "雨夜来信"
  chapters_count: 3
  adaptation_style: "短剧"
  language: "zh-CN"
```

`metadata` 把生成上下文和剧本正文分离，便于后续导出、版本追踪和二次生成。

## 5. characters

```yaml
characters:
  - id: "char_001"
    name: "林舟"
    aliases: ["小林"]
    role: "主角"
    description: "年轻记者，正在追查父亲失踪的真相。"
    motivation: "找到匿名来信背后的发信人。"
```

角色用 `id` 引用，不直接用姓名引用。这样可以避免同名、别名、称呼变化导致的混乱。

## 6. locations

```yaml
locations:
  - id: "loc_001"
    name: "老城区书店"
    description: "灯光昏暗，靠窗位置能看到雨夜街道。"
```

地点独立成表，方便多个场次复用，也方便前端根据地点生成画布背景。

## 7. events

```yaml
events:
  - id: "event_001"
    source_chapter: "chapter_001"
    summary: "林舟收到匿名短信，被约到老城区书店。"
    involved_characters: ["char_001"]
```

`events` 是小说章节和剧本场次之间的中间层。先抽事件再写场次，可以减少长文本一次性改编的不稳定。

## 8. scenes

```yaml
scenes:
  - id: "scene_001"
    title: "雨夜来信"
    source_chapters: ["chapter_001"]
    source_events: ["event_001"]
    location_id: "loc_001"
    time_of_day: "night"
    characters: ["char_001", "char_002"]
    dramatic_purpose: "建立悬念，引出主角目标。"
    summary: "林舟走进即将打烊的旧书店，遇到神秘老人。"
    beats:
      - id: "beat_001"
        type: "action"
        content: "林舟推门进入书店，雨水顺着伞尖滴落。"
      - id: "beat_002"
        type: "dialogue"
        speaker_id: "char_001"
        content: "你到底是谁？"
```

`beats` 是场次内部的最小编辑单位。每个 beat 必须有 `id`，因为 `storyboard.timeline` 会引用它。

支持的 `beat.type`：

- `action`：动作或画面描述。
- `dialogue`：角色对白，必须包含 `speaker_id`。
- `narration`：旁白或叙述。
- `transition`：转场提示。
- `sound`：声音提示。

## 9. storyboard

```yaml
storyboard:
  scenes:
    - scene_id: "scene_001"
      setting:
        mood: "mysterious"
        weather: "rain"
        lighting: "dim"
        background: "old_bookstore"
      cast:
        - character_id: "char_001"
          position: "left"
          pose: "holding_umbrella"
        - character_id: "char_002"
          position: "right"
          pose: "behind_counter"
      timeline:
        - id: "shot_001"
          source_beat_id: "beat_001"
          type: "action"
          duration_ms: 2600
          camera:
            shot: "wide"
            target: "stage"
            movement: "slow_push"
          actions:
            - actor: "char_001"
              motion: "walk_in"
              from: "offscreen_left"
              to: "left"
              emotion: "nervous"
          effects: ["rain", "dim_light"]
          props:
            - id: "prop_001"
              name: "雨伞"
              action: "carry"
              from: "offscreen_left"
              to: "left"
        - id: "shot_002"
          source_beat_id: "beat_002"
          type: "dialogue"
          duration_ms: 2200
          camera:
            shot: "medium"
            target: "char_001"
            movement: "cut"
          actions:
            - actor: "char_001"
              motion: "step_forward"
              from: "left"
              to: "center"
              emotion: "determined"
          dialogue:
            speaker_id: "char_001"
            text: "你到底是谁？"
          effects: []
```

### setting

`setting` 描述画布的整体氛围：

| 字段 | 说明 |
| --- | --- |
| `mood` | 情绪，例如 `mysterious`、`tense`、`warm`。 |
| `weather` | 天气，例如 `rain`、`clear`。 |
| `lighting` | 光线，例如 `dim`、`cold`、`warm`。 |
| `background` | 背景类型，例如 `old_bookstore`、`office`、`street`。 |

### cast

`cast` 描述角色初始出场站位和姿态。环境空镜、旁白、转场或声音场可以使用空 `cast`。如果某个 shot 里出现对白或人物动作，对应角色必须出现在 `cast` 中。

这里的 `position` 必须是画布内位置，不能使用 `offscreen_left` 或 `offscreen_right`。

- `left`
- `back_left`
- `center`
- `back_right`
- `right`

### timeline

`timeline` 是可执行的播放轨道。每个 shot 引用一个 `source_beat_id`，并额外给出镜头、动作、道具和效果。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 镜头唯一标识。 |
| `source_beat_id` | string | 是 | 引用当前 scene 中的 beat。 |
| `type` | string | 是 | 与 beat 类型一致或接近。 |
| `duration_ms` | number | 是 | 播放时长。 |
| `camera` | object | 是 | 镜头调度。 |
| `actions` | array | 是 | 人物动作。 |
| `dialogue` | object | 当 `type=dialogue` 时必填 | 台词内容。 |
| `effects` | array | 否 | 氛围效果，例如 `rain`、`flicker`、`spotlight`。 |
| `props` | array | 否 | 道具调度。 |

`camera.shot` 支持：

- `wide`
- `medium`
- `close`
- `insert`

`camera.movement` 支持：

- `cut`
- `slow_push`
- `pan`
- `shake`
- `hold`

`action.motion` 支持：

- `idle`
- `walk_in`
- `walk_to`
- `step_forward`
- `turn`
- `look_around`
- `point`
- `hand_prop`
- `place_prop`
- `pick_prop`
- `react`
- `close_door`

`action.from` 和 `action.to` 可以使用 `offscreen_left`、`offscreen_right` 表示入场或离场，但 `cast.position` 不使用场外位置。

## 10. 校验规则

系统至少校验以下内容：

- 顶层必须包含 `schema_version`、`title`、`metadata`、`characters`、`locations`、`events`、`scenes`、`storyboard`。
- `schema_version` 必须是 `2.0`。
- 每个 `character.id`、`location.id`、`event.id`、`scene.id` 必须唯一。
- `scene.location_id` 必须存在于 `locations`。
- `scene.characters` 中的角色 ID 必须存在于 `characters`。
- `scene.source_events` 中的事件 ID 必须存在于 `events`。
- 每个 `beat` 必须包含 `id`、`type`、`content`。
- `dialogue` 类型的 beat 必须包含 `speaker_id`，且角色必须存在。
- `storyboard.scenes` 必须覆盖每个 scene。
- `storyboard.timeline.source_beat_id` 必须引用当前 scene 的 beat。
- `cast` 可以为空，但 `action.actor`、`dialogue.speaker_id` 必须引用已有角色，且必须出现在当前 storyboard scene 的 `cast` 中。
- `duration_ms` 必须大于 0。

## 11. 设计原因

这个 Schema 的核心取舍是“正文可编辑，调度可执行”。

`scenes.beats` 保留作者最关心的文本结构：对白、动作、旁白、转场。`storyboard.timeline` 则服务于画布预演，负责镜头、动作、站位、道具和氛围效果。两层通过 `source_beat_id` 建立关系，既能追溯原文，又不会把视觉调度塞进每一条台词里。

这种设计也方便后续扩展：如果要增加角色关系图、镜头表、导出 Fountain/Markdown，或者加入语音、口型和背景图，都可以基于同一份 YAML 继续向外扩展。
