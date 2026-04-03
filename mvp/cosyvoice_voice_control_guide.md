# CosyVoice3 声音控制整理

这份文档把两类来源合在一起：

- 论文：[data/2505.pdf](/Users/citeace/Documents/Projects/MVP/CosyVoice/data/2505.pdf)
- 仓库代码：
  - [example.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/example.py)
  - [demo_all.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/demo_all.py)
  - [cosyvoice.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/cli/cosyvoice.py)
  - [frontend.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/cli/frontend.py)
  - [tokenizer.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/tokenizer/tokenizer.py)
  - [common.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/utils/common.py)
  - [render_dub_plan.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/mvp/render_dub_plan.py)

目标只有一个：把 CosyVoice3 里“声音怎么控”讲清楚，并给出可直接用的例子。

## 1. 论文里和声音控制直接相关的结论

论文里最重要的是 4 个点。

### 1.1 指令控制

论文 `2.5 Instructed Speech Generation` 明确说了两类控制：

- 自然语言指令
- 细粒度标签

自然语言指令的格式是：

```text
自然语言描述 + <|endofprompt|> + 正文
```

论文原文的关键点是：

- CosyVoice3 支持 emotions、speed、voice tones、dialects、accents、role-playing
- 对自然语言指令，输入前面要加一个自然语言描述和 `<|endofprompt|>`
- 对细粒度控制，支持 `[laughter]`、`[breath]`、`<strong>...</strong>`

### 1.2 风格词表

论文 Table 1 给了一批高频风格词。这些词比我们自己临时发明的中文标签更接近训练分布。

常用的几组：

- 情绪/语气：`angry` `calm` `cheerful` `empathetic` `fearful` `happy` `joyful` `mysterious` `optimistic` `proud` `sad` `serious` `soft` `surprised`
- 力度/节奏：`fast` `loud` `slow` `soft`
- 人设/角色：`girl` `detective` `doctor` `leader` `merchant` `peppa` `poet` `robot` `scholar` `wanderer`
- 方言/口音：`cantonese dialect` `chongqing dialect` `shanghai dialect` `sichuan dialect` `tianjin dialect` `xi'an dialect` `chinese english accent` `indian english accent` `russian english accent`

### 1.3 发音修复

论文 `2.3 Pronunciation Inpainting` 说明了一个核心方向：

- CosyVoice3 可以通过“字词 + 音素/拼音混写”来修发音

也就是说，模型不是只能吃纯自然语言文本，它能接受更细的发音控制输入。

### 1.4 说话人一致性

论文 `2.6.2` 说明：

- speaker prompt 和 style prompt 可以分开
- 说话人信息和风格信息是两个不同控制维度

这点很重要。落到实际工程里，意思就是：

- 音色一致性主要靠 `prompt_wav / speaker cache`
- 句子的情绪和风格再靠 `instruct_text`

不要拿一大段 prompt 文案去硬控音色。

## 2. 代码仓库里实际支持什么

### 2.1 三条主要 API

仓库实际暴露的主要接口在 [cosyvoice.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/cli/cosyvoice.py)：

- `inference_zero_shot`
- `inference_instruct2`
- `inference_cross_lingual`

#### `inference_zero_shot`

适合：

- 固定音色
- 用参考音的说话方式带输出

接口形态：

```python
cosyvoice.inference_zero_shot(
    tts_text=...,
    prompt_text=...,
    prompt_wav=...,
    zero_shot_spk_id='',
    stream=False,
    speed=1.0,
    text_frontend=True,
)
```

关键点：

- `prompt_text` 是参考音频的转写
- 在 CosyVoice3 里，`prompt_text` 里最好带 `<|endofprompt|>`
- 可以先 `add_zero_shot_spk(...)`，后续直接复用 `zero_shot_spk_id`

#### `inference_instruct2`

适合：

- 每句做风格控制
- 绘本对白
- 情绪和说话方式控制

接口形态：

```python
cosyvoice.inference_instruct2(
    tts_text=...,
    instruct_text=...,
    prompt_wav=...,
    zero_shot_spk_id='',
    stream=False,
    speed=1.0,
    text_frontend=True,
)
```

关键点：

- `instruct_text` 就是自然语言风格提示
- 这是绘本配音最常用的一条
- 如果同时传 `zero_shot_spk_id`，同角色一致性会明显更稳

#### `inference_cross_lingual`

适合：

- 跨语言
- 某些细粒度标签实验

但对你这个中文绘本项目，不是最优先。

原因：

- 你现在主要需求是“同角色一致性 + 中文短句稳定”
- 这类任务用 `inference_instruct2` 更稳

### 2.2 CosyVoice3 的 `<|endofprompt|>` 约束

在 [llm.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/llm/llm.py) 里，CosyVoice3LM 会直接检查：

- `text` 或 `prompt_text` 里必须有 `<|endofprompt|>`

这就是为什么 CosyVoice3 下：

