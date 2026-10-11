import DefaultTheme from 'vitepress/theme'
// 渲染系统自 tamcpp 移植:品牌色与排版基座(custom),代码/引用/表格/列表四张正文卡片
// 导入顺序照抄 tamcpp 的 theme/index.ts,层叠关系才一致
import './custom.css'
import './article-code.css'
import './article-quote.css'
import './article-table.css'
import './article-list.css'

export default DefaultTheme
