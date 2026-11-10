# 发布适配器契约

## 项目关联文件

项目根 `.story-publish.json` 是机器本地关联，不属于作品事实，也不得随 oh-story 正式包分发。版本 1 结构：

    {
      "schema_version": 1,
      "platforms": {
        "fanqie": {
          "adapter": "/absolute/path/project_publish.py",
          "python": "/absolute/path/.venv/bin/python",
          "cwd": "/absolute/path/publisher"
        }
      }
    }

文件只保存可执行关联，不保存 Book ID、Cookie、密码或 token。作品和正文目录仍由适配器自己的项目配置管理。

## 动作分级

| 动作 | 副作用 | 桥接要求 |
|---|---|---|
| `status` / `preview` | 无远端副作用 | 可直接执行 |
| `books` / `preflight` | 只读平台登录态 | 用户已要求查询或发布流程需要 |
| `login` | 更新本地认证状态 | 用户明确要求登录；验证码/MFA人工接管 |
| `draft` | 新建远端草稿 | `--confirm-remote-draft` |
| `edit` | 修改已有远端章节 | 下游 `--confirm-live` 与显式AI申报 |
| `publish` | 立即正式发布 | 下游 `--confirm-live` 与显式AI申报 |
| `schedule` | 新建排期发布 | 下游 `--confirm-live`、显式AI申报、日期/时间/每日章数 |

桥接层只允许上述动作，拒绝 `gui` 和任意未知动作。它使用参数数组调用子进程，禁止 `shell=True`。

## 配置与运行

`configure fanqie` 先校验 adapter、python 与 cwd，原子写入配置并尽量收紧为当前用户可读写。重复配置同一值必须幂等。

`run` 不解释平台业务参数，只完成动作白名单、确认门和安全进程调用。番茄适配器继续负责：

- 本地章节解析和字数检查；
- 线上全状态防重；
- 草稿、待发布和审核中状态识别；
- AI申报控件的真实选中校验；
- 平台写入结果判定。

## 失败与重试

非零退出码原样返回。任何远程写动作出现超时、浏览器关闭、未知弹窗或结果不明时，视为状态不确定：只允许先运行只读检查，不得自动重放原命令。这样避免第一次实际成功、重试又重复建章。