- `instruct_text` 必须带 `<|endofprompt|>`
- `zero_shot` 的 `prompt_text` 最好带 `<|endofprompt|>`
- `cross_lingual` 在官方示例里也把 `You are a helpful assistant.<|endofprompt|>` 直接写进了 `tts_text`

### 2.3 支持的细粒度标签

在 [tokenizer.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/tokenizer/tokenizer.py) 里，CosyVoice3 tokenizer 注册了这些特殊 token。

最常用的：

- `[breath]`
- `[laughter]`
- `<strong>`
- `</strong>`
- `[noise]`
- `[cough]`
- `[quick_breath]`
- `<laughter>`
- `</laughter>`

所以实际可控的句内效果包括：

- 呼吸
- 笑声
- 强调
- 部分拟声/噪声

### 2.4 官方示例里已经给出的 prompt 风格

在 [example.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/example.py) 和 [demo_all.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/demo_all.py) 里，官方已经给出几种很有代表性的写法：

- `Please say a sentence as angrily as possible.`
- `Please say a sentence in a very fearful tone.`
- `Please say a sentence as fast as possible.`
- `Please say a sentence in a very soft voice.`
- `请非常开心地说一句话。`
- `请用广东话表达。`
- `请用重庆话表达。`

所以仓库层面的结论很清楚：

- 中文 prompt 能用
- 英文 prompt 也能用
- 对 CosyVoice3 而言，英文 style word 更贴近论文 Table 1

### 2.5 角色缓存复用

仓库本身已经支持 speaker cache：

- `add_zero_shot_spk(...)`：把参考音和参考文本注册成一个 speaker
- `zero_shot_spk_id`：后续推理时复用这个 speaker

对应实现：

- 注册在 [cosyvoice.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/cli/cosyvoice.py)
- 复用逻辑在 [frontend.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/cosyvoice/cli/frontend.py)

这对“同角色多段声音不一致”是最关键的能力。

## 3. 当前项目里怎么用最稳

### 3.1 建议的控制层级

对于绘本配音，建议按这 4 层控制：

1. 角色音色：`prompt_wav`
2. 角色一致性：`zero_shot_spk_id`
3. 句子风格：`instruct_text`
4. 句内细节：`[breath]`、`<strong>...</strong>`

优先级是：

`干净 prompt_wav > 固定 zero_shot_spk_id > 稳定 instruct_text > 小幅 speed`

### 3.2 每个角色一条主参考音

推荐：

- `旁白者`：稳定、干净、正常讲述
- `狼先生`：稳定、单人、情绪不要太炸
- `小白兔`：稳定、童声、单人

不要用：

- 混了旁白和角色的长视频音轨
- 带背景音乐的片段
- 情绪起伏特别大的参考音去当全角色主参考音

### 3.3 风格词不要太散

同一个角色，风格词最好只保留少数几个组合。

例如 `狼先生`：

- `serious and calm`
- `serious and commanding`
- `angry and serious`

例如 `旁白者`：

- `calm and wise`
- `joyful and optimistic`
- `empathetic and hopeful`
- `mysterious and surprised`

不要同一个角色今天用：

- `objective`
- `bold`
- `confident`
- `soft`
- `mysterious`
- `joyful`

全部混在一起。模型很容易把“风格变化”放大成“像换了个人”。

## 4. 英文 prompt 还是中文 prompt

结论不要说绝对。

### 论文能支持的结论

论文没有做“中文 prompt vs 英文 prompt”的直接 A/B 实验，所以不能下结论说英文一定更好。

### 但工程上更推荐英文的原因

有两个：

- 论文 Table 1 的 style label 本身就是英文
- 论文 `2.6.1` 和 `2.6.2` 的自然语言 instruction 示例里，本来就有英文句子

所以对 CosyVoice3，推荐优先使用：

```text
You are a helpful assistant. Please speak in a serious and calm style.<|endofprompt|>
```

而不是随意发明一大段中文描述。

### 推荐策略

- 角色风格标签优先用英文
- 方言类可以继续用中文
- 发音修复和正文当然还是中文

## 5. 直接可用的例子

### 5.1 `inference_instruct2` 单句控制

```python
from cosyvoice.cli.cosyvoice import AutoModel

cosyvoice = AutoModel(model_dir='pretrained_models/Fun-CosyVoice3-0.5B')

for out in cosyvoice.inference_instruct2(
    tts_text='我才不吃兔子呢！我只喜欢<strong>最好的面包</strong>！',
    instruct_text='You are a helpful assistant. Please speak in a serious and commanding style.<|endofprompt|>',
    prompt_wav='data/prompt_candidates/wolf_candidate_primary_7s.wav',
    stream=False,
    speed=0.98,
    text_frontend=False,
):
    ...
```

适合：

- 某一句单独测试风格
- 生成试听版本

### 5.2 `zero_shot_spk_id` 固定角色一致性

