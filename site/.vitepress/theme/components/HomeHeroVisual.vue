<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// 首页 hero 终端卡:把 0.3 的动手环节(dtc 编译 mini.dts)演成打字机。
// 剧本里的命令、字节数、魔数都是 0.3 用 dtc v1.8.1 真实跑出来的;
// xxd 行为容纳卡片宽度做了截短,截断点落在真实的字节组边界上,不造字节。
type LineType = 'cmd' | 'ok' | 'save' | 'out'
interface Line {
  text: string
  type: LineType
}

const script: Line[] = [
  { text: '已就绪 mini.dts(十四行)', type: 'save' },
  { text: '$ dtc -I dts -O dtb -o mini.dtb mini.dts', type: 'cmd' },
  { text: '✓ 编译完成,mini.dtb 共 293 字节', type: 'ok' },
  { text: '$ xxd mini.dtb | head -1', type: 'cmd' },
  { text: '00000000: d00d feed 0000 0125 ...', type: 'out' },
  { text: '$ dtc -I dtb -O dts mini.dtb | head -4', type: 'cmd' },
  { text: '/dts-v1/;', type: 'out' },
  { text: '', type: 'out' },
  { text: '/ {', type: 'out' },
  { text: '    compatible = "edts,a_demo";', type: 'out' },
]

const CHAR_MS = 26        // 每字毫秒
const LINE_MS = 90        // 行间停顿
const LOOP_MS = 2600      // 跑完后驻留再循环

const done = ref<Line[]>([])
const partial = ref('')
const partialType = ref<LineType>('cmd')
const finished = ref(false)

let lineIdx = 0
let charIdx = 0
let timer: ReturnType<typeof setTimeout> | null = null

function reset() {
  done.value = []
  partial.value = ''
  partialType.value = 'cmd'
  finished.value = false
  lineIdx = 0
  charIdx = 0
  tick()
}

function tick() {
  if (lineIdx >= script.length) {
    finished.value = true
    timer = setTimeout(reset, LOOP_MS)
    return
  }
  const line = script[lineIdx]
  const chars = Array.from(line.text)   // 按码点切,中文不会断半截
  if (charIdx <= chars.length) {
    partial.value = chars.slice(0, charIdx).join('')
    partialType.value = line.type
    charIdx++
    timer = setTimeout(tick, CHAR_MS)
  } else {
    done.value.push(line)
    partial.value = ''
    lineIdx++
    charIdx = 0
    timer = setTimeout(tick, LINE_MS)
  }
}

onMounted(() => {
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (reduced) {
    // 减弱动效:一次性显示全部内容
    done.value = script.slice()
    finished.value = true
  } else {
    tick()
  }
})
onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <div class="hero-visual">
    <div class="terminal">
      <div class="terminal__bar">
        <span class="dot dot--red" />
        <span class="dot dot--yellow" />
        <span class="dot dot--green" />
        <span class="terminal__title">mini.dts — zsh</span>
      </div>

      <div class="terminal__body">
        <div
          v-for="(ln, i) in done"
          :key="'d' + i"
          class="ln"
          :class="'ln--' + ln.type"
        >{{ ln.text }}</div>

        <div
          v-if="!finished"
          class="ln"
          :class="'ln--' + partialType"
        >{{ partial }}<span class="cursor">▋</span></div>

        <div v-else class="ln ln--prompt"><span class="cursor">▋</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero-visual {
  /* 容下最长命令行(≈42 字符 × 9.3px ≈ 390px + 44px 内边距 + 2px 边框),取 480px 留余量;
     max-width:100% 保证窄屏/窄图列不被遮挡。 */
  width: 480px;
  max-width: 100%;
  margin: 0 auto;
  animation: hero-fade-up 0.7s cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
}

.terminal {
  position: relative;
  box-sizing: border-box;
  border: 1px solid var(--term-border);
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(135deg, var(--term-bg-from) 0%, var(--term-bg-to) 100%);
  box-shadow:
    0 22px 56px var(--term-shadow),
    0 6px 14px rgba(0, 0, 0, 0.16);
  animation: terminal-glow 4s ease-in-out infinite;
}

.terminal__bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 13px 16px;
  background: rgba(0, 0, 0, 0.22);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot--red { background: #ff5f56; }
.dot--yellow { background: #ffbd2e; }
.dot--green { background: #27c93f; }

.terminal__title {
  margin-left: 10px;
  color: var(--term-title);
  font-family: var(--vp-font-family-mono);
  font-size: 13px;
  letter-spacing: 0.3px;
}

.terminal__body {
  padding: 22px 22px 20px;
  font-family: var(--vp-font-family-mono);
  font-size: 15.5px;
  line-height: 1.75;
  /* 预留峰值高度 = 10 条剧本 + 1 收尾 prompt = 11 行,从开打就占满,避免边打字边撑高抖一下 */
  min-height: calc(19.25em + 42px);
}

.ln {
  white-space: pre;        /* 保留命令与输出的空格缩进 */
  min-height: 1.75em;
}

.ln--cmd { color: var(--term-cmd); }      /* shell 命令(钢蓝) */
.ln--ok { color: var(--term-ok); }        /* 编译成功(语义绿) */
.ln--save { color: var(--term-save); }    /* 文件就绪(琥珀) */
.ln--out { color: var(--term-out); }      /* 命令输出 */
.ln--prompt { color: var(--term-ok); }

.cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--term-ok);
  animation: blink 1.05s step-end infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  50.01%, 100% { opacity: 0; }
}

@keyframes terminal-glow {
  0%, 100% {
    box-shadow:
      0 22px 56px var(--term-shadow),
      0 6px 14px rgba(0, 0, 0, 0.22),
      0 0 0 0 rgba(96, 165, 250, 0);
  }
  50% {
    box-shadow:
      0 22px 56px var(--term-shadow),
      0 6px 14px rgba(0, 0, 0, 0.20),
      0 0 26px 3px var(--term-glow);
  }
}

@keyframes hero-fade-up {
  from { opacity: 0; transform: translateY(22px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .hero-visual,
  .terminal,
  .cursor {
    animation: none !important;
  }
}

@media (max-width: 639px) {
  .hero-visual {
    /* 手机端父容器(.image-container)是 width:auto 按内容撑开,max-width:100% 会相对它而非视口,
       故直接按视口约束:100vw - 48px(= 手机端 hero 左右各 24px 内边距后的内容宽度)。 */
    max-width: calc(100vw - 48px);
  }
  .terminal__body {
    font-size: 13px;
    padding: 16px 16px 14px;
    min-height: calc(19.25em + 30px);
  }
}
</style>
