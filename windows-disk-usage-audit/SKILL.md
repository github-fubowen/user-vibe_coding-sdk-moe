---
name: windows-disk-usage-audit
description: Windows 磁盘占用只读调查（C/D 盘）。当用户要求"调查磁盘占用/清理空间/磁盘分析/找大文件/C盘满了"时使用。只读扫描 + 报告，不删除任何文件。含 PowerShell 5.1 中文编码坑、robocopy 用法、junction/符号链接去重规则。
agent_created: true
version: 1.0.0
---

# Windows Disk Usage Audit（磁盘占用只读调查）

## 纪律（用户硬性要求）
- **只读调查**：扫描 + 报告。删除/移动文件必须先给清单、风险说明，获用户确认后另起任务执行。
- 结论先行、Markdown 表格 + 风险矩阵、中文输出。

## 工作流
1. **总览**：`Get-PSDrive C` 取 Total/Used/Free；根目录文件（hiberfil.sys/pagefile.sys/swapfile.sys）用 `Get-ChildItem C:\ -Force -File` 的 `.Length`。
2. **目录大小**：用 robocopy 而非 Get-ChildItem 递归（快 5-10 倍）：
   ```
   robocopy <dir> NULL /L /S /BYTES /NFL /NDL /NJH /NP /XJ
   ```
   - 汇总行格式：`       字节:  59605336  59605336 ...`，**取第一个数字 = Total**。
   - 解析正则：`(?:字节|Bytes)\s*:\s*(\d+)`（兼容中英文区域）。
3. **下钻**：对大目录（Windows/Users/Program Files/ProgramData）逐个子目录跑同一 robocopy，输出 TSV（`DIR\tpath\tbytes`）。
4. **junction/符号链接去重**（必做，否则重复计数）：
   - `Get-ChildItem <dir> -Force | Where-Object {$_.Attributes -match 'ReparsePoint'}` 枚举链接；
   - 已知系统旧链接（勿计）：Documents and Settings≡Users、All Users≡ProgramData、Application Data≡Roaming、Local Settings≡Local、My Documents≡Documents、ProgramData\Application Data≡ProgramData 自身；
   - **用户自定义链接**（如 D:\softlink、D:\UserData\fu268-linked 体系）：子目录扫描会对"链接根"跟随目标，报出 D 盘内容 —— 必须按 ReparsePoint 清单排除，只报 C 盘真实项；
   - 交叉校验：子目录求和 ≈ 父目录 robocopy 值（±5%），不符必有链接或硬链接。
5. **硬链接注意**：WinSxS/System32 等用硬链接，robocopy 名义大小偏大；报告标注"名义大小"，权威口径用 Filesystem 的 Used。
6. **报告**：深色 HTML 仪表盘（参考 `D盘占用分析报告.html` / `C盘占用分析报告.html` 的 CSS：cards + 条形图 + 风险矩阵表 + 建议清单），含"结论先行"摘要和只读声明。

## 踩坑记录（2026-08-18 实测）
- **PowerShell 5.1 脚本编码坑**：Write 工具写出的 .ps1 是 UTF-8 无 BOM，PS 5.1 按 ANSI(GBK) 解析 → 脚本内中文正则变乱码、静默失效。**修复：.ps1 必须带 UTF-8 BOM**（`printf '\xef\xbb\xbf'` 前缀）。内联命令不受影响。
- **robocopy /NJS 会吞掉汇总行**（Bytes/字节 在 Summary 里）→ 解析全为 0。只保留 /NJH，不要 /NJS。
- **PowerShell 工具前台输出可能不被捕获**（本环境）：需用 run_in_background + TaskOutput 或写文件后 Read。
- robocopy 输出在中文系统为「字节:」，英文为「Bytes:」。