```python
from cosyvoice.cli.cosyvoice import AutoModel

cosyvoice = AutoModel(model_dir='pretrained_models/Fun-CosyVoice3-0.5B')

cosyvoice.add_zero_shot_spk(
    prompt_text='You are a helpful assistant. Please speak in a serious and calm style.<|endofprompt|>这就是最好的面包。这是最好的苹果面包。',
    prompt_wav='data/prompt_candidates/wolf_candidate_primary_7s.wav',
    zero_shot_spk_id='wolf_master',
)

for out in cosyvoice.inference_instruct2(
    tts_text='可以，但我只教最好的，你能做到最好吗？',
    instruct_text='You are a helpful assistant. Please speak in a serious and commanding style.<|endofprompt|>',
    prompt_wav='data/prompt_candidates/wolf_candidate_primary_7s.wav',
    zero_shot_spk_id='wolf_master',
    stream=False,
    speed=1.0,
    text_frontend=False,
):
    ...
```

适合：

- 同角色多句连续生成
- 绘本角色一致性

### 5.3 `zero_shot` 参考音驱动

```python
for out in cosyvoice.inference_zero_shot(
    tts_text='我真的很棒，我是一个伟大的建筑师！',
    prompt_text='You are a helpful assistant. Please speak like a cheerful girl.<|endofprompt|>。绿绿的是吊车，那个绿绿的是吊车，那个黑黑的也是吊车。',
    prompt_wav='data/xiaolongbao_8s.wav',
    stream=False,
    speed=1.0,
    text_frontend=False,
):
    ...
```

适合：

- 参考音对结果影响更大
- 想优先保音色和说话习惯

### 5.4 细粒度标签

```python
tts_text = '[breath]因为他们那一辈人[breath]在乡里面住的要习惯一点，<strong>邻居都很活络</strong>。'
```

常用规则：

- `[breath]`：换气
- `<strong>...</strong>`：强调重点词
- `[laughter]`：笑声

### 5.5 发音修复

仓库官方示例：

```python
tts_text = '高管也通过电话、短信、微信等方式对报道[j][ǐ]予好评。'
```

也就是把 `给予` 的读音通过 pinyin token 强行指定。

## 6. JSON 方案怎么写

在你当前项目里，推荐这样写：

```json
{
  "roles": {
    "旁白者": {
      "prompt_wav": "data/prompt_candidates/narrator_candidate_primary_6s.wav",
      "prompt_text": "You are a helpful assistant. Please speak in a calm and wise style.<|endofprompt|>小白兔会自己种最好吃的红苹果，自己煮最可口的蘑菇汤。",
      "zero_shot_spk_id": "narrator_master"
    },
    "狼先生": {
      "prompt_wav": "data/prompt_candidates/wolf_candidate_primary_7s.wav",
      "prompt_text": "You are a helpful assistant. Please speak in a serious and calm style.<|endofprompt|>这就是最好的面包。这是最好的苹果面包。这是最好的奶油面包。这是最好的坚果面包。",
      "zero_shot_spk_id": "wolf_master"
    }
  },
  "entries": [
    {
      "index": 37,
      "role": "狼先生",
      "tts_text": "我才不吃兔子呢！我只喜欢<strong>最好的面包</strong>！",
      "api": {
        "name": "inference_instruct2",
        "speed": 0.98,
        "stream": false,
        "text_frontend": false,
        "instruct_text": "You are a helpful assistant. Please speak in a serious and commanding style.<|endofprompt|>"
      },
      "output_wav": "sentences/0037_狼先生.wav",
      "pause_ms_after": 320
    }
  ]
}
```

## 7. 当前项目里的额外工程支持

你当前项目的 [render_dub_plan.py](/Users/citeace/Documents/Projects/MVP/CosyVoice/mvp/render_dub_plan.py) 已经额外支持：

- 角色级 `zero_shot_spk_id`
- 启动时自动注册角色 speaker cache
- CosyVoice3 `cross_lingual` 自动补 `<|endofprompt|>` 前缀

所以你现在不需要每句都手写 speaker 注册逻辑，直接在 JSON 顶层 `roles` 里写就可以了。

## 8. 最推荐的绘本配音工作流

### 旁白

- 用一条稳定中性的单人旁白参考音
- 固定 `zero_shot_spk_id`
- 只保留 3 到 4 种风格：
  - `calm and wise`
  - `joyful and optimistic`
  - `empathetic and hopeful`
  - `mysterious and surprised`

### 狼先生

- 主参考音不要太炸
- 用 `wolf_master` 固定音色
- 风格词只保留：
  - `serious and calm`
  - `serious and commanding`
  - `angry and serious`

### 小白兔

- 童声参考音必须干净
- 用 `rabbit_child` 固定音色
- 风格词只保留：
  - `cheerful girl`
  - `fearful girl`
  - `joyful girl`
  - `proud and joyful girl`

## 9. 一句话总结

如果只记住一条：

**CosyVoice3 的声音控制，最稳的方式不是写更长的 prompt，而是用干净参考音固定 speaker，再用短而稳定的英文 style prompt 做句子控制。**
