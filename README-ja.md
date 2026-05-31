# ClearML分子シミュレーションチュートリアル

[English version](README.md)

このリポジトリは、ClearMLで分子シミュレーションの実行を管理するためのチュートリアルです。

現在はGAMESSを例にしていますが、考え方は他の外部シミュレーションプログラムにも応用できます。入力ファイルをClearML artifactとして渡し、Agent上でシミュレーターを投入し、別のClearML Taskでログを追跡・判定する、という構成です。

## 位置づけ

このリポジトリはチュートリアルですが、コードはそのまま小さな土台として使えるようにしています。

- シミュレーターごとの再利用コードは`clearml_gamess/`のようなディレクトリに置く
- 具体的な投入例は入力ファイルのそばに`<入力ファイル名（拡張子なし）>.cml.py`として置く
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

draft.md
```

## まず動かす

まずClearML serverを用意します。最初は公式のClearML hosted serverを使うのが簡単です。`app.clear.ml`でworkspaceを作り、API credentialを発行して、`local/clearml.conf`に設定します。

分子シミュレーションでは、入力、ログ、scratch/restart、補助出力などのファイルが増えやすく、公式serverだけでは容量や運用面がきつくなる可能性があります。企業内利用で自社データや大きな計算ログを扱うなら、頑張ってself-hosted ClearML serverや外部object storageを用意する方がよいはずです。このリポジトリではまだ自前serverの構築手順は扱っていませんが、そのうちserver設定例を追加するかもしれません。

依存関係を入れます。

```powershell
uv sync
```

ClearML設定は`local/clearml.conf.example`をもとに`local/clearml.conf`を作ってください。`local/`はこのマシンだけの設定や一時ログの置き場です。投入ログを残す場合は`local/logs/`に置き、`clearml.conf`の隣には置かないようにします。

ClearML Agentを起動します。

```powershell
uv run start-clearml-agent --queue default --create-queue --cpu-only
```

GAMESSのサンプルPipelineを投入します。

```powershell
uv run python clearml_gamess/examples/water_rhf_sto3g_opt.cml.py
```

## 利用者と開発者

入力ファイルを少し直して計算を流すだけなら、Gitを強く意識する必要はありません。`.inp`と`.cml.py`を編集して新しいPipelineを作れば、入力ファイルは`pipeline_input` artifactとしてClearMLに残ります。

Gitが重要になるのは、Agent上で動くtask wrapperを調整する場合です。artifact uploadのcallback、ログのpreview、scratch回収、metrics抽出などを直すときは、そのPythonコードの差分がAgentへ届く必要があります。この用途では、毎回commitするよりも、意図した差分がTaskのsource diffに入っていることを確認する方が大事です。新規ファイルは`git add`してから投入してください。

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

シミュレーターごとに、基本的には次の形で組みます。

1. 入力ファイルをClearML artifactとして登録する
2. ClearML Agent上でシミュレーターを投入する
3. 下流へ渡すためのrun manifest JSONを作る
4. 別のClearML Taskでrun manifest JSONを読み、ログを追跡して終了状態を判定する
5. ログやscratch/tempなど、実行後に生成されたファイルをartifactとして登録する
6. 必要な値をcallbackで抽出し、`tracking_metrics`として残す
7. シミュレーターが異常終了していた場合は、artifactを残したうえで判定側のClearML Taskをfailedにする

このリポジトリでは、この流れをClearML Pipelineの`run_gamess` stepと`track_gamess` stepとして表現しています。
