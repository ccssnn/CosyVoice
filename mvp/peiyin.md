可以，我把它整理成一份**适合直接做 SDK / Agent / WebUI 的 CosyVoice3 细粒度控制手册**。
目标不是“解释概念”，而是让你后面能直接落代码，不混乱。

我建议你以后统一按这 4 层来理解 CosyVoice3 的控制能力：

> **1. 指令控制（Instruction）**
> **2. 文本内联控制（Inline Tags）**
> **3. 发音修复控制（Pronunciation / Hotfix）**
> **4. 参考音频控制（Prompt Audio）**

如果你把这四层分开，整个系统会非常清晰。

---

# 一、总表：CosyVoice3 的细粒度控制地图

| 层级 |   控制方式 |       粒度 |              主要用途 |                                  推荐 API |
| -- | -----: | -------: | ----------------: | --------------------------------------: |
| 1  | 自然语言指令 |   句子/整段级 |    情绪、语速、角色、方言、风格 |                   `inference_instruct2` |
| 2  | 文本内联标签 | 词/短语/句内级 |     呼吸、笑声、强调、口语节奏 | `zero_shot / instruct2 / cross_lingual` |
| 3  |   发音修复 |     字/词级 | 多音字、专有名词、英语词、混语修音 |                 `zero_shot / instruct2` |
| 4  | 参考音频控制 |     说话人级 |   音色、口音、情绪底色、节奏底色 |                          所有带 prompt 的模式 |

---

# 二、第一层：指令控制（Instruction Control）

这是你最容易做成前端配置项的一层。
它主要解决的是：

> **“整体应该怎么说”**

适合放到：

* 风格选择器
* 情绪下拉框
* 语速滑块
* 角色模板
* 方言切换

推荐统一走：

```python id="4c91i9"
cosyvoice.inference_instruct2(...)
```

---

## 2.1 情绪控制（Emotion）

这是最常用的一类。

---

### 可控项（推荐标准化枚举）

```python id="v83p4k"
EMOTIONS = [
    "happy",
    "sad",
    "fearful",
    "angry",
    "surprised",
    "calm",
    "serious",
    "joyful",
    "energetic",
    "empathetic",
    "relaxed",
    "hopeful",
]
```

---

### 推荐 prompt 模板

```python id="1bep5c"
EMOTION_PROMPTS = {
    "happy": "请用开心、轻快、带一点兴奋的语气说话。",
    "sad": "请用低落、悲伤、克制的语气说话。",
    "fearful": "请用害怕、紧张、不安的语气说话。",
    "angry": "请用生气、不耐烦、带情绪的语气说话。",
    "surprised": "请用惊讶、不可思议、情绪起伏较大的语气说话。",
    "calm": "请用平静、稳定、自然的语气说话。",
    "serious": "请用严肃、正式、认真的语气说话。",
    "joyful": "请用喜悦、明亮、充满活力的语气说话。",
    "energetic": "请用精力充沛、饱满有劲的语气说话。",
    "empathetic": "请用温柔、理解、带安慰感的语气说话。",
    "relaxed": "请用轻松、自然、不紧绷的语气说话。",
    "hopeful": "请用带希望感、积极向上的语气说话。",
}
```

---

## 2.2 语速控制（Speed）

这类非常适合做滑块或三档按钮。

---

### 推荐标准化枚举

```python id="3rj6x0"
SPEEDS = ["slow", "normal", "fast"]
```

---

### 推荐 prompt 模板

```python id="hljbpi"
SPEED_PROMPTS = {
    "slow": "请用较慢、清晰、平稳的语速说话。",
    "normal": "请用自然、适中的语速说话。",
    "fast": "请用偏快、紧凑但清晰的语速说话。",
}
```

---

## 2.3 音量 / 力度（Volume / Intensity）

这类可以理解成“声压感”。

---

### 推荐标准化枚举

```python id="gt5my8"
VOLUMES = ["soft", "normal", "loud"]
```

---

### 推荐 prompt 模板

```python id="flq0vp"
VOLUME_PROMPTS = {
    "soft": "请轻声、柔和地说话。",
    "normal": "请用自然正常的音量说话。",
    "loud": "请用更有力量、更有气势的方式说话。",
}
```

---

## 2.4 角色控制（Role / Persona）

这类非常适合你后面做：

* 陪伴 Agent
* 配音角色
* 剧情对白
* 教学人物

---

### 推荐标准化枚举

```python id="ak4m18"
ROLES = [
    "child",
    "robot",
    "detective",
    "poet",
    "teacher",
    "customer_service",
    "storyteller",
    "news_anchor",
]
```

---

### 推荐 prompt 模板

