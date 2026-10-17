# 发布与恢复记录

主任务的完整 B/C/E/F 结果已在 2026-10-17 08:30:57 UTC 收齐，结论仍为
E1/E2 未达、F 已达。清理前本地提交为 `bd62cb0f1c0b878f64ae097ecf39a1cb4ea7cb99`，
其 tree 为 `b3d57f4c3d5bc1338a2dae90aa9270abba83ccb3`。

普通 `git push` 因当前 CLI 没有 GitHub 凭据失败。随后通过用户已连接的
GitHub 账户发布；未复制或记录凭据。上传清单保存全部 5,553 个变更项和
2,846 个不同的新增文本 blob。清理后的继续执行发现本地 Git 元数据、任务
源码和 checks-v18 已被移除，但该清单及 blob 原文仍在。

从公开基线 `12a1116` 重新取得仓库，再按清单原字节恢复全部变更，得到与
原提交完全相同的 tree。远端一次构造全部路径超时，改为分批组装，最终
远端 tree 也严格等于上述值。这里证明文件内容与模式相同；API 创建的
提交元数据不同，不能声称两个 commit SHA 相同。

实际发布的 r1 commit 为 `682f76acceef1658e23cd6d234134cf4335eabaa`，
父提交为 `12a1116`。更新前再次读取远端：`v18-gptpro` 为 `183cacb0`，
`hardening-v9-v12` 为 `12a1116`；使用旧 SHA 校验和 `force=false` 完成
快进更新。随后从公开远端 fetch，2026-10-17 10:59:56 UTC 的本地检查
确认远端 tree、恢复后的暂存 tree 和原实测 tree 三者相同。

Python 安装也受清理影响，已重新安装同一组精确版本：Python 3.13.16、
NumPy 2.3.4、SciPy 1.17.0、pytest 9.1.1，并实际导入及运行一个有已知
最优值的 MILP 控制。`publication_verify.py` 复核可见 13 文件、五天固定
plant/supply、任务/参考/oracle 源码、48 个 fresh 输入和盲替身冻结哈希。
结果保存于 `publication-verification.json`。这些是恢复完整性检查，
**不是把此前的整套 B/C/E/F 重新标成一次新运行**。

清理前最后追加的 CSV 行序实验尚未进入主提交，其旧输出没有存活副本。
因此恢复脚本并重新执行；`order-probe/` 与 `fairness/order_contract.json`
使用新时间、新运行输出，并明确标注环境清理后重跑。它们不计入原先的
480 次 fuzz 尝试，也没有引入第二个功能性 task 修订。

后续提交只补这些文档、完整性证据及附加实验。PR 以 **E 未达标** 的草稿
提出；该发布不代表允许将候选标作“稳定六场全挂”，也没有合并到 main。
