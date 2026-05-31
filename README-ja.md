# ClearML分子シミュレーションチュートリアル

[English version](README.md)

このリポジトリは、ClearMLで分子シミュレーションの実行を管理するためのチュートリアルです。

現在はGAMESSを例にしていますが、考え方は他の分子シミュレーションソフトにも応用できます。入力ファイルをClearMLのアーティファクト（ClearMLに保存するファイル）として渡し、Agent上で分子シミュレーションソフトを実行し、別のClearML Taskでログを追跡・判定する、という構成です。

## 位置づけ

このリポジトリはチュートリアルですが、コードはそのまま小さな土台として使えるようにしています。

- 分子シミュレーションソフトごとの再利用コードは`clearml_gamess/`のようなディレクトリに置く
- 具体的なClearMLタスク投入用スクリプトは入力ファイルのそばに`<入力ファイル名（拡張子なし）>.cml.py`として置く
- ClearML Agentの起動など、ローカル運用の補助は`tools/`に置く
- Agent向けの設計メモは`skills/`に置く

## 構成

```text
clearml_gamess/
  README.md
  README-ja.md
  cml_pipeline_gamess.py
  cml_task_run_gamess.py
  cml_task_track_gamess.py
  run_gamess.py
  track_gamess.py
  examples/

tools/
  start_clearml_agent.py

skills/
  clearml/
    task-design/
      SKILL.md
    artifacts/
      SKILL.md
    logging/
      SKILL.md
    development-workflow/
      SKILL.md
    inspect/
      SKILL.md

local/
  clearml.conf.example
```

## 用語

| 用語 | 意味 | このチュートリアルでの使い方 |
| --- | --- | --- |
| ClearML Server | Web UIとbackendを提供し、Taskやworkflowの記録、アーティファクト情報をClearML上で扱えるようにする場所です。アーティファクトの実体はClearML Serverだけでなく、設定によって外部object storageや共有ファイルシステムに置くこともできます。 | Task、Pipeline、ログ、アーティファクトを後から確認するための管理先として使います。 |
| Task | ClearMLが管理する実行単位です。実行するコード、パラメータ、ログ、metrics、アーティファクトなどがTaskに紐づきます。 | GAMESSを起動するTaskと、GAMESSログを追跡するTaskを分けています。 |
| Queue | 実行待ちのTaskを並べる場所です。 | `.cml.py`で作ったPipeline内のTaskをqueueへ投入し、Agentが順に取得します。 |
| ClearML Agent | queueを監視し、Taskを取得して、リポジトリ取得、環境構築、コード実行を行うプロセスです。 | エージェントPC上でAgentを起動し、queueから受け取ったTaskとしてGAMESSを実行します。 |
| Pipeline | 複数のTaskをつなげたworkflowです。 | GAMESSを起動するTaskとログを追跡するTaskをPipelineとしてつなげます。 |
| ClearMLタスク（Pipeline）投入用PC | ClearMLの正式なサーバー部品ではなく、`.cml.py`を実行してPipelineを作り、Taskをqueueへ投入する作業場所を指します。 | 入力ファイルのそばにある`.cml.py`を実行するPCです。エージェントPCと同じでも別でもかまいません。 |
| エージェントPC | ClearML Agentを動かすPCです。 | GAMESSをインストールし、`tools/start_clearml_agent.py`をそのマシンの`local/clearml.conf`で実行するPCです。 |

小さく試すだけなら、ClearML Server、投入用PC、エージェントPCをすべて同じマシン上で動かしてもかまいません。

## クイックスタート

### 初期設定

#### ClearML server

ClearML serverを用意します。ClearML SDKやAgentがServerへTask、ログ、アーティファクト情報を登録・取得できるようにするためです。