```python id="d3k6bw"
ROLE_PROMPTS = {
    "child": "请用5岁小朋友的语气说话，活泼、可爱、轻快。",
    "robot": "请像机器人一样说话，语气平稳、略带机械感。",
    "detective": "请像侦探一样说话，低沉、谨慎、带一点神秘感。",
    "poet": "请像诗人一样说话，缓慢、富有节奏和情感。",
    "teacher": "请像老师一样说话，清晰、耐心、易懂。",
    "customer_service": "请像客服一样说话，礼貌、清晰、温和。",
    "storyteller": "请像讲故事的人一样说话，自然、有画面感。",
    "news_anchor": "请像新闻播报员一样说话，正式、稳定、清楚。",
}
```

---

## 2.5 方言控制（Dialect）

这类建议你直接做成固定模板，不要让用户随便乱写。

---

### 推荐标准化枚举

```python id="ofbq8e"
DIALECTS = [
    "mandarin",
    "cantonese",
    "dongbei",
    "tianjin",
    "sichuan",
    "shanghai",
]
```

---

### 推荐 prompt 模板

```python id="dkm2cm"
DIALECT_PROMPTS = {
    "mandarin": "请用标准普通话表达。",
    "cantonese": "请用自然、地道的广东话表达。",
    "dongbei": "请用东北话口音表达。",
    "tianjin": "请用天津话口音表达。",
    "sichuan": "请用四川话口音表达。",
    "shanghai": "请用上海话口音表达。",
}
```

---

## 2.6 口音控制（Accent）

这类通常用于英语生成。

---

### 推荐标准化枚举

```python id="j0b70v"
ACCENTS = [
    "none",
    "chinese_english",
    "indian_english",
    "russian_english",
]
```

---

### 推荐 prompt 模板

```python id="d1smxj"
ACCENT_PROMPTS = {
    "none": "",
    "chinese_english": "请用带一点中式英语口音的方式说。",
    "indian_english": "请用带一点印度英语口音的方式说。",
    "russian_english": "请用带一点俄罗斯英语口音的方式说。",
}
```

---

# 三、第二层：文本内联控制（Inline Tags）

这一层是“真正细粒度”的核心。
它解决的是：

> **“句子里面，某个位置怎么说”**

不是整句，而是：

* 某个地方要换气
* 某个地方要笑
* 某个词要强调

这层建议你做成 **文本编辑器增强功能** 或 **自动插入器**。

---

# 3.1 `[breath]` —— 呼吸 / 换气

这是最值得用的 inline tag。

---

## 作用

在该位置插入自然呼吸 / 换气感。

---

## 示例

```python id="h12i0h"
text = "[breath]因为他们那一辈人[breath]在乡里面住的要习惯一点，[breath]邻居都很活络。"
```

---

## 适合场景

* 口语叙述
* 讲故事
* 播客风格
* 长句自然停顿
* 更像真人说话

---

## 使用建议

### 推荐

* 一句 0～3 个
* 放在逗号、转折、语义换气点附近

### 不推荐

* 每个短语都插
* 句首句尾滥用

---

# 3.2 `[laughter]` —— 笑声 / 带笑说话

---

## 作用

插入笑声或“说着说着笑出来”的效果。

---

## 示例

```python id="q6c73h"
text = "在他讲述那个荒诞故事的过程中，他突然[laughter]停下来，因为他自己也被逗笑了[laughter]。"
```

---

## 适合场景

* 剧情对白
* 角色扮演
* 播客访谈
* 更有生命力的陪伴语音

---

## 使用建议

不要把它当“背景音效”。
它更适合：

* 情绪点前后
* 对白式文本
* 人物表演型内容

---

# 3.3 `<strong>...</strong>` —— 强调 / 重读

这个非常值钱，因为它能做到**词级控制**。

---

## 作用

对某个词或短语做：

* 重读
* 强调
* 情绪抬升

---

## 示例

```python id="0ekehz"
text = "这不是普通的问题，这是<strong>非常严重</strong>的问题。"
```

---

## 适合场景

* 教学讲解
* 短视频配音
* 新闻重点
* 剧情台词
* 产品卖点强调

---

## 使用建议

### 推荐

* 强调 1～3 个关键词
* 强调“意义核心词”

### 不推荐

* 整句全加 `<strong>`
* 每句话都强调

---

# 四、第三层：发音修复控制（Pronunciation / Hotfix）

这一层解决的是：

> **“这个字 / 词读错了，怎么修”**

这类能力在 demo 里看起来不花哨，但它决定了：

> **产品到底能不能用**

尤其你做：

* 人名地名
* 品牌名
* 专有名词
* 多音字
* 中英混排

时，这层是必须的。

---

# 4.1 中文多音字修复

---

## 示例

```python id="3bz1k8"
text = "高管也通过电话、短信、微信等方式对报道[j][ǐ]予好评。"
```

这里的：

```text id="xg5kn8"
[j][ǐ]
```

就是在提示模型正确发音。

---

