# 🔧 快速故障排除指南

## 问题：所有API请求返回500错误

### 症状
```
Failed to load resource: the server responded with a status of 500 (Internal Server Error)
Unexpected token 'I', "Internal S"... is not valid JSON
```

### 原因
**服务器没有运行**

### 解决方案

#### 方法1: 使用启动脚本（推荐）
```bash
./start.sh
```

#### 方法2: 手动启动
```bash
cd /home/landasika/etf-predict
python run.py
```

### 验证服务器已启动
看到以下输出表示成功：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## 问题：浏览器加载旧版本JavaScript

### 症状
浏览器控制台显示加载 `home.js?v=80`，但最新版本是 `v75`

### 原因
浏览器缓存了旧版本的JavaScript文件

### 解决方案

#### Windows/Linux
按 `Ctrl + Shift + R` 或 `Ctrl + F5`

#### Mac
按 `Cmd + Shift + R`

#### 手动清除缓存
1. 按 `F12` 打开开发者工具
2. 右键点击刷新按钮
3. 选择"清空缓存并硬性重新加载"

---

## 问题：登录后仍然提示未认证

### 症状
已成功登录，但API请求仍然返回401错误

### 原因
1. Cookie被浏览器阻止
2. Session配置问题

### 解决方案

#### 1. 检查浏览器Cookie设置
- Chrome: 设置 → 隐私和安全 → Cookie → 允许
- Firefox: 设置 → 隐私与安全 → Cookie和网站数据 → 接受

#### 2. 清除所有Cookie
```bash
# Chrome/Edge
F12 → Application → Cookies → 删除所有

# Firefox
F12 → Storage → Cookies → 删除所有
```

#### 3. 重新登录
1. 访问 http://127.0.0.1:8000
2. 输入秘钥: `admin123`
3. 点击"登录系统"

---

## 问题：修改代码后没有生效

### 症状
修改了JavaScript或CSS文件，但浏览器中看不到变化

### 解决方案

#### 1. 清除浏览器缓存
按 `Ctrl + Shift + R` 强制刷新

#### 2. 检查文件版本号
查看 `<link>` 和 `<script>` 标签中的版本号是否正确：

```html
<!-- 正确 -->
<link rel="stylesheet" href="/static/css/home.css?v=8">
<script src="/static/js/home.js?v=75"></script>

<!-- 错误（浏览器缓存了旧版本） -->
<script src="/static/js/home.js?v=80"></script>
```

#### 3. 重启服务器
```bash
# 按 Ctrl+C 停止服务器
# 重新启动
python run.py
```

---

## 完整的重置流程

如果遇到问题，按以下步骤完全重置：

### 1. 停止服务器
```bash
# 按 Ctrl+C 停止运行中的服务器
```

### 2. 清除浏览器数据
```bash
# Chrome/Edge:
# 1. Ctrl+Shift+Delete
# 2. 选择"Cookie和其他网站数据"
# 3. 点击"清除数据"

# 或使用开发者工具:
# F12 → Application → Clear storage → Clear site data
```

### 3. 重启服务器
```bash
cd /home/landasika/etf-predict
./start.sh
```

### 4. 强制刷新浏览器
```bash
# Ctrl + Shift + R (Windows/Linux)
# Cmd + Shift + R (Mac)
```

### 5. 重新登录
```bash
# 访问 http://127.0.0.1:8000
# 输入秘钥: admin123
```

---

## 快速诊断检查清单

在请求帮助前，请确认以下各项：

- [ ] 服务器正在运行（`ps aux | grep python`）
- [ ] 浏览器已强制刷新（Ctrl+Shift+R）
- [ ] Cookie已启用（F12 → Application → Cookies）
- [ ] 已成功登录（页面右上角显示登出按钮）
- [ ] 查看了浏览器控制台错误（F12 → Console）
- [ ] 查看了网络请求状态（F12 → Network）
- [ ] 检查了服务器日志（`tail -f logs/*.log`）

---

## 获取帮助

如果问题仍然存在，请提供以下信息：

1. **浏览器控制台输出**（F12 → Console）
2. **网络请求详情**（F12 → Network → 失败的请求）
3. **服务器日志**（`tail -50 logs/server.log`）
4. **操作系统和浏览器版本**
5. **复现步骤**

---

**最后更新**: 2026-03-09
