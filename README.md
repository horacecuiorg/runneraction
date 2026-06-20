# RunnerAction Repository

这是一个用于 GitHub Actions 运行自动化脚本的仓库，支持使用 **Python**、**Bash** 以及 **.NET (C#)** 编写脚本。

---

## 目录结构 (Directory Structure)

```text
runneraction/
├── .github/
│   └── workflows/
│       └── run-scripts.yml       # GitHub Actions 工作流配置文件
├── scripts/
│   ├── read_vault.py             # Vault 密钥读取 Python 脚本
│   ├── sample_bash.sh            # 规范的 Bash 脚本模版
│   ├── requirements.txt          # Python 依赖包列表
│   └── dotnet/
│       └── RunnerScripts/        # .NET 8.0 控制台脚本项目
│           ├── RunnerScripts.csproj
│           └── Program.cs
├── .gitignore                    # Git 忽略配置
└── README.md                     # 项目说明文档
```

---

## 脚本文件及本地运行方法 (How to run locally)

### 1. Bash 脚本
*   **文件路径:** [sample_bash.sh](file:///home/ubuntu/document/github_org/runneraction/scripts/sample_bash.sh)
*   **本地运行方式:**
    ```bash
    # 赋予执行权限并运行
    chmod +x scripts/sample_bash.sh
    ./scripts/sample_bash.sh --name "Antigravity"
    ```

### 2. Python 脚本
*   **文件路径:** [read_vault.py](file:///home/ubuntu/document/github_org/runneraction/scripts/read_vault.py)
*   **依赖安装:**
    ```bash
    pip install -r scripts/requirements.txt
    ```
*   **本地运行方式:**
    ```bash
    # 查看帮助文档
    python3 scripts/read_vault.py --help
    
    # 获取 Vault 秘钥 (需要配置 VAULT_ADDR 或 VAULT_URL 以及 VAULT_TOKEN 环境变量)
    python3 scripts/read_vault.py -p "/v1/kv/data/home" -k "my_secret_key"
    ```

### 3. .NET Script (C# 脚本)
*   **文件路径:** [Program.cs](file:///home/ubuntu/document/github_org/runneraction/scripts/dotnet/RunnerScripts/Program.cs) (项目文件: [RunnerScripts.csproj](file:///home/ubuntu/document/github_org/runneraction/scripts/dotnet/RunnerScripts/RunnerScripts.csproj))
*   **前置要求:** 本地需安装 [.NET 10.0 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)。
*   **本地运行方式:**
    ```bash
    # 进入项目目录运行，或者通过项目路径运行
    dotnet run --project scripts/dotnet/RunnerScripts/RunnerScripts.csproj -- "Antigravity"
    ```

---

## GitHub Actions 集成 (GitHub Actions Workflow)

## GitHub Actions 集成 (GitHub Actions Workflow)

我们配置了两个工作流文件：

### 1. [run-scripts.yml](file:///home/ubuntu/document/github_org/runneraction/.github/workflows/run-scripts.yml)
*   **触发方式:** 支持 `workflow_dispatch` 手动触发（无需参数）。
*   **执行步骤:**
    1.  检出代码。
    2.  安装 [requirements.txt](file:///home/ubuntu/document/github_org/runneraction/scripts/requirements.txt) 中的 Python 依赖包。
    3.  测试运行 Python 脚本的 `--help` 命令。
    4.  执行 Bash 脚本 [sample_bash.sh](file:///home/ubuntu/document/github_org/runneraction/scripts/sample_bash.sh)。
    5.  编译并运行 C# 脚本 [Program.cs](file:///home/ubuntu/document/github_org/runneraction/scripts/dotnet/RunnerScripts/Program.cs)。

### 2. [telegram-notify.yml](file:///home/ubuntu/document/github_org/runneraction/.github/workflows/telegram-notify.yml)
*   **触发方式:** 支持 `workflow_dispatch` 手动触发（无需参数）。
*   **执行步骤:**
    1.  检出代码。
    2.  安装 [requirements.txt](file:///home/ubuntu/document/github_org/runneraction/scripts/requirements.txt) 中的 Python 依赖包并将输出写入日志文件 `run.log`。
    3.  从 Vault 秘密路径 `/v1/kv/data/github` 读取并掩码解析 `GIT_PUSH_BOT` 和 `MY_TEL_ID`，相关日志写入 `run.log`。
    4.  将包含执行日志的 `run.log` 文本文件作为附件通过 Telegram 发送到指定的 chat_id。