## 适合场景

* 多音字
* 生僻词
* 书面语词汇
* 专有名词

---

## 最佳实践：做一个修音字典

```python id="onlm0z"
PRON_FIX = {
    "给予": "给[j][ǐ]",
    "重阳": "重[chóng]阳",
    "行长": "háng长",   # 示例：具体格式按你测试结果调整
}
```

然后生成前自动替换。

---

# 4.2 英文发音修复（英语词 / 品牌名 / 外来词）

---

## 适合场景

* 品牌名：`Hermès`
* 公司名：`NVIDIA`
* 模型名：`Qwen`
* 产品名：`OpenAI`
* 外来词：`Beyoncé`

---

## 最佳实践

这类你通常不要直接让用户输原词，而是：

### 方案 A：文本规范化

```python id="t9fxgf"
"OpenAI" -> "Open A I"
"LLM" -> "L L M"
"NVIDIA" -> "N V I D I A"
```

### 方案 B：发音热修复字典

```python id="h1gffv"
EN_PRON_FIX = {
    "OpenAI": "Open A I",
    "LLM": "L L M",
    "AIGC": "A I G C",
}
```

---

# 4.3 日语假名 / 片假名输入控制

这在实际使用里非常重要。

---

## 原理

很多时候，直接输入复杂日文汉字句子不如输入发音更稳。

---

## 示例

```python id="66q4th"
text = "レキシ テキ セカイ ニ オイ テ ワ、カコ ワ タンニ スギサッ タ モノ デ ワ ナイ。"
```

---

## 适合场景

* 日语跨语言
* 日语 mixed-lingual
* 日语配音

---

## 最佳实践

如果你做日语支持，建议做一个前处理模块：

```python id="yliv5d"
jp_text -> kana/katakana
```

这样稳定性会高很多。

---

# 五、第四层：参考音频控制（Prompt Audio Control）

这一层很多人低估了，但它其实是：

> **最强的“隐式控制器”**

它控制的是：

* 你像谁
* 你说话的基调是什么
* 你天然偏快还是偏慢
* 你带什么口音 / 情绪底色

它不属于“文本控制”，但它是细粒度效果的核心组成。

---

# 5.1 音色控制（Timbre）

通过换参考音频控制：

* 男声 / 女声
* 年轻 / 成熟
* 明亮 / 低沉
* 可爱 / 冷静
* 角色感

---

## 建议你做一个 prompt 音色库

```python id="e8n3n7"
PROMPT_BANK = {
    "male_clear": "data/prompts/male_clear.wav",
    "female_soft": "data/prompts/female_soft.wav",
    "child_like": "data/prompts/child_like.wav",
    "serious_anchor": "data/prompts/serious_anchor.wav",
}
```

---

# 5.2 情绪底色控制（Emotion Prior）

如果你想要“快乐”的输出，最稳的方式不是只写：

```python id="2e9zkl"
"请开心地说"
```

而是：

* 用一个本来就比较开心、明亮的参考音频
* 再叠加情绪指令

这会稳定得多。

---

## 最佳实践

建立情绪 prompt 库：

```python id="cr4q4d"
EMOTION_PROMPT_BANK = {
    "happy": "data/prompts/happy.wav",
    "sad": "data/prompts/sad.wav",
    "angry": "data/prompts/angry.wav",
    "calm": "data/prompts/calm.wav",
}
```

---

# 5.3 节奏 / 语速底色控制（Rhythm Prior）

有些 prompt speaker 本来就：

* 说话快
* 断句密
* 偏播报
* 偏口语

这些都会被继承。

---

## 最佳实践

如果你要产品稳定：

不要只做“一个 prompt 音频”。

而是做成：

* `slow_speaker.wav`
* `normal_speaker.wav`
* `fast_speaker.wav`

---

# 5.4 方言 / 口音底色控制（Accent Prior）

如果你想让粤语更稳、印度英语更稳：

> **最强的方法永远是：prompt 本身就带那个味道。**

不是只靠一句文字 prompt。

---

# 六、推荐的“标准控制字典”

如果你后面要做 SDK，我建议你统一用这份 schema，不要让系统乱长。

---

## 6.1 控制对象结构

```python id="cv2xqj"
control = {
    # 第一层：整句风格
    "emotion": "happy",         # happy / sad / angry / ...
    "speed": "normal",          # slow / normal / fast
    "volume": "normal",         # soft / normal / loud
    "role": "teacher",          # child / robot / teacher / ...
    "dialect": "mandarin",      # mandarin / cantonese / ...
    "accent": "none",           # none / chinese_english / ...
    
    # 第二层：句内标签
    "inline_tags": [
        {"type": "breath", "pos": 0},
        {"type": "strong", "span": "非常严重"},
        {"type": "laughter", "pos": 18},
    ],

    # 第三层：发音修复
    "pron_fix": {
        "给予": "给[j][ǐ]",
        "OpenAI": "Open A I"
    },

    # 第四层：参考音频
    "prompt_voice": "female_soft",  # 对应 prompt 音频库 key
}
```

