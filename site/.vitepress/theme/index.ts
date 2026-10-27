import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
// 渲染系统自 tamcpp 移植:品牌色与排版基座(custom),代码/引用/表格/列表四张正文卡片
// 导入顺序照抄 tamcpp 的 theme/index.ts,层叠关系才一致
import './custom.css'
import './article-code.css'
import './article-quote.css'
import './article-table.css'
import './article-list.css'
import HomeHeroVisual from './components/HomeHeroVisual.vue'
import StatusToast from './components/StatusToast.vue'

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      // 首页 hero 右侧的终端卡(dtc 编译打字机),布局挂点在 custom.css 的
      // 「Hero Image Slot」段(VPHero .image-container 那套)
      'home-hero-image': () => h(HomeHeroVisual),
      // 文章状态弹窗:frontmatter 带 status/current_status 的页面,进页时
      // 右下角滑入 MC 成就风格的提示(tamcpp 同款,挂在全局布局槽位)
      'layout-top': () => h(StatusToast),
    })
  },
}