最初は公式の[ClearML hosted server](https://app.clear.ml/)を使うのが簡単です。

- workspaceを作る
- API credentialを発行する
- API credentialは後で`local/clearml.conf`に設定する

公式hosted serverはチュートリアルや小規模な検証には便利です。一方で、分子シミュレーションでは入力、ログ、scratch/restart、補助出力などのファイルが増えやすいため、企業内利用で自社データや大きな計算ログを扱う場合は、self-hosted ClearML serverや外部object storageを使う構成を検討してください。このリポジトリではまだ自前serverの構築手順は扱っていませんが、将来的にserver設定例を追加する可能性があります。

#### リポジトリ

ClearMLタスク投入用PCとエージェントPCの両方で、このリポジトリを`git clone`します。同じPCで試す場合は一つのcloneで十分です。エージェントPCにもcloneするのは、`tools/start_clearml_agent.py`をそのマシンの`local/clearml.conf`で実行するためです。

```bash
git clone https://github.com/kyusque/clearml-molecular-simulation-tutorial.git
cd clearml-molecular-simulation-tutorial
```

#### ClearML認証設定

`local/clearml.conf.example`をもとに`local/clearml.conf`を作り、発行したAPI credentialを設定します。ClearMLタスク投入用PCとエージェントPCが別の場合は、それぞれのcloneの`local/clearml.conf`に配置してください。

`local/`はこのマシンだけの設定や一時ログの置き場です。投入ログを残す場合は`local/logs/`に置き、`clearml.conf`の隣には置かないようにします。

#### uv

ClearMLタスク投入用PCとエージェントPCの両方に`uv`をインストールします。

`uv`が未インストールの場合は次のように入れます。このリポジトリのAgent起動helperとClearMLタスク投入用`.cml.py`にはPEP 723のinline script metadataを書いているため、クイックスタートでは`uv sync`は不要です。

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linuxでは次の形です。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### GAMESS

エージェントPCにGAMESSをインストールします。GAMESSの配置や`rungms`の扱いは[clearml_gamess/README-ja.md](clearml_gamess/README-ja.md)を参照してください。

### 実行

エージェントPCでClearML Agentを起動します。

```powershell
uv run tools/start_clearml_agent.py --queue default --create-queue --cpu-only
```

ClearMLタスク投入用PCでGAMESSのサンプルPipelineを作成し、Taskをqueueへ投入します。

```powershell
uv run clearml_gamess/examples/water_rhf_sto3g_opt.cml.py
```

## 利用者と開発者

入力ファイルを少し直して計算を流すだけなら、Gitを強く意識する必要はありません。`.inp`と`.cml.py`を編集して新しいPipelineを作れば、入力ファイルは`pipeline_input`アーティファクトとしてClearMLに残ります。

Gitが重要になるのは、Agent上で動くタスク実行コードを調整する場合です。アーティファクト登録、ログのプレビュー、scratchファイルの回収、metrics抽出などを直すときは、そのPythonコードの差分がAgentへ届く必要があります。この用途では、毎回commitするよりも、意図した差分がTaskのsource diffに入っていることを確認する方が大事です。新規ファイルは`git add`してから投入してください。

## 詳細

GAMESS固有の使い方と設計は、こちらにまとめています。

- [clearml_gamess/README-ja.md](clearml_gamess/README-ja.md)

Agent向けの設計メモと開発時の運用メモはこちらです。

- [skills/clearml/task-design/SKILL.md](skills/clearml/task-design/SKILL.md)
- [skills/clearml/artifacts/SKILL.md](skills/clearml/artifacts/SKILL.md)
- [skills/clearml/logging/SKILL.md](skills/clearml/logging/SKILL.md)
- [skills/clearml/development-workflow/SKILL.md](skills/clearml/development-workflow/SKILL.md)
- [skills/clearml/inspect/SKILL.md](skills/clearml/inspect/SKILL.md)

## 基本パターン

分子シミュレーションソフトごとに、基本的には次の形で組みます。

1. 入力ファイルをClearMLアーティファクトとして登録する
2. ClearML Agent上で分子シミュレーションソフトを実行する
3. 後続のTaskへ渡すための実行マニフェストJSONを作る
4. 別のClearML Taskで実行マニフェストJSONを読み、ログを追跡して終了状態を判定する
5. ログやscratch/tempなど、実行後に生成されたファイルをアーティファクトとして登録する
6. track側の処理でエネルギーなどの必要な値を抽出し、`tracking_metrics`として残す
7. 分子シミュレーションソフトが異常終了していた場合は、アーティファクトを残したうえで判定側のClearML Taskをfailedにする

このリポジトリでは、この流れをClearML Pipelineの`run_gamess` stepと`track_gamess` stepとして表現しています。