---

# 七、推荐的“控制编译策略”

你不要直接让主程序拼 prompt。
建议做一层：

> **Control → Prompt / Text / Prompt Audio 编译器**

这样系统会非常稳。

---

## 7.1 编译器思路

输入：

```python id="9r1f5i"
text = "这不是普通的问题，这是非常严重的问题。"
control = {
    "emotion": "serious",
    "speed": "slow",
    "volume": "normal",
    "role": "teacher",
    "dialect": "mandarin",
    "accent": "none",
    "inline_tags": [
        {"type": "strong", "span": "非常严重"},
        {"type": "breath", "pos": 0}
    ],
    "pron_fix": {},
    "prompt_voice": "female_soft"
}
```

输出成三样东西：

---

### 1）instruction prompt

```python id="9ihj5m"
"You are a helpful assistant. 请像老师一样说话，清晰、耐心、易懂。请用严肃、正式、认真的语气说话。请用较慢、清晰、平稳的语速说话。请用标准普通话表达。<|endofprompt|>"
```

---

### 2）inline processed text

```python id="v8h1to"
"[breath]这不是普通的问题，这是<strong>非常严重</strong>的问题。"
```

---

### 3）prompt wav 路径

```python id="3gwj5j"
"data/prompts/female_soft.wav"
```

---

# 八、最推荐你先做成产品能力的控制项（优先级）

如果你不是做研究，而是做实际产品，我建议按下面顺序实现：

---

## 第一优先级（必须有）

* emotion
* speed
* prompt voice
* pron_fix

这四个能决定 80% 实际体验。

---

## 第二优先级（很值钱）

* `[breath]`
* `<strong>...</strong>`
* role
* dialect

这四个能明显拉开“普通 TTS”和“可控 TTS”的差距。

---

## 第三优先级（锦上添花）

* `[laughter]`
* accent
* volume

这类不是所有产品都必须，但在角色 / 陪伴 / 表演类产品里很有用。

---

# 九、最实用的落地建议

如果你真的要把它做成一个稳定系统，建议你直接这样分模块：

---

## 模块 1：`style_controller.py`

负责：

* emotion
* speed
* role
* dialect
* accent
* volume

---

## 模块 2：`inline_tag_processor.py`

负责：

* `[breath]`
* `[laughter]`
* `<strong>...</strong>`

---

## 模块 3：`pronunciation_fixer.py`

负责：

* 中文多音字修复
* 英文缩写展开
* 品牌名读法
* 日语假名转换（可选）

---

## 模块 4：`prompt_router.py`

负责：

* 选哪条参考音频
* 情绪 prompt 库
* 角色 prompt 库
* 方言 prompt 库

---

## 模块 5：`tts_engine.py`

统一调：

```python id="2i0n4d"
inference_zero_shot
inference_instruct2
inference_cross_lingual
```

---

# 十、最后给你一份“最终版简表”（建议你保存）

---

## CosyVoice3 细粒度控制完整清单

### A. 指令控制（整句级）

* 情绪：happy / sad / angry / fearful / surprised / calm / serious / ...
* 语速：slow / normal / fast
* 音量：soft / normal / loud
* 角色：child / robot / detective / teacher / storyteller / ...
* 方言：mandarin / cantonese / dongbei / tianjin / sichuan / shanghai
* 口音：chinese_english / indian_english / russian_english
* 风格：客服、播报、讲故事、短视频、安抚、旁白等

---

### B. 文本内联控制（句内级）

* `[breath]`
* `[laughter]`
* `<strong>...</strong>`

---

### C. 发音修复（字词级）

* 中文多音字修复
* 英文缩写/品牌名修复
* 专有名词修复
* 日语假名/片假名输入
* 混语读法修复

---

### D. 参考音频控制（说话人级）

* 音色
* 情绪底色
* 节奏底色
* 语速底色
* 方言底色
* 口音底色

---

如果你愿意，我下一步最适合直接做的是：

### 选项 A（最实用）

我直接帮你把这套整理成一个 **`CosyVoice3Controller` 完整 Python 类**，你可以直接调用：

```python id="ztp6n4"
tts.generate(
    text="我终于抢到演唱会门票了！",
    emotion="happy",
    speed="fast",
    role="child",
    inline_tags=[...],
    pron_fix={...},
    prompt_voice="female_soft"
)
```

### 选项 B（最适合做产品）

我直接帮你设计一套 **可控 TTS 的 DSL / JSON schema**，方便你前端、Agent、数据库统一使用。

如果你愿意，我建议直接继续做 **A + B**，这样你下一步就可以真正落工程了。

